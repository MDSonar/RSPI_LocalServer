import base64
import logging
import json
import subprocess
import psutil
import urllib.request
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from .config import get_config
from .file_manager import FileManager

logger = logging.getLogger(__name__)

app = FastAPI(title="RSPI LocalServer", version="2.0.0")

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
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
    except:
        pass
    
    return None

def download_app_from_github(app_id):
    """Download app files from GitHub."""
    manifest = get_app_manifest(app_id)
    if not manifest:
        raise Exception("App manifest not found")
    
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
    
    for category in ["core", "optional"]:
        ui_path = APPS_DIR / category / "systeminfo" / "systeminfo.html"
        if ui_path.exists():
            return ui_path.read_text()
    
    ui_path = Path(__file__).parent / "static" / "systeminfo.html"
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
@app.get("/api/system/info")
async def get_system_info(authorization: str = None):
    """Get system information."""
    verify_auth(authorization)
    
    try:
        # CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        # Memory info
        mem = psutil.virtual_memory()
        
        # Disk info
        disk = psutil.disk_usage('/')
        
        # Temperature (try multiple sources)
        temp = None
        try:
            temp_result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True,
                text=True,
                timeout=2
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
        
        # System info
        import platform
        try:
            model_file = Path("/proc/device-tree/model")
            model = model_file.read_text().strip().replace('\x00', '') if model_file.exists() else platform.machine()
        except:
            model = platform.machine()
        
        # Uptime
        boot_time = psutil.boot_time()
        import time
        uptime_seconds = int(time.time() - boot_time)
        
        return {
            "cpu": {
                "percent": round(cpu_percent, 1),
                "count": cpu_count,
                "freq": round(cpu_freq.current, 0) if cpu_freq else None
            },
            "memory": {
                "total": mem.total,
                "used": mem.used,
                "percent": round(mem.percent, 1)
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "percent": round(disk.percent, 1)
            },
            "temperature": round(temp, 1) if temp else None,
            "model": model,
            "uptime_seconds": uptime_seconds,
            "platform": platform.system()
        }
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
