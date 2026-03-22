#!/usr/bin/env bash
# PV-Inverter Proxy — One-Line Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash
#
# What it does:
#   1. Creates pv-proxy service user
#   2. Installs Python 3 + venv + git
#   3. Clones the repo (or pulls if exists)
#   4. Creates venv and installs package
#   5. Creates default config if missing
#   6. Installs and starts systemd service
#
# Requirements: Debian 12+ / Ubuntu 22.04+, root access
#
set -euo pipefail

REPO="https://github.com/meintechblog/pv-inverter-proxy.git"
INSTALL_DIR="/opt/pv-inverter-proxy"
CONFIG_DIR="/etc/pv-inverter-proxy"
SERVICE_USER="pv-proxy"
SERVICE_NAME="pv-inverter-proxy"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}>>>${NC} $1"; }
ok()    { echo -e "${GREEN} ✓${NC} $1"; }
fail()  { echo -e "${RED} ✗ $1${NC}"; exit 1; }

# --- Pre-flight ---
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PV-Inverter Proxy — Installer${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

[ "$(id -u)" -eq 0 ] || fail "Must run as root"
command -v apt-get >/dev/null 2>&1 || fail "apt-get not found — Debian/Ubuntu required"

# Check if port 502 is already in use
if ss -tlnp 2>/dev/null | grep -q ':502 '; then
    echo ""
    echo -e "${BLUE}  Note: Port 502 is currently in use.${NC}"
    ss -tlnp 2>/dev/null | grep ':502 '
    echo ""
    echo -e "  The proxy needs port 502. If this is a previous installation,"
    echo -e "  it will be restarted automatically. Otherwise stop the conflicting service first."
    echo ""
fi

# --- Step 1: System dependencies ---
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git >/dev/null 2>&1
ok "Python 3, venv, git installed"

# --- Step 2: Service user ---
if id "$SERVICE_USER" &>/dev/null; then
    ok "User $SERVICE_USER exists"
else
    info "Creating service user..."
    useradd -r -s /usr/sbin/nologin "$SERVICE_USER"
    ok "User $SERVICE_USER created"
fi

# --- Step 3: Clone or update repo ---
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
    ok "Updated to latest"
else
    info "Cloning repository..."
    git clone "$REPO" "$INSTALL_DIR"
    ok "Cloned to $INSTALL_DIR"
fi

# --- Step 4: Python venv + install ---
info "Setting up Python environment..."
cd "$INSTALL_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .
ok "Package installed in venv"

# --- Step 5: Config ---
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    info "Creating default config..."
    cat > "$CONFIG_DIR/config.yaml" << 'YAML'
# PV-Inverter Proxy Configuration
# Docs: https://github.com/meintechblog/pv-inverter-proxy

# SolarEdge inverter connection
inverter:
  host: "192.168.3.18"    # Your SolarEdge inverter IP
  port: 1502              # Modbus TCP port
  unit_id: 1              # Modbus unit/slave ID

# Modbus proxy server (Venus OS connects here)
proxy:
  port: 502

# Venus OS MQTT (optional — leave host empty to disable)
venus:
  host: ""                # Venus OS / Cerbo GX IP address
  port: 1883              # MQTT port (default 1883)
  portal_id: ""           # Leave empty for auto-discovery

# Web dashboard
webapp:
  port: 80

# Logging
log_level: INFO
YAML
    ok "Default config created at $CONFIG_DIR/config.yaml"
    echo ""
    echo -e "${BLUE}  Edit the config to match your setup:${NC}"
    echo -e "  nano $CONFIG_DIR/config.yaml"
    echo ""
else
    if grep -q '^solaredge:' "$CONFIG_DIR/config.yaml" 2>/dev/null; then
        echo ""
        echo -e "${RED}  WARNING: Your config uses the old 'solaredge:' key.${NC}"
        echo -e "  The proxy now expects 'inverter:' instead."
        echo -e "  Please update your config:"
        echo -e "    nano $CONFIG_DIR/config.yaml"
        echo -e "  Change 'solaredge:' to 'inverter:' and add a 'venus:' section."
        echo -e "  Reference: $INSTALL_DIR/config/config.example.yaml"
        echo ""
    fi
    ok "Config exists at $CONFIG_DIR/config.yaml"
fi

# --- Step 6: Permissions ---
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"
ok "Permissions set"

# --- Step 7: Systemd service ---
info "Installing systemd service..."
cp "$INSTALL_DIR/config/pv-inverter-proxy.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Service installed and enabled"

# --- Step 8: Start ---
info "Starting service..."
systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "Service is running"
else
    echo ""
    echo -e "${RED}  Service failed to start. Check logs:${NC}"
    echo "  journalctl -u $SERVICE_NAME -n 20 --no-pager"
    echo ""
    exit 1
fi

# --- Done ---
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "  Dashboard:  http://$(hostname -I | awk '{print $1}')"
echo "  Config:     $CONFIG_DIR/config.yaml"
echo "  Logs:       journalctl -u $SERVICE_NAME -f"
echo "  Status:     systemctl status $SERVICE_NAME"
echo ""
echo "  To update later:"
echo "    curl -fsSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash"
echo ""
