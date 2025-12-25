import base64
import logging
import json
import subprocess
import psutil
import urllib.request
import urllib.error
import shutil
import time
from collections import deque
from datetime import datetime
from threading import Lock
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from .config import get_config
from .file_manager import FileManager

logger = logging.getLogger(__name__)

app = FastAPI(title="RSPI LocalServer", version="2.0.0")

# Time-series buffer for 30-minute trends (collect every 10 seconds = 180 samples)
metrics_history = deque(maxlen=180)
metrics_lock = Lock()

# Configure CORS for LAN access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize file manager
file_manager = FileManager()

# App state management
APPS_STATE_FILE = Path("/opt/rspi-localserver/apps_state.json")
APPS_DIR = Path("/opt/rspi-localserver/apps")
# Local repo copy (for offline installs); install.sh will place apps/ here
LOCAL_REPO_APPS = Path(__file__).parent.parent / "apps"

# GitHub raw base (configurable)
cfg = get_config()
GITHUB_RAW_BASE = cfg.get(
    "apps.github_raw_base",
    "https://raw.githubusercontent.com/MDSonar/RSPI_LocalServer/main/apps",
)


def fetch_json(url: str, timeout: int = 8):
    """Fetch JSON from URL with User-Agent and return dict."""
    req = urllib.request.Request(url, headers={"User-Agent": "rspi-localserver/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())

def load_app_state():
    """Load installed apps state."""
    if APPS_STATE_FILE.exists():
        try:
            return json.loads(APPS_STATE_FILE.read_text())
        except:
            pass
    return {"installed": ["systeminfo", "taskmanager"]}  # Mandatory apps

def save_app_state(state):
    """Save installed apps state."""
    try:
        APPS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        APPS_STATE_FILE.write_text(json.dumps(state, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save app state: {e}")
        return False

def get_app_manifest(app_id):
    """Get app manifest from installed location or GitHub."""
    # Try local first
    for category in ["core", "optional"]:
        manifest_path = APPS_DIR / category / app_id / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except:
                pass
    
    # Try local repo copy (offline support)
    for category in ["core", "optional"]:
        manifest_path = LOCAL_REPO_APPS / category / app_id / "manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text())
            except:
                pass

    # Try GitHub
    try:
        for category in ["core", "optional"]:
            url = f"{GITHUB_RAW_BASE}/{category}/{app_id}/manifest.json"
            try:
                return fetch_json(url)
            except Exception as e:
                logger.warning(f"Manifest fetch failed from {url}: {e}")
    except Exception:
        pass
    
    return None

def download_app_from_github(app_id):
    """Download app files from GitHub."""
    manifest = get_app_manifest(app_id)
    if not manifest:
        raise Exception("App manifest not found (check github_raw_base and connectivity)")
    
    # Determine category
    category = "optional"  # Default, core apps are pre-installed
    for cat in ["core", "optional"]:
        check_path = APPS_DIR / cat / app_id
        if check_path.exists():
            category = cat
            break
    
    app_dir = APPS_DIR / category / app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    
    # Download manifest (GitHub first, then local fallback)
    manifest_path = app_dir / "manifest.json"
    try:
        manifest_url = f"{GITHUB_RAW_BASE}/{category}/{app_id}/manifest.json"
        urllib.request.urlretrieve(manifest_url, str(manifest_path))
    except Exception as e:
        logger.warning(f"GitHub manifest fetch failed for {app_id}: {e}; trying local copy")
        local_manifest = LOCAL_REPO_APPS / category / app_id / "manifest.json"
        if not local_manifest.exists():
            logger.error(f"Local manifest missing at {local_manifest}")
            raise
        shutil.copy(local_manifest, manifest_path)

    # Download each file
    for file_name in manifest["files"]:
        file_path = app_dir / file_name
        try:
            file_url = f"{GITHUB_RAW_BASE}/{category}/{app_id}/{file_name}"
            urllib.request.urlretrieve(file_url, str(file_path))
            logger.info(f"Downloaded {file_name} for app {app_id}")
        except Exception as e:
            logger.warning(f"GitHub fetch failed for {file_name}: {e}; trying local copy")
            local_file = LOCAL_REPO_APPS / category / app_id / file_name
            if not local_file.exists():
                logger.error(f"Local file missing at {local_file}")
                raise
            shutil.copy(local_file, file_path)
    
    return True


def verify_auth(authorization: str = None):
    """Simple Basic Auth verification."""
    config = get_config()
    if not config.get("auth.enabled", False):
        return True
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        scheme, credentials = authorization.split()
        if scheme.lower() != "basic":
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        
        expected_user = config.get("auth.username", "admin")
        expected_pass = config.get("auth.password", "admin123")
        
        if username != expected_user or password != expected_pass:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        return True
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/", response_class=HTMLResponse)
async def root(authorization: str = None):
    """Serve the dashboard."""
    verify_auth(authorization)
    ui_path = Path(__file__).parent / "static" / "dashboard.html"
    if ui_path.exists():
        return ui_path.read_text()
    return "<h1>RSPI LocalServer</h1><p>Dashboard not found</p>"


@app.get("/apps/filemanager", response_class=HTMLResponse)
async def filemanager_app(authorization: str = None):
    """Serve the file manager app."""
    verify_auth(authorization)
    
    # Try installed location first
    for category in ["core", "optional"]:
        ui_path = APPS_DIR / category / "filemanager" / "filemanager.html"
        if ui_path.exists():
            return ui_path.read_text()
    
    # Fallback to static (dev mode)
    ui_path = Path(__file__).parent / "static" / "filemanager.html"
    if ui_path.exists():
        return ui_path.read_text()
    
    return "<h1>File Manager</h1><p>App not installed. Please install from dashboard.</p>"


@app.get("/apps/systeminfo", response_class=HTMLResponse)
async def systeminfo_app(authorization: str = None):
    """Serve the system info app."""
    verify_auth(authorization)
    # Prefer the compact dev fallback to ensure latest UI
    ui_path = Path(__file__).parent / "static" / "systeminfo.html"
    if ui_path.exists():
        return ui_path.read_text()

    # Otherwise serve installed app
    for category in ["core", "optional"]:
        ui_path = APPS_DIR / category / "systeminfo" / "systeminfo.html"
        if ui_path.exists():
            return ui_path.read_text()

    return "<h1>System Info</h1><p>App not found</p>"


@app.get("/apps/taskmanager", response_class=HTMLResponse)
async def taskmanager_app(authorization: str = None):
    """Serve the task manager app."""
    verify_auth(authorization)
    
    for category in ["core", "optional"]:
        ui_path = APPS_DIR / category / "taskmanager" / "taskmanager.html"
        if ui_path.exists():
            return ui_path.read_text()
    
    ui_path = Path(__file__).parent / "static" / "taskmanager.html"
    if ui_path.exists():
        return ui_path.read_text()
    
    return "<h1>Task Manager</h1><p>App not found</p>"


# App Management APIs
@app.get("/api/apps/status")
async def get_apps_status(authorization: str = None):
    """Get installed apps status."""
    verify_auth(authorization)
    return load_app_state()


@app.post("/api/apps/install")
async def install_app(app_id: str = Form(...), authorization: str = None):
    """Install an app by downloading from GitHub."""
    verify_auth(authorization)
    
    valid_apps = ["filemanager", "systeminfo", "taskmanager"]
    if app_id not in valid_apps:
        raise HTTPException(status_code=400, detail="Invalid app ID")
    
    state = load_app_state()
    if app_id in state["installed"]:
        return {"message": f"App {app_id} already installed"}
    
    try:
        # Download app files from GitHub
        download_app_from_github(app_id)
        
        # Mark as installed
        state["installed"].append(app_id)
        if not save_app_state(state):
            raise Exception("Failed to save app state")
        
        return {"message": f"App {app_id} installed successfully"}
    except Exception as e:
        logger.error(f"Failed to install app {app_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")


@app.post("/api/apps/uninstall")
async def uninstall_app(app_id: str = Form(...), authorization: str = None):
    """Uninstall an app by removing its files."""
    verify_auth(authorization)
    
    # Prevent uninstalling mandatory apps
    if app_id in ["systeminfo", "taskmanager"]:
        raise HTTPException(status_code=400, detail="Cannot uninstall core apps")
    
    state = load_app_state()
    if app_id not in state["installed"]:
        return {"message": f"App {app_id} not installed"}
    
    try:
        # Remove app directory
        for category in ["core", "optional"]:
            app_dir = APPS_DIR / category / app_id
            if app_dir.exists():
                shutil.rmtree(app_dir)
                logger.info(f"Removed app directory: {app_dir}")
                break
        
        # Update state
        state["installed"].remove(app_id)
        if not save_app_state(state):
            raise Exception("Failed to save app state")
        
        return {"message": f"App {app_id} uninstalled successfully"}
    except Exception as e:
        logger.error(f"Failed to uninstall app {app_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Uninstall failed: {str(e)}")


# System Info APIs
def collect_system_metrics():
    """Collect comprehensive system metrics."""
    import platform
    import os
    
    data = {}
    
    # ===== CPU =====
    cpu_percent_total = psutil.cpu_percent(interval=0.5)
    cpu_percent_per_core = psutil.cpu_percent(interval=0, percpu=True)
    cpu_freq = psutil.cpu_freq()
    cpu_times = psutil.cpu_times()
    cpu_stats = psutil.cpu_stats()
    
    data["cpu"] = {
        "percent_total": round(cpu_percent_total, 1),
        "percent_per_core": [round(c, 1) for c in cpu_percent_per_core] if cpu_percent_per_core else [],
        "count": psutil.cpu_count(),
        "freq_current": round(cpu_freq.current, 0) if cpu_freq else None,
        "freq_min": round(cpu_freq.min, 0) if cpu_freq and cpu_freq.min else None,
        "freq_max": round(cpu_freq.max, 0) if cpu_freq and cpu_freq.max else None,
        "times": {
            "user": round(cpu_times.user, 1),
            "system": round(cpu_times.system, 1),
            "idle": round(cpu_times.idle, 1),
            "iowait": round(cpu_times.iowait, 1) if hasattr(cpu_times, 'iowait') else None
        },
        "ctx_switches": cpu_stats.ctx_switches,
        "interrupts": cpu_stats.interrupts,
    }
    
    # Load averages (Linux)
    try:
        la = os.getloadavg()
        data["cpu"]["load_avg"] = {"1m": round(la[0], 2), "5m": round(la[1], 2), "15m": round(la[2], 2)}
    except Exception:
        data["cpu"]["load_avg"] = None
    
    # ===== MEMORY =====
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    data["memory"] = {
        "total": mem.total,
        "used": mem.used,
        "free": mem.free,
        "available": mem.available,
        "percent": round(mem.percent, 1),
        "cached": mem.cached if hasattr(mem, 'cached') else None,
        "buffers": mem.buffers if hasattr(mem, 'buffers') else None,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_free": swap.free,
        "swap_percent": round(swap.percent or 0, 1),
        "swap_in": swap.sin if hasattr(swap, 'sin') else None,
        "swap_out": swap.sout if hasattr(swap, 'sout') else None
    }
    
    # ===== DISK =====
    disk_root = psutil.disk_usage('/')
    disk_io = psutil.disk_io_counters()
    partitions = psutil.disk_partitions(all=False)
    
    data["disk"] = {
        "root": {
            "total": disk_root.total,
            "used": disk_root.used,
            "free": disk_root.free,
            "percent": round(disk_root.percent, 1)
        },
        "io": {
            "read_bytes": disk_io.read_bytes if disk_io else None,
            "write_bytes": disk_io.write_bytes if disk_io else None,
            "read_count": disk_io.read_count if disk_io else None,
            "write_count": disk_io.write_count if disk_io else None,
            "busy_time": disk_io.busy_time if disk_io and hasattr(disk_io, 'busy_time') else None
        },
        "partitions": [
            {
                "device": p.device,
                "mountpoint": p.mountpoint,
                "fstype": p.fstype,
                "opts": p.opts
            }
            for p in partitions
        ],
        "mounts": []
    }
    
    # USB mounts
    try:
        usb_root = Path("/media/usb")
        if usb_root.exists():
            for p in usb_root.iterdir():
                if p.is_dir():
                    try:
                        du = psutil.disk_usage(str(p))
                        data["disk"]["mounts"].append({
                            "path": str(p),
                            "total": du.total,
                            "used": du.used,
                            "free": du.free,
                            "percent": round(du.percent, 1)
                        })
                    except Exception:
                        pass
    except Exception:
        pass
    
    # ===== NETWORK =====
    net_io = psutil.net_io_counters(pernic=True)
    net_connections = len(psutil.net_connections(kind='inet'))
    
    data["network"] = {
        "interfaces": [],
        "active_connections": net_connections
    }
    
    for iface, stats in net_io.items():
        iface_data = {
            "name": iface,
            "bytes_sent": stats.bytes_sent,
            "bytes_recv": stats.bytes_recv,
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv,
            "errin": stats.errin,
            "errout": stats.errout,
            "dropin": stats.dropin,
            "dropout": stats.dropout
        }
        
        # Try to get IP addresses
        try:
            addrs = psutil.net_if_addrs().get(iface, [])
            iface_data["addresses"] = [
                {"family": str(addr.family), "address": addr.address}
                for addr in addrs
            ]
        except Exception:
            iface_data["addresses"] = []
        
        data["network"]["interfaces"].append(iface_data)
    
    # Wi-Fi info (if available)
    data["network"]["wifi"] = None
    try:
        iwconfig = subprocess.run(
            ["iwconfig"], capture_output=True, text=True, timeout=2
        )
        if iwconfig.returncode == 0 and "ESSID" in iwconfig.stdout:
            # Parse basic Wi-Fi info (simplified)
            data["network"]["wifi"] = {"raw": iwconfig.stdout[:500]}
    except Exception:
        pass
    
    # ===== PROCESSES =====
    processes = []
    zombie_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
        try:
            pinfo = proc.info
            if pinfo['status'] == psutil.STATUS_ZOMBIE:
                zombie_count += 1
            processes.append({
                "pid": pinfo['pid'],
                "name": pinfo['name'],
                "user": pinfo['username'],
                "cpu": round(pinfo['cpu_percent'] or 0, 1),
                "memory": round(pinfo['memory_percent'] or 0, 1),
                "status": pinfo['status']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Sort by CPU for top consumers
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    top_cpu = processes[:5]
    
    # Sort by memory for top consumers
    processes.sort(key=lambda x: x['memory'], reverse=True)
    top_mem = processes[:5]
    
    data["processes"] = {
        "total": len(processes),
        "zombie_count": zombie_count,
        "top_cpu": top_cpu,
        "top_memory": top_mem,
        "all": processes[:100]  # Limit to 100 for response size
    }
    
    # ===== HARDWARE (Raspberry Pi specific) =====
    data["hardware"] = {}
    
    # Temperature
    temp = None
    try:
        temp_result = subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2
        )
        if temp_result.returncode == 0:
            temp_str = temp_result.stdout.strip()
            temp = float(temp_str.split("=")[1].replace("'C", ""))
    except:
        try:
            if Path("/sys/class/thermal/thermal_zone0/temp").exists():
                temp_raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
                temp = float(temp_raw) / 1000.0
        except:
            pass
    
    data["hardware"]["temperature"] = round(temp, 1) if temp else None
    
    # GPU temperature (if available)
    try:
        gpu_temp_result = subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2
        )
        # Note: Raspberry Pi usually reports same for CPU/GPU
        data["hardware"]["gpu_temperature"] = data["hardware"]["temperature"]
    except:
        data["hardware"]["gpu_temperature"] = None
    
    # Throttling status
    throttled = None
    try:
        th = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2)
        if th.returncode == 0 and th.stdout:
            val_hex = th.stdout.strip().split("=")[-1]
            val = int(val_hex, 16)
            throttled = {
                "under_voltage": bool(val & (1 << 0)),
                "freq_capped": bool(val & (1 << 1)),
                "throttled": bool(val & (1 << 2)),
                "temp_limit": bool(val & (1 << 3)),
                "under_voltage_has_occurred": bool(val & (1 << 16)),
                "freq_capped_has_occurred": bool(val & (1 << 17)),
                "throttled_has_occurred": bool(val & (1 << 18)),
                "temp_limit_has_occurred": bool(val & (1 << 19)),
            }
    except Exception:
        throttled = None
    
    data["hardware"]["throttled"] = throttled
    
    # Model and SoC info
    try:
        model_file = Path("/proc/device-tree/model")
        data["hardware"]["model"] = model_file.read_text().strip().replace('\x00', '') if model_file.exists() else None
    except:
        data["hardware"]["model"] = None
    
    try:
        serial_file = Path("/proc/cpuinfo")
        if serial_file.exists():
            cpuinfo = serial_file.read_text()
            for line in cpuinfo.split('\n'):
                if 'Serial' in line:
                    data["hardware"]["serial"] = line.split(':')[-1].strip()
                if 'Revision' in line:
                    data["hardware"]["revision"] = line.split(':')[-1].strip()
    except:
        pass
    
    # ===== SYSTEM =====
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    
    data["system"] = {
        "uptime_seconds": uptime_seconds,
        "boot_time": int(boot_time),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "logged_in_users": [u.name for u in psutil.users()]
    }
    
    # USB devices
    data["system"]["usb_devices"] = []
    try:
        lsusb = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2)
        if lsusb.returncode == 0:
            data["system"]["usb_devices"] = lsusb.stdout.strip().split('\n')[:20]
    except:
        pass
    
    return data


@app.get("/api/system/info")
async def get_system_info(authorization: str = None):
    """Get comprehensive system information."""
    verify_auth(authorization)
    
    try:
        data = collect_system_metrics()
        
        # Store in history buffer for trends (simplified for graph)
        timestamp = time.time()
        with metrics_lock:
            metrics_history.append({
                "timestamp": timestamp,
                "cpu_percent": data["cpu"]["percent_total"],
                "memory_percent": data["memory"]["percent"],
                "temperature": data["hardware"]["temperature"]
            })
        
        return data
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/history")
async def get_system_history(authorization: str = None):
    """Get 30-minute trend history for CPU, Memory, Temperature."""
    verify_auth(authorization)
    
    with metrics_lock:
        history = list(metrics_history)
    
    return {
        "timestamps": [h["timestamp"] for h in history],
        "cpu_percent": [h["cpu_percent"] for h in history],
        "memory_percent": [h["memory_percent"] for h in history],
        "temperature": [h["temperature"] if h["temperature"] else 0 for h in history]
    }


# Task Manager APIs
@app.get("/api/tasks/list")
async def list_tasks(authorization: str = None):
    """List running processes."""
    verify_auth(authorization)
    
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.info
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "user": pinfo['username'],
                    "cpu": round(pinfo['cpu_percent'] or 0, 1),
                    "memory": round(pinfo['memory_percent'] or 0, 1),
                    "status": pinfo['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        
        return {"processes": processes[:100]}  # Limit to top 100
    except Exception as e:
        logger.error(f"Failed to list processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tasks/kill")
async def kill_task(pid: int = Form(...), authorization: str = None):
    """Kill a process by PID."""
    verify_auth(authorization)
    
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()
        proc.terminate()
        
        return {"message": f"Process {proc_name} (PID {pid}) terminated"}
    except psutil.NoSuchProcess:
        raise HTTPException(status_code=404, detail="Process not found")
    except psutil.AccessDenied:
        raise HTTPException(status_code=403, detail="Access denied")
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_app_config(authorization: str = None):
    """Get UI configuration."""
    verify_auth(authorization)
    config = get_config()
    return {
        "title": config.get("ui.title", "RSPI File Manager"),
        "refreshInterval": config.get("ui.refresh_interval_ms", 2000),
    }


@app.get("/api/browse")
async def browse(path: str = "", authorization: str = None):
    """List directory contents."""
    verify_auth(authorization)
    
    result = file_manager.list_directory(path)
    if result is None:
        raise HTTPException(status_code=404, detail="Path not found or not a directory")
    
    return result


@app.post("/api/upload")
async def upload(
    path: str = Form(""),
    file: UploadFile = File(...),
    authorization: str = None,
):
    """Upload a file to the specified path."""
    verify_auth(authorization)
    
    try:
        file_bytes = await file.read()
        success = file_manager.upload_file(path, file.filename, file_bytes)
        
        if not success:
            raise HTTPException(status_code=400, detail="Upload failed")
        
        return {"message": "File uploaded successfully", "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mkdir")
async def mkdir(path: str, name: str, authorization: str = None):
    """Create a new folder."""
    verify_auth(authorization)
    
    if not name:
        raise HTTPException(status_code=400, detail="Folder name is required")
    
    success = file_manager.create_folder(path, name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create folder")
    
    return {"message": "Folder created successfully"}


@app.post("/api/rename")
async def rename(path: str, new_name: str, authorization: str = None):
    """Rename a file or folder."""
    verify_auth(authorization)
    
    if not new_name:
        raise HTTPException(status_code=400, detail="New name is required")
    
    success = file_manager.rename_item(path, new_name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to rename")
    
    return {"message": "Item renamed successfully"}


@app.post("/api/delete")
async def delete(path: str, authorization: str = None):
    """Delete a file or folder."""
    verify_auth(authorization)
    
    success = file_manager.delete_item(path)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete")
    
    return {"message": "Item deleted successfully"}


@app.get("/api/download")
async def download(path: str, authorization: str = None):
    """Download a file."""
    verify_auth(authorization)
    
    file_path = file_manager.get_file_path(path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@app.post("/api/eject")
async def eject(path: str, authorization: str = None):
    """Eject/unmount a USB drive."""
    verify_auth(authorization)
    
    import subprocess
    from pathlib import Path
    
    # Get the full mount path
    base_path = Path(file_manager.validator.base_path)
    target_path = (base_path / path).resolve()
    
    # Verify it's within base_path
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Check if it's a mount point
    try:
        result = subprocess.run(
            ["mountpoint", "-q", str(target_path)],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail="Not a mount point")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout checking mount point")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="mountpoint command not found")
    
    # Unmount and cleanup via the helper script (pass mount path, not device)
    try:
        result = subprocess.run(
            ["/usr/local/bin/usb-mount.sh", "remove", str(target_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            logger.error(f"Failed to eject {target_path}: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Failed to eject drive: {error_msg}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout ejecting drive")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="usb-mount.sh helper script not found")

    return {"message": "Drive ejected successfully"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    host = config.get("server.host", "0.0.0.0")
    port = config.get("server.port", 8080)
    uvicorn.run(app, host=host, port=port)
