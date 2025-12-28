#!/bin/bash
set -e

# RSPI LocalServer Installation Script
# Run: sudo bash install.sh

APP_NAME="rspi-localserver"
APP_USER="rspi"
APP_GROUP="rspi"
APP_HOME="/opt/rspi-localserver"
VENV_PATH="$APP_HOME/venv"
CONFIG_PATH="/etc/rspi-localserver"
LOG_PATH="/var/log/rspi-localserver"
SYSTEMD_SERVICE="/etc/systemd/system/${APP_NAME}.service"

echo "🚀 Installing $APP_NAME..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash install.sh)"
   exit 1
fi

# Update system packages
echo "🔄 Updating system packages..."
apt update
apt install -y python3 python3-venv python3-pip ntfs-3g exfat-fuse exfatprogs dosfstools \
    build-essential pkg-config poppler-utils tesseract-ocr libtesseract-dev libleptonica-dev

# Create application user and group
echo "👤 Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    groupadd -f "$APP_GROUP"
    useradd -r -g "$APP_GROUP" -d "$APP_HOME" -s /usr/sbin/nologin "$APP_USER" || true
fi
RSPI_UID=$(id -u "$APP_USER")
RSPI_GID=$(id -g "$APP_USER")

# Create directories
echo "📁 Creating directories..."
mkdir -p "$APP_HOME"
mkdir -p "$CONFIG_PATH"
mkdir -p "$LOG_PATH"
mkdir -p "/media/usb"
chmod 755 "/media/usb"

# Create USB auto-mount helper script
echo "🔌 Configuring USB auto-mount..."
cat > /usr/local/bin/usb-mount.sh << 'MOUNT_SCRIPT'
#!/bin/bash
# USB auto-mount helper script
ACTION=$1
DEVNAME=$2

RSPI_UID=$(id -u rspi)
RSPI_GID=$(id -g rspi)

# Get filesystem label or use device name
FS_LABEL=$(blkid -s LABEL -o value "$DEVNAME" 2>/dev/null)
FS_TYPE=$(blkid -s TYPE -o value "$DEVNAME" 2>/dev/null)
if [ -z "$FS_LABEL" ]; then
    MOUNT_POINT="/media/usb/$(basename $DEVNAME)"
else
    MOUNT_POINT="/media/usb/$FS_LABEL"
fi

if [ "$ACTION" = "add" ]; then
    # Create mount point and mount
    mkdir -p "$MOUNT_POINT"
    chown $RSPI_UID:$RSPI_GID "$MOUNT_POINT"
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        logger "USB: $MOUNT_POINT already mounted"
        exit 0
    fi
    # Choose mount command/options per FS type
    MOUNT_OK=false
    if [ "$FS_TYPE" = "ntfs" ] || [ "$FS_TYPE" = "fuseblk" ]; then
        if command -v ntfs-3g >/dev/null 2>&1; then
            ntfs-3g -o uid=$RSPI_UID,gid=$RSPI_GID,umask=022,big_writes "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
        else
            mount -t ntfs -o uid=$RSPI_UID,gid=$RSPI_GID,umask=022 "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
        fi
    elif [ "$FS_TYPE" = "vfat" ] || [ "$FS_TYPE" = "exfat" ]; then
        mount -t "$FS_TYPE" -o uid=$RSPI_UID,gid=$RSPI_GID,umask=022 "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
    elif [ -n "$FS_TYPE" ]; then
        # ext*, xfs, btrfs, etc. (no uid/gid options)
        mount -t "$FS_TYPE" "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
    else
        # Fallback
        mount "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
    fi
    if $MOUNT_OK; then
        logger "USB: Mounted $DEVNAME at $MOUNT_POINT"
    else
        # Fallback: try read-only mount for visibility
        if [ "$FS_TYPE" = "ntfs" ] || [ "$FS_TYPE" = "fuseblk" ]; then
            if command -v ntfs-3g >/dev/null 2>&1; then
                ntfs-3g -o ro,uid=$RSPI_UID,gid=$RSPI_GID,umask=022 "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
            fi
        elif [ "$FS_TYPE" = "vfat" ] || [ "$FS_TYPE" = "exfat" ]; then
            mount -t "$FS_TYPE" -o ro,uid=$RSPI_UID,gid=$RSPI_GID,umask=022 "$DEVNAME" "$MOUNT_POINT" && MOUNT_OK=true
        fi
        if $MOUNT_OK; then
            logger "USB: Mounted read-only $DEVNAME at $MOUNT_POINT"
        else
            logger "USB: Failed to mount $DEVNAME at $MOUNT_POINT"
            rmdir "$MOUNT_POINT" 2>/dev/null || true
        fi
    fi
elif [ "$ACTION" = "remove" ]; then
    # Determine the actual mount point
    if [ -d "$DEVNAME" ]; then
        MOUNT_POINT="$DEVNAME"
    else
        MP=$(findmnt -n -o TARGET "$DEVNAME" 2>/dev/null)
        if [ -n "$MP" ]; then
            MOUNT_POINT="$MP"
        fi
    fi

    # Unmount and remove empty directory
    if [ -n "$MOUNT_POINT" ] && mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        umount -l "$MOUNT_POINT" || umount -l "$DEVNAME" || true
        logger "USB: Unmounted $DEVNAME from $MOUNT_POINT"
        # Remove empty directory
        if [ -d "$MOUNT_POINT" ] && [ -z "$(ls -A $MOUNT_POINT 2>/dev/null)" ]; then
            rmdir "$MOUNT_POINT" 2>/dev/null || true
            logger "USB: Removed empty mount point $MOUNT_POINT"
        fi
    else
        # Fallback: just try to remove dir if empty
        if [ -d "$MOUNT_POINT" ] && [ -z "$(ls -A $MOUNT_POINT 2>/dev/null)" ]; then
            rmdir "$MOUNT_POINT" 2>/dev/null || true
            logger "USB: Removed empty mount point $MOUNT_POINT"
        fi
    fi
fi
MOUNT_SCRIPT

chmod +x /usr/local/bin/usb-mount.sh

# Create systemd service for USB mounting
cat > /etc/systemd/system/usb-mount@.service << 'SERVICE_EOF'
[Unit]
Description=Mount USB Drive %I
After=local-fs.target dev-%i.device
BindsTo=dev-%i.device
Requires=dev-%i.device

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=30
TimeoutStopSec=30
ExecStart=/usr/local/bin/usb-mount.sh add /dev/%i
ExecStop=/usr/local/bin/usb-mount.sh remove /dev/%i
SERVICE_EOF

# Setup udev rules to trigger systemd service
cat > /etc/udev/rules.d/99-automount.rules << UDEV_EOF
# Auto-mount USB storage devices via systemd
ACTION=="add", SUBSYSTEM=="block", ENV{DEVTYPE}=="partition", KERNEL=="sd*[0-9]", ENV{ID_FS_TYPE}!="", \
    TAG+="systemd", ENV{SYSTEMD_WANTS}+="usb-mount@%k.service"
# Removal will be handled by systemd ExecStop when the device disappears
UDEV_EOF

# Reload systemd and udev
systemctl daemon-reload
udevadm control --reload
udevadm trigger

# Copy application files
echo "📦 Copying application files..."
if [ -d "$(dirname "$0")/app" ]; then
    cp -r "$(dirname "$0")/app" "$APP_HOME/"
    cp -r "$(dirname "$0")/requirements.txt" "$APP_HOME/"

    # Copy apps (core and optional) for offline fallback; dashboard controls install state
    if [ -d "$(dirname "$0")/apps" ]; then
        cp -r "$(dirname "$0")/apps" "$APP_HOME/" 2>/dev/null || true
        echo "✅ Apps directory copied (core + optional for fallback)"
    fi
else
    echo "❌ Application files not found. Run this script from the project root directory."
    exit 1
fi

# Copy and customize config
echo "⚙️  Setting up configuration..."
if [ -f "$(dirname "$0")/config/config.yaml" ]; then
    cp "$(dirname "$0")/config/config.yaml" "$CONFIG_PATH/"
fi

###############################################
# Install Python dependencies (resilient flow)
###############################################
echo "🐍 Installing Python dependencies..."
python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

# Use on-disk temp to avoid tmpfs exhaustion
BUILD_TMP="$APP_HOME/tmpbuild"
mkdir -p "$BUILD_TMP"
export TMPDIR="$BUILD_TMP"

pip install --upgrade pip setuptools wheel

# Install core deps (skip heavy PyMuPDF/Pillow; they cause OOM on 1GB Pi)
echo "📦 Installing lightweight core dependencies..."
grep -Ev '^(PyMuPDF|Pillow|pdf2image|pytesseract)' "$APP_HOME/requirements.txt" > "$APP_HOME/requirements.core.txt"

set +e
pip install --no-cache-dir -r "$APP_HOME/requirements.core.txt"
CORE_STATUS=$?
set -e

if [ $CORE_STATUS -ne 0 ]; then
  echo "❌ Core dependency install failed. Check logs."
  exit 1
fi

# Install pdfminer.six as lightweight PDF parser (no build required)
echo "📄 Installing pdfminer.six (lightweight PDF parser)..."
pip install --no-cache-dir pdfminer.six

# Optional: Try Pillow from piwheels binary (for OCR support)
echo "🖼️ Attempting Pillow from piwheels (OCR support, optional)..."
set +e
pip install --no-cache-dir Pillow --index-url https://www.piwheels.org/simple
PILLOW_STATUS=$?
set -e

if [ $PILLOW_STATUS -eq 0 ]; then
  echo "✅ Pillow installed from piwheels"
  # Try pdf2image and pytesseract for OCR
  set +e
  pip install --no-cache-dir pdf2image pytesseract
  OCR_STATUS=$?
  set -e
  if [ $OCR_STATUS -eq 0 ]; then
    echo "✅ OCR support enabled (pdf2image + pytesseract)"
  else
    echo "⚠️ OCR packages failed; OCR features disabled"
  fi
else
  echo "⚠️ Pillow install failed; OCR features disabled"
fi

# Verify text extraction backend
if python - <<'PY'
try:
    import pdfminer.high_level
    print('pdfminer-ok')
except Exception:
    raise SystemExit(1)
PY
then
  echo "✅ Text extraction backend available (pdfminer.six + pdftotext)"
else
  echo "❌ No text extraction backend available. Installation incomplete."
  exit 1

# Create systemd service
echo "🔧 Installing systemd service..."
cat > "$SYSTEMD_SERVICE" << 'SYSTEMD_EOF'
[Unit]
Description=RSPI LocalServer File Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
User=rspi
Group=rspi
WorkingDirectory=/opt/rspi-localserver
Environment="PATH=/opt/rspi-localserver/venv/bin"
ExecStart=/opt/rspi-localserver/venv/bin/gunicorn \
    --bind 0.0.0.0:8080 \
    --workers 1 \
    --threads 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 30 \
    --access-logfile /var/log/rspi-localserver/access.log \
    --error-logfile /var/log/rspi-localserver/error.log \
    --log-level info \
    app.main:app

Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rspi-localserver

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/media/usb /var/log/rspi-localserver /opt/rspi-localserver

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

# Set permissions
echo "🔐 Setting permissions..."
# Clean up stale sd* folders that are not mount points (avoid I/O errors)
if [ -d "/media/usb" ]; then
    for d in /media/usb/sd*; do
        [ -d "$d" ] || continue
        if mountpoint -q "$d" 2>/dev/null; then
            umount -l "$d" 2>/dev/null || true
        fi
        if [ -d "$d" ] && [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
            rmdir "$d" 2>/dev/null || true
        fi
    done
fi

chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" "$CONFIG_PATH" "$LOG_PATH" "/media/usb" 2>/dev/null || true
chmod 755 "$APP_HOME"
chmod 755 "$LOG_PATH"
chmod 640 "$CONFIG_PATH/config.yaml"
chmod 644 "$SYSTEMD_SERVICE"

# Enable and start service
echo "▶️  Enabling and starting service..."
systemctl daemon-reload
systemctl enable "$APP_NAME"
systemctl restart "$APP_NAME"

# Verify installation
sleep 2
if systemctl is-active --quiet "$APP_NAME"; then
    echo ""
    echo "✅ Installation successful!"
    echo ""
    echo "📍 Service: $APP_NAME"
    echo "📂 App directory: $APP_HOME"
    echo "⚙️  Config: $CONFIG_PATH/config.yaml"
    echo "📋 Logs: $LOG_PATH/"
    echo ""
    echo "🌐 Access: http://<pi-ip>:8080"
    echo ""
    echo "🛠️  Common commands:"
    echo "  sudo systemctl status $APP_NAME       # Check status"
    echo "  sudo systemctl restart $APP_NAME      # Restart"
    echo "  sudo systemctl stop $APP_NAME         # Stop"
    echo "  sudo tail -f $LOG_PATH/error.log      # View logs"
    echo ""
else
    echo "❌ Service failed to start. Check logs:"
    systemctl status "$APP_NAME"
    exit 1
fi
