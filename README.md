# RSPI LocalServer

A lightweight, LAN-only file manager web app for Raspberry Pi 4B (1GB RAM, Wi-Fi) that lets home users browse, upload, download, create, rename, and delete files on USB storage via a simple, responsive web UI.

## Features

✅ **File Management**
- Browse directories and view file metadata (size, modified date)
- Upload files (single or batch folder upload)
- Download files
- Create folders
- Rename files and folders
- Delete files and folders (with confirmation)

✅ **Performance & Security**
- Lightweight: ~50–120 MB RAM usage
- Path-safe filesystem access (prevents directory traversal attacks)
- Optional HTTP Basic Auth
- LAN-only access (no internet exposure by default)
- Runs as unprivileged `rspi` user via systemd
- Gunicorn + UvicornWorker for stability

✅ **Dynamic Storage**
- Auto-detects USB drives mounted under `/media/usb/<label>`
- No restart needed when drives are plugged/unplugged
- Works with multiple drives

✅ **Easy Deployment**
- Single `install.sh` script on Raspberry Pi OS Lite
- YAML configuration
- Systemd service integration
- `update.sh` and `uninstall.sh` for lifecycle management
- Simple, responsive HTML/CSS/JS UI

## System Requirements

- **Hardware:** Raspberry Pi 4B (1 GB RAM minimum; 2+ GB recommended for comfort)
- **OS:** Raspberry Pi OS Lite (Bullseye or later, 32-bit or 64-bit)
- **Network:** Ethernet or Wi-Fi on the same LAN
- **Storage:** USB drive(s) with ext4, NTFS, exFAT, or FAT32 filesystem

## Installation

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3 and dependencies
sudo apt install -y python3 python3-venv python3-pip

# Install filesystem drivers (optional, for NTFS/exFAT)
sudo apt install -y ntfs-3g exfat-fuse
```

### 2. Mount USB Drives (Optional: Auto-Mount)

To auto-mount USB drives when plugged in:

```bash
# Create mount point
sudo mkdir -p /media/usb
sudo chmod 755 /media/usb

# Install auto-mount tool (systemd-mount handles this)
# Already available in Raspberry Pi OS Lite

# Create udev rule for auto-mounting
sudo bash -c 'cat > /etc/udev/rules.d/99-automount.rules << '"'"'EOF'"'"'
ACTION=="add", SUBSYSTEMS=="usb", KERNEL=="sd*[0-9]", ENV{ID_FS_USAGE}=="filesystem", \
  RUN+="/bin/mkdir -p /media/usb/%E{ID_FS_LABEL_ENC}", \
  RUN+="/bin/mount -o uid=1000,gid=1000 /dev/%k /media/usb/%E{ID_FS_LABEL_ENC}"
ACTION=="remove", SUBSYSTEMS=="usb", KERNEL=="sd*[0-9]", ENV{ID_FS_USAGE}=="filesystem", \
  RUN+="/bin/umount /media/usb/%E{ID_FS_LABEL_ENC}"
EOF'

# Reload udev rules
sudo udevadm control --reload
sudo udevadm trigger
```

Or manually mount:

```bash
# Identify drive
lsblk

# Mount (example: /dev/sda1)
sudo mkdir -p /media/usb/mydrive
sudo mount /dev/sda1 /media/usb/mydrive
sudo chown -R pi:pi /media/usb/mydrive
```

### 3. Install RSPI LocalServer

```bash
# Clone or download the project
cd ~/RSPI_LocalServer

# Run installer (as root)
sudo bash install.sh
```

The installer will:
- Create the `rspi` application user
- Install Python dependencies in a virtual environment at `/opt/rspi-localserver`
- Create the systemd service
- Create log directory at `/var/log/rspi-localserver`
- Start the service on port `8080`

### 4. Access the UI

From any device on the same LAN:

```
http://<pi-ip>:8080
```

Find your Pi's IP:
```bash
hostname -I
```

## Configuration

Edit `/etc/rspi-localserver/config.yaml`:

```yaml
server:
  host: "0.0.0.0"           # Listen on all interfaces (LAN-only)
  port: 8080                # Web UI port
  workers: 1                # Keep at 1 for 1GB RAM
  timeout: 30               # Request timeout (seconds)

storage:
  base_path: "/media/usb"   # Root directory for browsing
  max_upload_mb: 500        # Max file upload size
  max_files_per_dir: 5000   # Safety limit for large dirs
  allowed_extensions: []    # Empty = allow all; e.g., ["jpg", "mp4", "pdf"]

auth:
  enabled: false            # Enable HTTP Basic Auth
  username: "admin"
  password: "admin123"      # Change if enabled!

ui:
  title: "RSPI File Manager"
  refresh_interval_ms: 2000
```

After editing, restart:
```bash
sudo systemctl restart rspi-localserver
```

## Service Management

```bash
# Check status
sudo systemctl status rspi-localserver

# Restart
sudo systemctl restart rspi-localserver

# Stop
sudo systemctl stop rspi-localserver

# View logs
sudo tail -f /var/log/rspi-localserver/error.log
sudo journalctl -u rspi-localserver -f
```

## Update

```bash
cd ~/RSPI_LocalServer
sudo bash update.sh
```

Creates a dated backup, updates code, and restarts the service.

## Uninstall

```bash
sudo bash uninstall.sh
```

Keeps config and logs for reference; optionally remove them manually.

## Security Notes

### LAN-Only Access
- The app binds to `0.0.0.0:8080` but is **only accessible from the same Wi-Fi/Ethernet network**.
- **Do not expose this to the internet** unless you add:
  - HTTPS/TLS (use Caddy reverse proxy)
  - Strong authentication
  - IP whitelisting / VPN

### Optional Basic Auth
- Enable in `config.yaml` for simple password protection
- Not suitable for public internet exposure; use a reverse proxy + OAuth for that

### File Permissions
- App runs as unprivileged `rspi` user
- Can only access files under `/media/usb` and `/opt/rspi-localserver`
- Directory traversal attacks are prevented by path validation

### Uploads
- Set `allowed_extensions` if you only want specific file types
- Configure `max_upload_mb` to prevent filling the drive

## Performance

### RAM Usage
- Baseline: ~50–80 MB (Gunicorn + FastAPI + UI)
- Per request: ~20–50 MB (file uploads, directory listing)
- Peak with large files: ~100–150 MB

**Monitor:**
```bash
watch -n 1 'ps aux | grep gunicorn'
```

### CPU Usage
- Minimal at idle
- Single-threaded (1 worker) is sufficient for home use
- Concurrent requests queued automatically

### Disk I/O
- Optimized for USB 2.0/3.0 speeds (10–400 MB/s depending on drive)
- Directory listing is cached in-memory per request (not persistent)

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u rspi-localserver -n 50

# Check if port is in use
sudo lsof -i :8080

# Verify Python venv
source /opt/rspi-localserver/venv/bin/activate
python3 -c "import fastapi; print(fastapi.__version__)"
```

### Can't Access Web UI

```bash
# Check if service is running
sudo systemctl is-active rspi-localserver

# Check firewall
sudo iptables -L -n | grep 8080

# Test locally
curl http://localhost:8080

# Find Pi's IP
hostname -I
```

### USB Drive Not Showing Up

```bash
# Check mount
mount | grep /media/usb

# Manual mount
lsblk
sudo mkdir -p /media/usb/mydrive
sudo mount /dev/sdX1 /media/usb/mydrive
sudo chown -R 1000:1000 /media/usb/mydrive  # rspi user
```

### Uploads Slow or Failing

- Check USB drive speed: `dd if=/dev/zero of=/mnt/test.img bs=1M count=100`
- Reduce `max_upload_mb` in config
- Restart service: `sudo systemctl restart rspi-localserver`

## Project Structure

```
RSPI_LocalServer/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration loader
│   ├── file_manager.py   # File operations + path safety
│   └── static/
│       └── index.html    # Web UI (HTML/CSS/JS)
├── config/
│   └── config.yaml       # Default configuration
├── scripts/
│   └── (systemd service files - generated by install.sh)
├── requirements.txt      # Python dependencies
├── install.sh           # Installation script
├── update.sh            # Update script
├── uninstall.sh         # Uninstall script
└── README.md            # This file
```

## API Endpoints

All endpoints require optional HTTP Basic Auth (if enabled) and are LAN-only.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve web UI |
| GET | `/api/config` | Get UI config |
| GET | `/api/browse?path=<path>` | List directory |
| POST | `/api/upload` | Upload file |
| POST | `/api/mkdir` | Create folder |
| POST | `/api/rename` | Rename item |
| POST | `/api/delete` | Delete item |
| GET | `/api/download?path=<path>` | Download file |
| GET | `/health` | Health check |

## Development

### Local Testing (on Pi or laptop)

```bash
# Create venv
python3 -m venv venv
source venv/bin/activate

# Install deps
pip install -r requirements.txt

# Run dev server
python3 app/main.py
# Access: http://localhost:8080
```

### Run with Gunicorn (like production)

```bash
source venv/bin/activate
gunicorn --bind 0.0.0.0:8080 --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  app.main:app
```

## License

MIT License – freely use, modify, and distribute.

## Contributing

Suggestions and PRs welcome! Focus areas:
- Mobile UI improvements
- Drag-and-drop upload
- Search/filter
- File preview (images, text)
- Bandwidth throttling for large files
- Multi-user support (per-folder auth)

## FAQ

**Q: Can I expose this to the internet?**
A: Not recommended without HTTPS, strong auth, and a reverse proxy. Use a VPN for remote access.

**Q: What if my Pi has only 512 MB RAM?**
A: It may struggle. Consider reducing workers (already at 1) or using a lighter alternative like Samba.

**Q: Can I change the port?**
A: Yes, edit `config.yaml` and set `server.port`. Restart: `sudo systemctl restart rspi-localserver`.

**Q: Can I use a different storage path?**
A: Yes, change `storage.base_path` in `config.yaml`. Ensure permissions allow the `rspi` user to read/write.

**Q: How do I backup files?**
A: Use standard Linux tools or Mount the USB drive on a laptop. App provides no backup functionality.

---

**Created for home users who want simple, lightweight file management on a Raspberry Pi.**

For help, check logs: `sudo journalctl -u rspi-localserver -f`
