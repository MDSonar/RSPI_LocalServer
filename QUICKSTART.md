# RSPI LocalServer – Quick Start Guide

## 30-Second Installation

```bash
# Clone/download this project, then:
cd RSPI_LocalServer

# Run the installer (handles Python setup automatically)
sudo bash install.sh

# Access at: http://<your-pi-ip>:8080
```

## What Gets Installed

- ✅ Python FastAPI web server on port `8080`
- ✅ Systemd service `rspi-localserver` (auto-start on boot)
- ✅ Virtual environment in `/opt/rspi-localserver`
- ✅ Config at `/etc/rspi-localserver/config.yaml`
- ✅ Logs at `/var/log/rspi-localserver/`

## Basic Commands

```bash
# Check status
sudo systemctl status rspi-localserver

# View logs
sudo tail -f /var/log/rspi-localserver/error.log

# Restart
sudo systemctl restart rspi-localserver

# Stop
sudo systemctl stop rspi-localserver

# Update
cd RSPI_LocalServer && sudo bash update.sh

# Uninstall
sudo bash uninstall.sh
```

## Setup USB Drive (Manual)

```bash
# Identify your drive
lsblk

# Mount it (example: /dev/sda1)
sudo mkdir -p /media/usb/mydrive
sudo mount /dev/sda1 /media/usb/mydrive
sudo chown -R pi:pi /media/usb/mydrive

# Now it's visible in the web UI!
```

## Enable Basic Auth (Optional)
## What Happens Automatically

The installer automatically sets up:
- 🔄 System package updates
- 🐍 Python 3, venv, and pip
- 🔌 **USB auto-mount** (plug in a drive → it appears automatically)
- 🐧 Systemd service (starts on boot)
- ⚡ Web server on port 8080

**No manual USB mounting needed!**

## Enable Basic Auth (Optional)

Edit `/etc/rspi-localserver/config.yaml`:

```yaml
auth:
  enabled: true
  username: "admin"
  password: "mypassword123"  # Change this!
```

Then restart:
```bash
sudo systemctl restart rspi-localserver
```

## Firewall (if needed)

```bash
# Allow port 8080 (example with ufw)
sudo ufw allow 8080/tcp
sudo ufw enable
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't access UI | Check Pi IP: `hostname -I`; ensure on same network |
| Service won't start | Check logs: `sudo journalctl -u rspi-localserver` |
| Slow uploads | Check USB drive; reduce `max_upload_mb` in config |
| Drive not appearing | Plug in USB drive; restart service if needed: `sudo systemctl restart rspi-localserver` |

## Next Steps

- Read [README.md](README.md) for full documentation
- Customize config at `/etc/rspi-localserver/config.yaml`
- Access from phone/laptop on your Wi-Fi: `http://<pi-ip>:8080`

---

**That's it!** Simple file manager for your home network. 🚀
