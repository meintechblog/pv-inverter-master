# PV-Inverter Proxy

Modbus TCP proxy that makes a **SolarEdge SE30K** inverter appear as a **Fronius** to **Venus OS** (Victron). Venus OS natively discovers, monitors, and controls the inverter — including power limiting via DVCC/ESS.

Includes a dark-themed **web dashboard** with live monitoring, power control, and Venus OS integration.

## Prerequisites

- **Debian 12+** / **Ubuntu 22.04+** (LXC, VM, or bare metal)
- **Python 3.12+** (installed automatically by installer)
- **Venus OS >= 3.7** (required for MQTT on LAN feature)
- All devices on the same LAN

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash
```

This installs everything: Python venv, systemd service, default config. Edit the config afterwards:

```bash
nano /etc/venus-os-fronius-proxy/config.yaml
systemctl restart venus-os-fronius-proxy
```

### Update

Same command — the script detects an existing installation and updates in-place:

```bash
curl -fsSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash
```

## Configuration

`/etc/venus-os-fronius-proxy/config.yaml`:

```yaml
inverter:
  host: "192.168.3.18"    # Your SolarEdge inverter IP
  port: 1502              # Modbus TCP port
  unit_id: 1              # Modbus unit/slave ID

proxy:
  port: 502               # Venus OS connects here

venus:
  host: ""                # Venus OS IP (empty = MQTT disabled)
  port: 1883              # MQTT port
  portal_id: ""           # Leave empty for auto-discovery

webapp:
  port: 80                # Dashboard URL

log_level: INFO
```

Leave `venus.host` empty to run without Venus OS MQTT integration. The proxy and dashboard work standalone.

## Setup Flow

### 1. Install the Proxy

Run the install command above. The dashboard is available at `http://<proxy-ip>`.

### 2. Configure SolarEdge Connection

Open the dashboard Config page. The default SolarEdge IP (192.168.3.18:1502) is pre-filled. Adjust to match your inverter and click Save & Apply. A green connection bobble confirms the connection.

### 3. Connect Venus OS

Point Venus OS to the proxy IP on port 502. It auto-discovers the proxy as a Fronius inverter. When Venus OS connects, the Config page shows an auto-detect banner prompting you to set up MQTT.

### 4. Enable Venus OS MQTT (Optional)

On your Venus OS device (Remote Console):
1. Go to **Settings > Services > MQTT on LAN**
2. Enable MQTT

Then enter the Venus OS IP in the Config page's Venus section and click Save & Apply. A green MQTT bobble confirms the connection. Dashboard features like Lock Toggle and Override Detection activate automatically.

## Architecture

<p align="center">
  <img src="docs/architecture-hex.svg" alt="System Architecture" width="800"/>
</p>

The proxy sits between the SolarEdge inverter and Venus OS, translating protocols in real-time:

| Path | Protocol | Purpose |
|------|----------|---------|
| SE30K **→** Proxy | Modbus TCP :1502 | Poll inverter data every 1s (power, voltage, temperature) |
| Proxy **→** Venus OS | Modbus TCP :502 | Serve translated Fronius SunSpec registers |
| Venus OS **→** Proxy | Modbus Write | Send power limit commands (ESS feed-in control) |
| Proxy **→** SE30K | Modbus Write (EDPC) | Forward power limits to the real inverter |
| Venus OS **→** Proxy | MQTT :1883 | Subscribe to ESS settings, grid power, limiter state |
| Proxy **→** Browser | WebSocket + REST :80 | Live dashboard with real-time updates |

## Features

- **Modbus Proxy** — SolarEdge registers translated to Fronius SunSpec profile (Model 1/103/120/123)
- **Venus OS Native** — Auto-detected as "Fronius SE30K", power limiting via Model 123 -> SE EDPC
- **Live Dashboard** — Power gauge, 3-phase AC table, sparkline (60 min), peak statistics
- **Power Control** — Dropdown (5% steps) with confirmation, auto-revert after 5 min
- **Venus OS Widget** — Connection status, override display, disable toggle (15 min safety cap)
- **Config Page** — SolarEdge and Venus OS settings with live connection bobbles
- **MQTT Setup Guide** — In-app instructions when MQTT is not connected
- **Venus OS Auto-Detect** — Banner when Venus OS Modbus connection is detected
- **Smart Notifications** — Toast alerts for overrides, faults, temperature warnings, night mode
- **CSS Animations** — Smooth gauge transitions, entrance animations, prefers-reduced-motion support
- **Night Mode** — Synthetic registers when inverter sleeps, no crashes

## Dashboard

Access at `http://<proxy-ip>` (port 80).

**Pages:**
- **Dashboard** — Power gauge, 3-phase AC, power control, connection status, Venus OS control, sparkline, peak stats, inverter status, service health
- **Config** — SolarEdge and Venus OS connection settings with live status bobbles
- **Registers** — Raw Modbus register viewer

## Management

```bash
# Service status
systemctl status venus-os-fronius-proxy

# Live logs
journalctl -u venus-os-fronius-proxy -f

# Restart
systemctl restart venus-os-fronius-proxy

# Stop
systemctl stop venus-os-fronius-proxy
```

## Tech Stack

- **Python 3.12**, pymodbus 3.8+, aiohttp, paho-mqtt, structlog, PyYAML
- **Frontend**: Vanilla JS, CSS3 (zero dependencies, no build step)
- **Deployment**: systemd service on Debian/Ubuntu (LXC recommended)

## Development

```bash
git clone https://github.com/meintechblog/pv-inverter-proxy.git
cd venus-os-fronius-proxy
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Deploy from dev machine to LXC:

```bash
./deploy.sh              # Update existing installation
./deploy.sh --first-time # First-time setup on LXC
```

## License

[Energy Community License (ECL-1.0)](LICENSE) — Free to use, modify, and redistribute. Commercial resale of the software itself is not permitted. See [LICENSE](LICENSE) for details.
