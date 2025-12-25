#!/bin/bash
set -e

# RSPI LocalServer Update Script
# Run: sudo bash update.sh

APP_NAME="rspi-localserver"
APP_HOME="/opt/rspi-localserver"
VENV_PATH="$APP_HOME/venv"
CONFIG_PATH="/etc/rspi-localserver"

echo "🔄 Updating $APP_NAME..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash update.sh)"
   exit 1
fi

# Check if app is installed
if [ ! -d "$APP_HOME" ]; then
    echo "❌ Application not found at $APP_HOME"
    echo "Run install.sh first"
    exit 1
fi

# Stop service
echo "🛑 Stopping service..."
systemctl stop "$APP_NAME" || true

# Backup current app
echo "💾 Backing up current installation..."
BACKUP_DIR="/opt/rspi-localserver-backup-$(date +%Y%m%d-%H%M%S)"
cp -r "$APP_HOME" "$BACKUP_DIR"
echo "Backup saved to: $BACKUP_DIR"

# Update application files
echo "📦 Updating application files..."
if [ -d "$(dirname "$0")/app" ]; then
    rm -rf "$APP_HOME/app"
    cp -r "$(dirname "$0")/app" "$APP_HOME/"
else
    echo "❌ Application files not found. Run this script from the project root directory."
    exit 1
fi

# Update dependencies
echo "🐍 Updating Python dependencies..."
source "$VENV_PATH/bin/activate"
pip install --upgrade pip setuptools wheel
pip install -r "$APP_HOME/requirements.txt"
deactivate

# Optionally update config (keep existing, merge new)
if [ -f "$(dirname "$0")/config/config.yaml" ]; then
    echo "⚙️  Config file exists at $CONFIG_PATH/config.yaml (not overwritten)"
    echo "   Review $(dirname "$0")/config/config.yaml for new options"
fi

# Fix permissions
echo "🔐 Fixing permissions..."
chown -R rspi:rspi "$APP_HOME"
chmod 755 "$APP_HOME"

# Restart service
echo "▶️  Restarting service..."
systemctl daemon-reload
systemctl restart "$APP_NAME"

# Verify
sleep 2
if systemctl is-active --quiet "$APP_NAME"; then
    echo ""
    echo "✅ Update successful!"
    echo ""
    echo "🌐 Access: http://<pi-ip>:8080"
    echo "📋 Check logs: sudo tail -f /var/log/rspi-localserver/error.log"
    echo ""
else
    echo "❌ Service failed to start after update"
    echo "Rolling back..."
    rm -rf "$APP_HOME"
    cp -r "$BACKUP_DIR" "$APP_HOME"
    systemctl restart "$APP_NAME"
    exit 1
fi
