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

# Setup USB auto-mount rules (handles labeled and unlabeled drives)
echo "🔌 Configuring USB auto-mount..."
cat > /etc/udev/rules.d/99-automount.rules << UDEV_EOF
# Auto-mount USB storage with rspi ownership
ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd*[0-9]", ENV{ID_FS_TYPE}!="", \
    RUN+="/bin/mkdir -p /media/usb/%E{ID_FS_LABEL_ENC}", \
    RUN+="/bin/chown ${RSPI_UID}:${RSPI_GID} /media/usb/%E{ID_FS_LABEL_ENC}", \
    RUN+="/bin/mount -o uid=${RSPI_UID},gid=${RSPI_GID},umask=022 /dev/%k /media/usb/%E{ID_FS_LABEL_ENC}"

# Fallback for devices without label
ACTION=="add", SUBSYSTEM=="block", KERNEL=="sd*[0-9]", ENV{ID_FS_TYPE}!="", ENV{ID_FS_LABEL_ENC}=="", \
    RUN+="/bin/mkdir -p /media/usb/%k", \
    RUN+="/bin/chown ${RSPI_UID}:${RSPI_GID} /media/usb/%k", \
    RUN+="/bin/mount -o uid=${RSPI_UID},gid=${RSPI_GID},umask=022 /dev/%k /media/usb/%k"

# Unmount on removal
ACTION=="remove", SUBSYSTEM=="block", KERNEL=="sd*[0-9]", \
    RUN+="/bin/umount -l /dev/%k"
UDEV_EOF

# Reload udev rules
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
