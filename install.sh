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
apt install -y python3 python3-venv python3-pip ntfs-3g exfat-fuse

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
if [ -z "$FS_LABEL" ]; then
    MOUNT_POINT="/media/usb/$(basename $DEVNAME)"
else
    MOUNT_POINT="/media/usb/$FS_LABEL"
fi

if [ "$ACTION" = "add" ]; then
    # Create mount point and mount
    mkdir -p "$MOUNT_POINT"
    chown $RSPI_UID:$RSPI_GID "$MOUNT_POINT"
    mount -o uid=$RSPI_UID,gid=$RSPI_GID,umask=022 "$DEVNAME" "$MOUNT_POINT"
    logger "USB: Mounted $DEVNAME at $MOUNT_POINT"
elif [ "$ACTION" = "remove" ]; then
    # Unmount
    umount -l "$DEVNAME" 2>/dev/null || true
    logger "USB: Unmounted $DEVNAME"
fi
MOUNT_SCRIPT

chmod +x /usr/local/bin/usb-mount.sh

# Create systemd service for USB mounting
cat > /etc/systemd/system/usb-mount@.service << 'SERVICE_EOF'
[Unit]
Description=Mount USB Drive %I
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/usb-mount.sh add /dev/%i
ExecStop=/usr/local/bin/usb-mount.sh remove /dev/%i
SERVICE_EOF

# Setup udev rules to trigger systemd service
cat > /etc/udev/rules.d/99-automount.rules << UDEV_EOF
# Auto-mount USB storage devices via systemd
ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd*[0-9]", ENV{ID_FS_TYPE}!="", \
    TAG+="systemd", ENV{SYSTEMD_WANTS}+="usb-mount@%k.service"
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
else
    echo "❌ Application files not found. Run this script from the project root directory."
    exit 1
fi

# Copy and customize config
echo "⚙️  Setting up configuration..."
if [ -f "$(dirname "$0")/config/config.yaml" ]; then
    cp "$(dirname "$0")/config/config.yaml" "$CONFIG_PATH/"
fi

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
python3 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"
pip install --upgrade pip setuptools wheel
pip install -r "$APP_HOME/requirements.txt"
deactivate

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
chown -R "$APP_USER:$APP_GROUP" "$APP_HOME" "$CONFIG_PATH" "$LOG_PATH" "/media/usb"
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
