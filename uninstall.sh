#!/bin/bash
set -e

# RSPI LocalServer Uninstall Script
# Run: sudo bash uninstall.sh

APP_NAME="rspi-localserver"
APP_HOME="/opt/rspi-localserver"
CONFIG_PATH="/etc/rspi-localserver"
LOG_PATH="/var/log/rspi-localserver"
SYSTEMD_SERVICE="/etc/systemd/system/${APP_NAME}.service"
APP_USER="rspi"

echo "⚠️  Uninstalling $APP_NAME..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash uninstall.sh)"
   exit 1
fi

# Confirm
echo "This will:"
echo "  - Stop the $APP_NAME service"
echo "  - Remove application files from $APP_HOME"
echo "  - Remove systemd service"
echo "  - Keep config files at $CONFIG_PATH (for reference)"
echo "  - Keep logs at $LOG_PATH (for reference)"
echo "  - Keep the rspi user account"
echo "  - Keep /media/usb mount point"
echo ""
read -p "Continue? (yes/no): " -r
echo ""
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Stop service
echo "🛑 Stopping service..."
systemctl stop "$APP_NAME" || true
systemctl disable "$APP_NAME" || true

# Remove service file
echo "🔧 Removing systemd service..."
rm -f "$SYSTEMD_SERVICE"
systemctl daemon-reload

# Remove application files
echo "🗑️  Removing application files..."
rm -rf "$APP_HOME"

# Optionally remove other files
echo ""
echo "Optional cleanup:"
echo "  - To remove config files: sudo rm -rf $CONFIG_PATH"
echo "  - To remove logs: sudo rm -rf $LOG_PATH"
echo "  - To remove rspi user: sudo userdel -r $APP_USER"
echo ""

echo "✅ Uninstall complete!"
echo ""
echo "To finish cleanup, run:"
echo "  sudo rm -rf $CONFIG_PATH"
echo "  sudo rm -rf $LOG_PATH"
echo "  sudo userdel -r $APP_USER"
