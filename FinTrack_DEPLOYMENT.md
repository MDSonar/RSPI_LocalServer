# FinTrack Deployment Guide for Raspberry Pi

**Step-by-step guide to deploy FinTrack on Raspberry Pi 4B (1GB RAM).**

---

## Prerequisites

- Raspberry Pi 4B with 1GB+ RAM
- Raspberry Pi OS (32-bit or 64-bit)
- microSD card (32GB minimum recommended)
- Network connectivity (LAN)
- Optional: USB drive for archive storage

---

## Step 1: Prepare System (5 minutes)

### SSH into Pi
```bash
ssh pi@raspberrypi.local
# Or: ssh pi@<your-pi-ip>
# Default password: raspberry
```

### Update packages
```bash
sudo apt update
sudo apt upgrade -y
```

### Install Python 3.9+
```bash
python3 --version
# Should be 3.9 or later. If not:
sudo apt install python3-dev python3-venv -y
```

### Install system dependencies
```bash
# For PyMuPDF (PDF parsing)
sudo apt install libfitz-dev -y

# For pytesseract (OCR, if using scanned PDFs)
sudo apt install tesseract-ocr libtesseract-dev -y

# For pdf2image
sudo apt install libpoppler-dev libpoppler-cpp-dev -y
```

---

## Step 2: Clone/Transfer FinTrack Code (10 minutes)

### Option A: Git clone (preferred)
```bash
cd ~
git clone https://github.com/<your-username>/FinTrack.git
cd FinTrack
```

### Option B: SCP from desktop
```bash
# On desktop:
scp -r /path/to/FinTrack pi@raspberrypi.local:~/
# Then SSH in and:
cd ~/FinTrack
```

### Verify structure
```bash
ls -la
# Should see: fintrack/, requirements.txt, README.md, etc.
```

---

## Step 3: Setup Python Virtual Environment (5 minutes)

```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# Verify
python --version  # Should show 3.9+
```

---

## Step 4: Install Dependencies (10-15 minutes)

### Install Python packages
```bash
pip install --upgrade pip setuptools wheel

# Install requirements
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed fastapi-0.104.1 uvicorn-0.24.0 sqlalchemy-2.0.23 ...
```

### Test imports
```bash
python3 -c "import fastapi; import sqlalchemy; import fitz; print('✓ All imports OK')"
```

---

## Step 5: Test Locally (5 minutes)

### Run development server
```bash
python3 -m uvicorn fintrack.main:app --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Started server process [1234]
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Test from another machine
```bash
# On desktop:
curl http://<pi-ip>:8000/
# Should return HTML (dashboard)
```

### Upload test PDF
```bash
curl -X POST http://<pi-ip>:8000/api/finance/upload \
  -F "file=@test_statement.pdf"
```

### Stop server
```bash
Ctrl+C
```

---

## Step 6: Setup Systemd Service (5 minutes)

### Create service file
```bash
sudo nano /etc/systemd/system/fintrack.service
```

### Paste this (adjust user/paths if needed):
```ini
[Unit]
Description=FinTrack Personal Finance Tracker
After=network.target

[Service]
Type=notify
User=pi
WorkingDirectory=/home/pi/FinTrack
Environment="PATH=/home/pi/FinTrack/venv/bin"
ExecStart=/home/pi/FinTrack/venv/bin/gunicorn \
  -w 1 \
  --threads 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  fintrack.main:app \
  --bind 0.0.0.0:8000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Save and exit
```
Ctrl+X → Y → Enter
```

### Enable and start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable fintrack
sudo systemctl start fintrack
```

### Verify it's running
```bash
sudo systemctl status fintrack
# Should show: "active (running)"
```

### View logs (real-time)
```bash
sudo journalctl -u fintrack -f
# Press Ctrl+C to exit
```

---

## Step 7: Configure Storage (Optional but Recommended)

### Check available storage
```bash
df -h
# Should show /home or main partition with >1GB free
```

### If using external USB drive:

```bash
# List drives
lsblk
# Example: sda1 is your USB drive

# Create mount point
mkdir -p /mnt/usb

# Mount (adjust device name)
sudo mount /dev/sda1 /mnt/usb

# Check ownership
ls -la /mnt/usb

# Make writable by pi user
sudo chown pi:pi /mnt/usb

# Update config.yaml (optional)
nano config.yaml
# Change storage.csv_export to /mnt/usb/csv_export
```

### Auto-mount on boot (optional)
```bash
sudo blkid
# Note the UUID of your USB drive

sudo nano /etc/fstab
# Add line: UUID=<your-uuid> /mnt/usb ext4 defaults,auto 0 0

# Test
sudo systemctl daemon-reload
```

---

## Step 8: Verify Deployment (10 minutes)

### Check service status
```bash
sudo systemctl status fintrack
```

### Check database created
```bash
ls -lah storage/fintrack.db
# Should exist and be >100 bytes
```

### Test API endpoints
```bash
# Get empty statements list
curl http://localhost:8000/api/finance/statements
# Response: {"statements": []}

# Get summary
curl http://localhost:8000/api/finance/analytics/summary
# Response: {"total_income": 0, "total_expenses": 0, ...}
```

### Open dashboard
```bash
# From desktop browser:
# http://<pi-ip>:8000/
# Should show upload zone + empty stats
```

### Upload test PDF
Upload a sample SBI/HDFC/AMEX statement via dashboard.  
Verify it appears in recent statements + transactions load.

---

## Step 9: Post-Deployment Configuration (5 minutes)

### Create config.yaml (optional)
```bash
mkdir -p fintrack/config
nano fintrack/config/config.yaml
```

### Example config
```yaml
storage:
  db_path: "storage/fintrack.db"
  pdf_archive: "storage/pdf_archive/"
  csv_export: "storage/csv_export/"

parsing:
  max_upload_mb: 10
  ocr_enabled: true
  ocr_engine: "pytesseract"

archival:
  min_age_days: 180
  auto_archive: false  # Set to true if you add systemd timer

logging:
  level: "INFO"
```

### Restart service to apply config
```bash
sudo systemctl restart fintrack
```

---

## Step 10: Setup Auto-Archival (Optional)

### Create systemd timer
```bash
sudo nano /etc/systemd/system/fintrack-archive.timer
```

### Paste this (runs 1st of each month at 2 AM):
```ini
[Unit]
Description=FinTrack Monthly Archival Timer
Requires=fintrack-archive.service

[Timer]
OnCalendar=*-*-01 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Create service
```bash
sudo nano /etc/systemd/system/fintrack-archive.service
```

### Paste this:
```ini
[Unit]
Description=FinTrack Archive Old Transactions
After=fintrack.service

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/FinTrack
Environment="PATH=/home/pi/FinTrack/venv/bin"
ExecStart=/usr/bin/curl -X POST http://localhost:8000/api/finance/archive?days_old=180
StandardOutput=journal
StandardError=journal
```

### Enable timer
```bash
sudo systemctl daemon-reload
sudo systemctl enable fintrack-archive.timer
sudo systemctl start fintrack-archive.timer
```

### Check timer status
```bash
sudo systemctl list-timers fintrack-archive.timer
```

---

## Maintenance

### View logs
```bash
# Latest 100 lines
sudo journalctl -u fintrack -n 100

# Last 1 hour
sudo journalctl -u fintrack --since "1 hour ago"

# Real-time
sudo journalctl -u fintrack -f
```

### Restart service
```bash
sudo systemctl restart fintrack
```

### Stop service
```bash
sudo systemctl stop fintrack
```

### Disable service (won't start on boot)
```bash
sudo systemctl disable fintrack
```

### Upgrade code (pull latest)
```bash
cd ~/FinTrack
git pull origin main
sudo systemctl restart fintrack
```

### Update Python dependencies
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart fintrack
```

---

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u fintrack -n 50 --no-pager

# Common issues:
# - Port 8000 already in use → change port in service file
# - Database locked → check if another instance running
# - Import error → reinstall venv: rm -rf venv && python3 -m venv venv
```

### PDF parsing fails
```bash
# Enable OCR if not already
sudo apt install tesseract-ocr -y

# Update config.yaml
ocr_enabled: true
```

### Running out of disk space
```bash
# Check storage
df -h

# Archive old PDFs
sudo journalctl --vacuum=30d

# Clean pip cache
pip cache purge

# Delete old CSV exports (keep last 3 months)
ls -lart storage/csv_export/
rm storage/csv_export/old_*.csv
```

### Slow performance
```bash
# Check system load
uptime

# Monitor processes
top
# Press q to exit

# If CPU high: disable OCR in config
# If memory high: ensure only 1 gunicorn worker (--workers 1)
```

---

## Monitoring

### Watch service auto-restart on failure
```bash
sudo journalctl -u fintrack -f
# If service crashes, it auto-restarts after 10 seconds (RestartSec=10)
```

### Monthly storage check
```bash
# Schedule a cron job to alert on low disk space
crontab -e
# Add: 0 0 * * * df -h | mail -s "Disk usage" pi@localhost
```

### Database integrity check
```bash
sqlite3 storage/fintrack.db "PRAGMA integrity_check;"
# Should return: ok
```

---

## Backup & Restore

### Backup database
```bash
# Manual backup
cp storage/fintrack.db storage/fintrack.db.backup

# Or daily backup via cron
crontab -e
# Add: 0 3 * * * cp ~/FinTrack/storage/fintrack.db ~/FinTrack/storage/fintrack.db.$(date +\%Y\%m\%d)
```

### Restore from backup
```bash
cp storage/fintrack.db.backup storage/fintrack.db
sudo systemctl restart fintrack
```

### Backup to USB drive
```bash
# Monthly backup to USB
sudo cp -r ~/FinTrack/storage /mnt/usb/fintrack_backup_$(date +%Y%m%d)
```

---

## Performance Tuning (Optional)

### If slow on 1GB RAM:

**Option 1: Reduce threads**
```ini
# In /etc/systemd/system/fintrack.service:
ExecStart=/... gunicorn -w 1 --threads 2 ...  # Reduce from 4 to 2
```

**Option 2: Disable OCR**
```yaml
# In config.yaml:
parsing:
  ocr_enabled: false
```

**Option 3: Increase DB cache**
```python
# In fintrack/db/database.py:
engine = create_engine(
    "sqlite:///./storage/fintrack.db",
    connect_args={"timeout": 10},
    pool_size=5,
    max_overflow=10,
)
```

---

## Uninstall

### Stop and disable service
```bash
sudo systemctl stop fintrack
sudo systemctl disable fintrack
sudo rm /etc/systemd/system/fintrack.service
sudo systemctl daemon-reload
```

### Remove files
```bash
rm -rf ~/FinTrack
# Or keep storage: rm -rf ~/FinTrack/{fintrack,venv,requirements.txt}
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start | `sudo systemctl start fintrack` |
| Stop | `sudo systemctl stop fintrack` |
| Restart | `sudo systemctl restart fintrack` |
| Status | `sudo systemctl status fintrack` |
| Logs (live) | `sudo journalctl -u fintrack -f` |
| Logs (last 100) | `sudo journalctl -u fintrack -n 100` |
| Enable on boot | `sudo systemctl enable fintrack` |
| Disable on boot | `sudo systemctl disable fintrack` |

---

## Next Steps After Deployment

1. **Upload real bank statements** (SBI, HDFC, AMEX)
2. **Verify transaction extraction** – count matches manual count
3. **Test lineage detection** – check if CC payments are linked
4. **Schedule monthly archival** – set auto-archival timer (Step 10)
5. **Setup backup** – copy DB to USB monthly
6. **Monitor logs** – check for parsing errors: `sudo journalctl -u fintrack -f`
7. **Invite family** – share dashboard URL if multi-user desired

---

## Support

- **README.md** – Complete documentation
- **copilot-instructions.md** – Developer patterns
- **API /docs** – Auto-generated Swagger: `http://<pi-ip>:8000/docs`
- **Logs** – `sudo journalctl -u fintrack`

---

**Status: ✅ DEPLOYMENT-READY**

Typical deployment time: 30-45 minutes (including system updates).
