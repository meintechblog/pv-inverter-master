# Technology Stack

**Project:** Venus OS Fronius Proxy -- v3.0 Setup & Onboarding
**Researched:** 2026-03-19
**Scope:** Stack additions for MQTT config UI, auto-discovery, connection status, install script

## Existing Stack (DO NOT CHANGE)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Runtime |
| pymodbus | >=3.6,<4.0 | Modbus TCP server + client |
| aiohttp | latest | HTTP server, WebSocket, REST API |
| structlog | latest | Structured JSON logging |
| PyYAML | latest | Config file parsing |
| vanilla JS | N/A | Frontend (3-file: HTML/CSS/JS) |
| systemd | N/A | Service management |

## Recommended Stack Additions

### Zero new dependencies needed

The v3.0 features require **no new Python packages**. Everything can be built with the existing stack plus Python stdlib. This is deliberate -- the project has a "zero new dependencies" decision that should be maintained.

**Rationale:** The existing raw-socket MQTT client in `venus_reader.py` already works. The new features are config plumbing and UI, not new protocol work.

### Core Framework (no changes)

| Technology | Version | Purpose | Why No Change |
|------------|---------|---------|---------------|
| aiohttp | existing | Config API endpoints | Already serves REST + WebSocket, just add new routes |
| PyYAML | existing | MQTT config persistence | Already handles config load/save with atomic writes |
| Python dataclasses | stdlib | VenusConfig dataclass | Same pattern as InverterConfig, ProxyConfig |

### MQTT Discovery (stdlib only)

| Component | Implementation | Why |
|-----------|---------------|-----|
| Portal ID auto-detect | MQTT wildcard `N/+/system/0/Serial` | Venus OS MQTT supports `+` wildcard in place of portal ID. Subscribe to `N/+/system/0/Serial` and the payload contains the portal ID as a 12-char hex string. No library needed -- raw socket MQTT client already exists in `venus_reader.py`. **HIGH confidence** -- documented in [victronenergy/venus-html5-app TOPICS.md](https://github.com/victronenergy/venus-html5-app/blob/master/TOPICS.md) and confirmed by [community posts](https://community.victronenergy.com/questions/155407/mqtt-local-via-mqtt-broker.html) |
| Venus OS host detection | Extract source IP from incoming Modbus TCP connection on port 502 | pymodbus server already accepts connections. The source IP of the first Modbus client connection IS the Venus OS IP. No library needed. **HIGH confidence** -- the proxy already does this implicitly |
| MQTT broker probe | `socket.create_connection((host, 1883), timeout=3)` | Quick TCP connect test to verify MQTT broker is reachable before attempting full MQTT connection. Stdlib socket. **HIGH confidence** |
| Keep-alive | `R/{portalId}/system/0/Serial` with empty payload every 50s | Venus OS MQTT broker stops publishing subscribed notifications after 60s without keep-alive. Current code sends PINGREQ but not the R/ keep-alive topic. Both are needed: PINGREQ keeps the TCP connection alive, R/ keep-alive tells Venus OS to keep sending data. **HIGH confidence** -- [documented behavior](https://github.com/victronenergy/dbus-mqtt) |

### Connection Status Detection (stdlib + existing)

| Component | Implementation | Why |
|-----------|---------------|-----|
| Inverter status | Already exists in `ConnectionManager` | `ConnectionState` enum: CONNECTED, RECONNECTING, NIGHT_MODE. Already tracked in `shared_ctx["conn_mgr"]` |
| MQTT status | New field in `shared_ctx["venus_settings"]` | Add `connected: bool` and `last_seen: float` to the venus_settings dict. The MQTT loop already updates `ts` on every message. Frontend checks `ts` freshness (stale if >90s since last update). **No library needed** |
| Config page connection bobble | CSS + existing WebSocket | Existing WebSocket already pushes snapshots with connection state. Add MQTT status to the snapshot. Frontend renders green/red/yellow dot based on state. **No library needed** |
| Venus OS auto-detected IP | Track first Modbus client IP in `shared_ctx` | pymodbus `ModbusTcpServer` accepts connections. Hook into the connection handling to extract the peer address. **MEDIUM confidence** -- pymodbus internal API for connection callbacks needs verification during implementation |

### Config Persistence (existing pattern)

| Component | Implementation | Why |
|-----------|---------------|-----|
| VenusConfig dataclass | New `@dataclass` in `config.py` | Pattern: `host: str = ""`, `port: int = 1883`, `portal_id: str = ""` (empty = auto-detect). Same pattern as existing InverterConfig |
| Config save | `save_config()` already exists | Atomic write via tempfile + os.replace. Just extend the Config dataclass with a `venus` field |
| Config API | `POST /api/config` already exists in webapp | Extend existing endpoint to accept venus section. No new routes needed, just wider payload |

### Install Script Improvements (bash only)

| Improvement | Implementation | Why |
|-------------|---------------|-----|
| Secure curl flags | `curl -fsSL --proto '=https' --tlsv1.2` | `-f` fails on HTTP errors (prevents piping 404 into bash). `--proto '=https'` forces HTTPS. `--tlsv1.2` requires TLS 1.2+. Industry standard for curl-pipe-bash. |
| Version pinning | `VERSION` env var + `git checkout "v${VERSION}"` | Allow pinning to specific release: `VERSION=3.0.0 bash`. Default to `main` if unset for backwards compatibility |
| Idempotency guards | Check state before each action | Already partially done. Add: skip apt-get if packages present, skip venv creation if exists, compare running version before restart |
| Config preservation on update | Never overwrite existing `config.yaml` | Already done (checks `! -f`). The existing logic is correct |
| Post-install config guidance | Print setup URL | Show `http://<IP>/config` after install so user knows where to go for MQTT setup |
| Version display | `git describe --tags --always` | Show installed version in final output for troubleshooting |

## What NOT to Add

| Temptation | Why Not |
|------------|---------|
| paho-mqtt | Adds dependency for no benefit. Raw socket MQTT client is ~60 LOC and handles the subscribe/publish pattern needed. paho-mqtt's threading model also conflicts with the asyncio event loop |
| aiomqtt | Better async fit than paho, but still unnecessary. The raw client works and is tested. Adding it would require refactoring `venus_reader.py` for no user-visible gain |
| zeroconf / python-avahi | Venus OS does not advertise services via mDNS by default. The Modbus connection itself IS the discovery mechanism -- Venus OS MUST connect to the proxy, so the IP is known |
| Any frontend framework | Project constraint: vanilla JS, no build tooling. A config form with 4 fields does not need React |
| SQLite / database | Config is YAML. Settings are 5 fields. A database would be absurd over-engineering |
| python-dotenv | Config is YAML-based. Adding env var config support would create two sources of truth |
| Flask / FastAPI | aiohttp already runs the webapp. One HTTP framework is enough |

## Implementation Architecture for New Features

### MQTT Auto-Configuration Flow

```
1. User installs proxy (install.sh)
2. Proxy starts with venus.host = "" (empty = not configured)
3. Venus OS connects to proxy on port 502 (Modbus TCP)
4. Proxy extracts Venus OS IP from incoming TCP connection
5. Proxy attempts MQTT connect to detected_ip:1883
6. If MQTT works: subscribe N/+/system/0/Serial -> extract portal_id from topic
7. Auto-populate venus section in config.yaml, save to disk
8. Dashboard elements un-grey (MQTT-dependent: Lock, Override, Venus Settings)
9. User can override any auto-detected value via Config page
```

### Config Dataclass Extension

```python
@dataclass
class VenusConfig:
    host: str = ""          # Empty = auto-detect from Modbus connection
    port: int = 1883        # MQTT port (standard, rarely changed)
    portal_id: str = ""     # Empty = auto-detect via MQTT wildcard N/+/...
    enabled: bool = True    # Allow disabling MQTT entirely (hides Venus widgets)
```

Add to existing `Config`:

```python
@dataclass
class Config:
    inverter: InverterConfig = field(default_factory=InverterConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    night_mode: NightModeConfig = field(default_factory=NightModeConfig)
    webapp: WebappConfig = field(default_factory=WebappConfig)
    venus: VenusConfig = field(default_factory=VenusConfig)  # NEW
    log_level: str = "INFO"
```

### MQTT Wildcard Discovery Detail

The current `venus_reader.py` hardcodes `PORTAL_ID` and `VENUS_HOST`. Change to:

1. Accept `host` and `portal_id` as parameters (from config)
2. If `portal_id` is empty, subscribe to `N/+/system/0/Serial`
3. First message received will have topic `N/{actual_portal_id}/system/0/Serial`
4. Extract `actual_portal_id` from the topic string (split on `/`, index 1)
5. Save discovered portal_id back to config
6. Re-subscribe with concrete portal_id for all other topics

```python
# Discovery phase (portal_id unknown):
sub_topics = ["N/+/system/0/Serial"]

# After portal_id discovered:
portal = extracted_portal_id
sub_topics = [
    f"N/{portal}/settings/0/Settings/CGwacs/#",
    f"N/{portal}/system/0/Ac/Grid/#",
    # ... existing topics
]
```

### Connection Status in WebSocket Snapshot

```python
# Add to existing dashboard snapshot (pushed every ~1s via WebSocket):
"connections": {
    "inverter": "connected",          # from conn_mgr.state.value (existing)
    "mqtt": "connected",              # NEW: from venus_settings presence + ts freshness
    "venus_os_ip": "192.168.3.146",   # NEW: detected or configured
    "portal_id": "88a29ec1e5f4",      # NEW: detected or configured
}
```

Frontend uses this to:
- Show green/red/yellow bobble next to each service on Config page
- Grey out MQTT-dependent dashboard elements when `mqtt != "connected"`
- Show "Waiting for Venus OS..." message when `venus_os_ip` is empty

### Install Script Improved One-Liner

```bash
# Current:
curl -sSL https://raw.githubusercontent.com/.../install.sh | bash

# Improved (secure):
curl -fsSL --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/.../install.sh | bash

# With version pinning:
curl -fsSL --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/.../install.sh | VERSION=3.0.0 bash
```

### Config Page YAML Section

The install script's default config template should include the new venus section:

```yaml
# Venus OS MQTT connection (auto-detected if left empty)
venus:
  host: ""         # Venus OS IP (auto-detected from Modbus connection)
  port: 1883       # MQTT broker port
  portal_id: ""    # VRM Portal ID (auto-detected via MQTT)
  enabled: true    # Set false to disable MQTT features
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| MQTT client | Raw socket (existing) | paho-mqtt or aiomqtt | Would add a dependency. Raw socket client works, is ~60 LOC, handles the simple subscribe/publish needed. Project avoids new deps |
| Service discovery | Modbus connection IP extraction | mDNS/Avahi/zeroconf | Venus OS does not advertise via mDNS. Modbus connection IP is simpler and guaranteed |
| Portal ID config | Auto-detect via wildcard + manual override | Manual entry only | Wildcard discovery is documented and reliable. Auto-detect with manual override gives best UX |
| Config UI framework | Vanilla JS (existing) | Alpine.js / htmx | Project constraint: zero frontend dependencies. A config form is trivially simple in vanilla JS |
| Config format | YAML (existing) | TOML, JSON, env vars | YAML already used with load/save module. No reason to change |
| Install method | bash script (existing) | Ansible, Docker, deb package | Target is single LXC. Bash is the right tool. Docker explicitly out of scope |

## Version Constraints

| Package | Current Pin | Change? | Notes |
|---------|------------|---------|-------|
| pymodbus | >=3.6,<4.0 | No | Sufficient for all v3.0 features |
| aiohttp | unpinned | No | Latest 3.x stable is fine |
| structlog | unpinned | No | Stable API |
| PyYAML | unpinned | No | Stable API |

**No version changes or new packages needed.**

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| No new deps needed | HIGH | Codebase already has all building blocks. Raw MQTT, config save, WebSocket push all exist |
| MQTT wildcard discovery | HIGH | Documented by Victron in [TOPICS.md](https://github.com/victronenergy/venus-html5-app/blob/master/TOPICS.md). `N/+/system/0/Serial` returns portal ID. Confirmed by community |
| Venus OS IP from Modbus | MEDIUM | Conceptually sound (Venus OS must connect to port 502). pymodbus transport API for extracting peer IP needs verification during implementation |
| MQTT keep-alive 60s | HIGH | Documented in [dbus-mqtt](https://github.com/victronenergy/dbus-mqtt). Broker requires R/ keep-alive every 60s or stops publishing notifications |
| Install script patterns | HIGH | Standard bash practices. Well-documented at [Arslan's guide](https://arslan.io/2019/07/03/how-to-write-idempotent-bash-scripts/) and [curl best practices](https://www.joyfulbikeshedding.com/blog/2020-05-11-best-practices-when-using-curl-in-shell-scripts.html) |
| Config dataclass extension | HIGH | Follows existing pattern exactly (InverterConfig, ProxyConfig). load_config/save_config already handle nested dataclasses |

## Sources

- [victronenergy/dbus-mqtt](https://github.com/victronenergy/dbus-mqtt) -- MQTT keep-alive mechanism, topic structure (archived, replaced by dbus-flashmq since Venus OS v3.20)
- [victronenergy/venus-html5-app TOPICS.md](https://github.com/victronenergy/venus-html5-app/blob/master/TOPICS.md) -- MQTT topic reference, wildcard usage for portal ID
- [victronenergy/dbus-flashmq](https://github.com/victronenergy/dbus-flashmq) -- Current MQTT implementation in Venus OS v3.20+
- [Victron Community: MQTT local & via broker](https://community.victronenergy.com/questions/155407/mqtt-local-via-mqtt-broker.html) -- Portal ID wildcard pattern confirmation
- [Home Assistant Victron integration](https://community.home-assistant.io/t/victron-venus-os-with-mqtt-sensors-switches-and-numbers/527931) -- Real-world MQTT topic usage examples
- [Idempotent Bash scripts (Arslan, 2019)](https://arslan.io/2019/07/03/how-to-write-idempotent-bash-scripts/) -- Install script idempotency patterns
- [Curl best practices in shell scripts (Joyful Bikeshedding, 2020)](https://www.joyfulbikeshedding.com/blog/2020-05-11-best-practices-when-using-curl-in-shell-scripts.html) -- Security flags for curl-pipe-bash pattern
