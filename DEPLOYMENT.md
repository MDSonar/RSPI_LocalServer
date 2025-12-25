# RSPI LocalServer – Deployment Checklist

Use this guide to deploy on your Raspberry Pi 4B.

## Pre-Deployment

- [ ] Raspberry Pi 4B with 1GB+ RAM
- [ ] Fresh Raspberry Pi OS Lite (Bullseye or later)
- [ ] Network access (Ethernet or Wi-Fi)
- [ ] USB drive(s) for file storage
- [ ] SSH access to Pi or physical keyboard/monitor

## Step-by-Step Deployment

### 1. Prepare Raspberry Pi OS

```bash
# SSH into your Pi
ssh pi@<pi-ip>

# The install.sh script will automatically:
# - Update system packages
# - Install Python 3, venv, and pip
# - Set up the application

# (Optional) Pre-install filesystem drivers for NTFS/exFAT support:
sudo apt install -y ntfs-3g exfat-fuse

# (Optional) Install Samba if you want Windows-style shares too
sudo apt install -y samba
```

- [ ] SSH access to Raspberry Pi confirmed

### 2. Prepare USB Storage

#### Option A: Auto-Mount (Recommended)

```bash
# Create mount point
sudo mkdir -p /media/usb
sudo chmod 755 /media/usb

# Create udev rule for automatic mounting when drive is plugged in
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

# Test: Plug in a USB drive; it should appear at /media/usb/<label>
mount | grep /media/usb
```

- [ ] Auto-mount rule created and tested

#### Option B: Manual Mount

```bash
# List block devices to find your USB drive
lsblk

# Assuming /dev/sda1 is your USB drive
sudo mkdir -p /media/usb/mydrive
sudo mount /dev/sda1 /media/usb/mydrive
sudo chown -R pi:pi /media/usb/mydrive

# To make permanent, add to /etc/fstab:
# UUID=<your-uuid> /media/usb/mydrive auto defaults,uid=1000,gid=1000 0 0
# (get UUID with: sudo blkid /dev/sda1)
```

- [ ] USB drive mounted and accessible

### 3. Install RSPI LocalServer

```bash
# Download or clone the project to your Pi
# (Example: download as ZIP, extract, or git clone)
cd ~/RSPI_LocalServer

# Run installation
sudo bash install.sh

# This will automatically:
# - Update system packages
# - Install Python 3, venv, and pip
# - Create 'rspi' application user
# - Install Python venv at /opt/rspi-localserver
# - Create systemd service
# - Start the service automatically
```

Monitor the installation output. You should see:
```
✅ Installation successful!
📍 Service: rspi-localserver
📂 App directory: /opt/rspi-localserver
⚙️  Config: /etc/rspi-localserver/config.yaml
📋 Logs: /var/log/rspi-localserver/
```

- [ ] Installation script completed without errors
- [ ] Service is running: `sudo systemctl status rspi-localserver`

### 4. Verify Installation

```bash
# Check service status
sudo systemctl status rspi-localserver
# Should show: Active (running)

# Check service is listening
sudo lsof -i :8080
# Should show gunicorn listening on port 8080

# Find your Pi's IP
hostname -I
# Example output: 192.168.1.100

# Test from another device on your network
curl http://<pi-ip>:8080
# Should return HTML (the web UI)
```

- [ ] Service running
- [ ] Port 8080 is open and listening
- [ ] Can access UI from another device on the network

### 5. Access the Web UI

From any device on your Wi-Fi/Ethernet network:

```
http://<your-pi-ip>:8080
```

Example: `http://192.168.1.100:8080`

You should see:
- 🏠 Root directory of `/media/usb`
- 📁 List of USB drives/folders
- 📤 Upload buttons
- ➕ New Folder button
- 🔄 Refresh button

- [ ] Web UI loads and displays files

### 6. Test Core Features

- [ ] **Browse:** Click folders to navigate
- [ ] **Upload:** Click "Upload File" and select a small test file
- [ ] **Download:** Download the uploaded file to verify
- [ ] **Create Folder:** Click "New Folder", enter a name, create it
- [ ] **Rename:** Right-click or use Rename button on a test folder/file
- [ ] **Delete:** Delete the test folder with confirmation

### 7. (Optional) Enable Basic Auth

Edit the config:

```bash
sudo nano /etc/rspi-localserver/config.yaml
```

Change:
```yaml
auth:
  enabled: true
  username: "admin"
  password: "mycustompassword123"
```

Save (Ctrl+X, Y, Enter) and restart:

```bash
sudo systemctl restart rspi-localserver
```

Test by accessing the UI again. You should be prompted for username/password.

- [ ] Basic auth enabled and working (if desired)

### 8. (Optional) Set Up Firewall

If you have UFW enabled:

```bash
# Allow port 8080
sudo ufw allow 8080/tcp
sudo ufw enable

# Check
sudo ufw status
# Should show 8080/tcp as ALLOW
```

- [ ] Firewall configured (if applicable)

### 9. Monitor & Logs

```bash
# View real-time logs
sudo journalctl -u rspi-localserver -f

# Or check error log
sudo tail -f /var/log/rspi-localserver/error.log

# Check RAM usage
ps aux | grep gunicorn
# Look for the "RES" column (resident memory)
```

- [ ] Logs viewable and no errors
- [ ] RAM usage is reasonable (< 200 MB)

### 10. Configure Boot & Persistence

The systemd service is already configured to:
- Start automatically on boot: `sudo systemctl enable rspi-localserver`
- Restart on failure
- Run as unprivileged `rspi` user

Test it:

```bash
# Reboot and verify it starts automatically
sudo reboot

# After reboot, check status
sudo systemctl status rspi-localserver
```

- [ ] Service starts automatically on boot

## Post-Deployment

### Regular Maintenance

```bash
# Update the system periodically
sudo apt update && sudo apt upgrade -y

# Check logs for errors
sudo journalctl -u rspi-localserver --since "1 day ago" | grep -i error

# Monitor disk usage on USB drives
df -h /media/usb

# Check RAM usage
free -h
```

### Updating RSPI LocalServer

When a new version is available:

```bash
cd ~/RSPI_LocalServer
git pull origin main  # or download the new version
sudo bash update.sh
```

This will:
- Create a dated backup
- Update the code
- Update dependencies
- Restart the service

### Backup Important Files

```bash
# Backup config (in case you customize it)
sudo cp /etc/rspi-localserver/config.yaml ~/config.yaml.bak

# Backup USB data regularly to another device
# (Use rsync, scp, or manually copy to a laptop)
```

## Troubleshooting

### UI Won't Load

```bash
# Check if service is running
sudo systemctl is-active rspi-localserver

# Check logs
sudo journalctl -u rspi-localserver -n 50

# Restart service
sudo systemctl restart rspi-localserver

# Test locally on Pi
curl http://localhost:8080
```

### Can't Find Pi's IP

```bash
# Find all devices on your network
hostname -I            # On the Pi itself
arp-scan -l            # On another Linux device
nmap -sn 192.168.1.0/24  # Scan your network
# Or check your router's admin panel for connected devices
```

### USB Drive Not Showing

```bash
# List all mounts
mount | grep /media

# Identify drive
lsblk

# Manually mount if needed
sudo mkdir -p /media/usb/mydrive
sudo mount /dev/sdX1 /media/usb/mydrive

# Check permissions
ls -la /media/usb
# Should be readable by everyone
```

### Slow Performance

```bash
# Check if Pi is CPU-throttled due to heat
vcgencmd measure_temp

# Monitor real-time resource usage
top

# Check disk I/O (USB drive might be slow)
iostat -x 1

# Reduce workers if needed (already at 1, which is minimal)
```

### Service Crashes or Restarts Often

```bash
# Check error log
sudo tail -f /var/log/rspi-localserver/error.log

# Check if port 8080 is in use
sudo lsof -i :8080

# Check if /media/usb has permission issues
ls -la /media/usb
```

## Security Checklist

- [ ] Pi password changed from default: `passwd`
- [ ] SSH key-based auth set up (optional but recommended)
- [ ] Basic auth enabled in config (recommended)
- [ ] Firewall restricts access to port 8080 (optional)
- [ ] Service runs as unprivileged `rspi` user (done automatically)
- [ ] App only accessible from local LAN (not exposed to internet)
- [ ] USB drives mounted with appropriate permissions

## Performance Expectations

| Metric | Typical Value |
|--------|---------------|
| RAM at idle | 50–80 MB |
| RAM with 1 user browsing | 80–120 MB |
| RAM peak (large file upload) | 100–150 MB |
| CPU usage at idle | <1% |
| Directory listing time (100 files) | <200 ms |
| File upload speed | Limited by USB drive speed |
| File download speed | Limited by USB drive & network |

## Final Notes

- 🌐 **Network:** App is LAN-only by design. Do not expose to the internet without HTTPS, strong auth, and a reverse proxy.
- 📦 **Minimal dependencies:** Uses only FastAPI, Gunicorn, and standard library—no heavy frameworks.
- 🔒 **Security:** Path traversal attacks prevented; file access isolated to `/media/usb`.
- 💾 **Storage:** No database; all config is YAML; no state is persisted.
- 🔄 **Easy maintenance:** `install.sh`, `update.sh`, `uninstall.sh` handle everything.

---

**Deployment complete!** Your Raspberry Pi is now a lightweight file server for your home network. 🎉

For help, see [README.md](README.md) or check logs:
```bash
sudo journalctl -u rspi-localserver -f
```
