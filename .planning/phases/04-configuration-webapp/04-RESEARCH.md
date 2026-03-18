# Phase 4: Configuration Webapp - Research

**Researched:** 2026-03-18
**Domain:** Embedded web server (aiohttp), REST API, single-page frontend
**Confidence:** HIGH

## Summary

Phase 4 adds an embedded HTTP server to the existing asyncio-based proxy, providing configuration editing, live status monitoring, and a register viewer -- all via a single-page vanilla HTML/JS/CSS frontend with no build step. The locked decision is aiohttp running inside the existing event loop (no separate process), serving static files and REST API endpoints, with browser-side polling every 2 seconds.

The technical challenge is modest: aiohttp's `AppRunner`/`TCPSite` API is designed exactly for this "add HTTP to an existing asyncio app" use case. The `shared_ctx` dict pattern already exposes all runtime state (`cache`, `conn_mgr`, `control_state`, `poll_counter`) needed by the API. The main complexity is in the config save/hot-reload flow (validate, test-connect, write YAML, reconnect plugin) and the register viewer (formatting 177 registers with SunSpec model grouping and human-readable names).

**Primary recommendation:** Use aiohttp `AppRunner`/`TCPSite` to embed the HTTP server as another task in the existing `asyncio.gather()` call in `run_proxy()`. Pass `shared_ctx` to the aiohttp `app` dict for API handlers to read live data. Serve the single HTML file from `importlib.resources` (Python 3.11+).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Embedded aiohttp server running inside the existing asyncio event loop -- no separate process
- Serves static HTML/JS/CSS + REST API endpoints for live data and config management
- Frontend: single vanilla HTML file with inline CSS/JS -- zero build step, embedded as static file in Python package
- Live data via browser-side polling with fetch() every 2 seconds -- no WebSocket/SSE complexity
- Webapp listens on port 80 (standard HTTP) -- requires CAP_NET_BIND_SERVICE (already configured for port 502 in systemd unit)
- No authentication -- all devices in same trusted LAN
- Only inverter connection settings editable via webapp: SE IP address, Modbus port, unit ID
- Other settings (poll interval, log level, night mode threshold) stay in config.yaml for advanced users via SSH
- Save to YAML + hot-reload: write new values to config.yaml, then apply changes without restarting (reconnect SE30K client with new address)
- Before saving: validate IP format/port range, then attempt a test Modbus TCP connection to the new address -- show success/failure before committing
- Side-by-side register viewer: left = SE30K source, right = Fronius target -- grouped by SunSpec model with collapsible sections
- Human-readable field names alongside register addresses, auto-refresh every 2s, flash/highlight on value change
- Compact single-page layout: status indicators at top, config section, register viewer below -- no tabs or navigation
- Connection status: colored dots (green/red/yellow) + text label
- Health metrics: service uptime, last successful poll timestamp, poll success rate (last 5 min)
- Visual style: minimal dark theme -- dark background, clean typography, monospace for register values

### Claude's Discretion
- aiohttp route structure and middleware
- REST API endpoint design (paths, response format)
- CSS styling details (exact colors, spacing, fonts within the dark theme constraint)
- Hot-reload implementation (how to reconnect SE30K client, reinitialize cache)
- How to expose shared_ctx data to API endpoints
- Error handling for API requests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WEB-01 | Webapp erreichbar ueber HTTP im LAN | aiohttp AppRunner/TCPSite on port 80, systemd CAP_NET_BIND_SERVICE |
| WEB-02 | SolarEdge IP-Adresse und Modbus-Port konfigurierbar ueber UI | REST API for config read/write, YAML save, test-connect, hot-reload |
| WEB-03 | Verbindungsstatus zu SolarEdge und Venus OS live angezeigt | shared_ctx exposes conn_mgr.state, pymodbus server tracks connected clients |
| WEB-04 | Service-Health-Status angezeigt (uptime, letzte erfolgreiche Polls) | shared_ctx exposes cache, poll_counter; compute uptime from process start |
| WEB-05 | Register-Viewer zeigt Live Modbus Register (SolarEdge-Quell- und Fronius-Ziel-Register) | cache.datablock.values for Fronius target; plugin last poll result for SE source |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | >=3.10,<4.0 | Async HTTP server + static file serving | Native asyncio, AppRunner for embedding in existing loop, no WSGI overhead |
| PyYAML | >=6.0,<7.0 (already dep) | Config read/write | Already in project dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| importlib.resources | stdlib (3.11+) | Load static HTML from package | Serve embedded HTML file without filesystem path assumptions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiohttp | Starlette/FastAPI | Heavier dependency tree (anyio, pydantic), overkill for 5 endpoints |
| aiohttp | plain asyncio HTTP | Would need to hand-roll routing, response formatting, static serving |

**Installation:**
```bash
pip install "aiohttp>=3.10,<4.0"
```

**Version verification:** aiohttp 3.13.3 is the latest stable release (verified via PyPI 2026-03-18). The `>=3.10,<4.0` range ensures compatibility with current stable while avoiding breaking changes.

## Architecture Patterns

### Recommended Project Structure
```
src/venus_os_fronius_proxy/
    webapp.py              # aiohttp app factory, routes, API handlers
    config.py              # Extended with save_config() and WebappConfig
    static/
        index.html         # Single-file frontend (HTML + inline CSS/JS)
```

### Pattern 1: Embedded aiohttp via AppRunner
**What:** Use `AppRunner`/`TCPSite` to start an aiohttp server inside the existing asyncio event loop, alongside the Modbus server and poller.
**When to use:** Always -- this is the locked decision.
**Example:**
```python
# Source: https://docs.aiohttp.org/en/stable/web_advanced.html
from aiohttp import web

async def create_webapp(shared_ctx: dict, config) -> web.AppRunner:
    app = web.Application()
    app["shared_ctx"] = shared_ctx
    app["config"] = config
    app["config_path"] = config_path
    app["start_time"] = time.monotonic()

    app.router.add_get("/", index_handler)
    app.router.add_get("/api/status", status_handler)
    app.router.add_get("/api/registers", registers_handler)
    app.router.add_get("/api/config", config_get_handler)
    app.router.add_post("/api/config", config_save_handler)
    app.router.add_post("/api/config/test", config_test_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    return runner

# In run_proxy or __main__.py:
runner = await create_webapp(shared_ctx, config)
site = web.TCPSite(runner, "0.0.0.0", 80)
await site.start()
# ... continues with existing asyncio.gather() for proxy tasks
```

### Pattern 2: Shared State via app dict
**What:** Pass `shared_ctx` dict into the aiohttp `app` dict. API handlers access it via `request.app["shared_ctx"]`.
**When to use:** For all API endpoints that need live proxy data.
**Example:**
```python
# Source: https://docs.aiohttp.org/en/stable/web_advanced.html
async def status_handler(request: web.Request) -> web.Response:
    ctx = request.app["shared_ctx"]
    cache = ctx["cache"]
    conn_mgr = ctx["conn_mgr"]
    poll_counter = ctx["poll_counter"]

    return web.json_response({
        "connection": {
            "solaredge": conn_mgr.state.value,
        },
        "health": {
            "uptime_seconds": time.monotonic() - request.app["start_time"],
            "cache_stale": cache.is_stale,
            "poll_success": poll_counter["success"],
            "poll_total": poll_counter["total"],
        },
    })
```

### Pattern 3: Config Save with Test-Connect
**What:** Before saving new inverter settings, attempt a test Modbus TCP connection to validate reachability.
**When to use:** On POST `/api/config` or POST `/api/config/test`.
**Example:**
```python
from pymodbus.client import AsyncModbusTcpClient

async def test_inverter_connection(host: str, port: int, unit_id: int) -> dict:
    """Attempt a test connection to validate inverter reachability."""
    client = AsyncModbusTcpClient(host, port=port, timeout=5)
    try:
        connected = await client.connect()
        if not connected:
            return {"success": False, "error": "Connection refused"}
        # Try reading SunSpec header to verify it's a Modbus device
        result = await client.read_holding_registers(40000, 2, slave=unit_id)
        if result.isError():
            return {"success": False, "error": f"Modbus error: {result}"}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        client.close()
```

### Pattern 4: Hot-Reload via Plugin Reconnect
**What:** After saving new config, close the current plugin connection and reconnect with new parameters.
**When to use:** When config save succeeds and test-connect passes.
**Example:**
```python
async def hot_reload_inverter(shared_ctx: dict, new_host: str, new_port: int, new_unit_id: int):
    plugin = shared_ctx["plugin"]  # Need to expose plugin in shared_ctx
    await plugin.close()
    plugin._host = new_host
    plugin._port = new_port
    plugin._unit_id = new_unit_id
    await plugin.connect()
```

### Pattern 5: Serving Embedded HTML via importlib.resources
**What:** Load the single HTML file from the Python package using `importlib.resources`, avoiding filesystem path assumptions.
**When to use:** For serving the frontend page.
**Example:**
```python
import importlib.resources

async def index_handler(request: web.Request) -> web.Response:
    ref = importlib.resources.files("venus_os_fronius_proxy.static").joinpath("index.html")
    html = ref.read_text(encoding="utf-8")
    return web.Response(text=html, content_type="text/html")
```

### Anti-Patterns to Avoid
- **Using web.run_app():** This blocks the event loop. Use AppRunner/TCPSite instead for embedding.
- **Separate process/thread for HTTP:** Adds IPC complexity. The locked decision is single-process asyncio.
- **WebSocket for live data:** Locked decision is fetch() polling every 2s. Simpler, no connection state management.
- **Global variables for shared state:** Use `app` dict pattern, not module-level globals.
- **Writing config without backup:** Always validate new config before overwriting. Consider writing to a temp file then renaming (atomic write).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP server | Raw asyncio protocol | aiohttp | Routing, static files, JSON responses, middleware -- all handled |
| JSON responses | Manual json.dumps + Response | `web.json_response()` | Sets content-type, handles encoding |
| IP validation | Custom regex | `ipaddress.ip_address()` | stdlib, handles IPv4/IPv6, edge cases |
| Port validation | Custom range check | Simple `1 <= port <= 65535` | Trivial but don't forget it |
| Atomic file write | Direct open/write | `tempfile` + `os.replace()` | Prevents partial writes on crash |
| SunSpec field names | Hardcoded strings in JS | JSON lookup table served from Python | Single source of truth from register-mapping-spec |

**Key insight:** The frontend is intentionally minimal (single vanilla HTML file). The complexity is in the backend API, not in frontend framework choices.

## Common Pitfalls

### Pitfall 1: systemd ReadOnlyPaths blocks config writes
**What goes wrong:** The current systemd unit has `ReadOnlyPaths=/etc/venus-os-fronius-proxy`. Writing config.yaml will fail with `PermissionError`.
**Why it happens:** Phase 3 set up read-only protection for the config directory.
**How to avoid:** Change `ReadOnlyPaths` to `ReadWritePaths=/etc/venus-os-fronius-proxy` in the systemd unit, since the webapp now needs write access. Or keep ReadOnlyPaths and add `ReadWritePaths` to override just the config file.
**Warning signs:** Config save returns 500 error in production but works in development.

### Pitfall 2: Port 80 requires CAP_NET_BIND_SERVICE
**What goes wrong:** aiohttp fails to bind to port 80.
**Why it happens:** Ports below 1024 require elevated capabilities.
**How to avoid:** `CAP_NET_BIND_SERVICE` is already configured in the systemd unit (for port 502). Verify it covers the webapp port too -- it does, since it's an ambient capability on the process, not per-port.
**Warning signs:** `OSError: [Errno 13] Permission denied` on startup.

### Pitfall 3: Race condition between test-connect and save
**What goes wrong:** User triggers test-connect, it succeeds, but by the time save happens the inverter is unreachable.
**Why it happens:** Network conditions change between test and save.
**How to avoid:** Accept this as inherent -- the test is best-effort validation, not a guarantee. The save should proceed even if the network changes. The proxy's existing reconnection logic (ConnectionManager) handles runtime failures.
**Warning signs:** N/A -- design-level acceptance.

### Pitfall 4: SolarEdgePlugin has no host/port setter
**What goes wrong:** Hot-reload tries to update plugin connection params but the plugin stores them as private attributes set in `__init__`.
**Why it happens:** Plugin was designed for single-connection lifecycle.
**How to avoid:** Add a `reconfigure(host, port, unit_id)` method to InverterPlugin ABC and SolarEdgePlugin, or directly set private attributes (less clean but pragmatic). Alternatively, create a new plugin instance entirely.
**Warning signs:** AttributeError or connection still goes to old address after config save.

### Pitfall 5: Frontend polling continues during config save
**What goes wrong:** While config save + reconnect is in progress, the status API returns stale/error data, causing confusing UI flicker.
**Why it happens:** The 2-second polling cycle doesn't pause during config operations.
**How to avoid:** Add a "reconfiguring" state to the API response during hot-reload. Frontend shows a "Reconnecting..." indicator instead of error.
**Warning signs:** Green->Red->Green status flicker during config save.

### Pitfall 6: Venus OS client count not directly available
**What goes wrong:** WEB-03 requires showing Venus OS connection status, but pymodbus server doesn't expose a simple "connected clients" count.
**Why it happens:** pymodbus ModbusTcpServer manages connections internally.
**How to avoid:** Track Venus OS connection state indirectly -- if the server is running and recent reads have been served, Venus OS is connected. Alternatively, check `server.active_connections` if the pymodbus version supports it, or wrap the server context to count reads.
**Warning signs:** Status shows "Venus OS: Unknown" because there's no client count API.

## Code Examples

### Register Viewer Data Structure
The register viewer needs to map register addresses to human-readable names grouped by SunSpec model. This data should be defined in Python and served as JSON.

```python
# Source: docs/register-mapping-spec.md
REGISTER_MODELS = [
    {
        "name": "Common (Model 1)",
        "start": 40002,
        "fields": [
            {"addr": 40002, "name": "DID", "size": 1},
            {"addr": 40003, "name": "Length", "size": 1},
            {"addr": 40004, "name": "Manufacturer", "size": 16, "type": "string"},
            {"addr": 40020, "name": "Model", "size": 16, "type": "string"},
            {"addr": 40036, "name": "Options", "size": 8, "type": "string"},
            {"addr": 40044, "name": "Version", "size": 8, "type": "string"},
            {"addr": 40052, "name": "Serial Number", "size": 16, "type": "string"},
            {"addr": 40068, "name": "Device Address", "size": 1},
        ],
    },
    {
        "name": "Inverter (Model 103)",
        "start": 40069,
        "fields": [
            {"addr": 40069, "name": "DID", "size": 1},
            {"addr": 40070, "name": "Length", "size": 1},
            {"addr": 40071, "name": "AC Current", "size": 1, "unit": "A"},
            {"addr": 40072, "name": "AC Current A", "size": 1, "unit": "A"},
            {"addr": 40073, "name": "AC Current B", "size": 1, "unit": "A"},
            {"addr": 40074, "name": "AC Current C", "size": 1, "unit": "A"},
            {"addr": 40075, "name": "AC Current SF", "size": 1, "sf": True},
            {"addr": 40076, "name": "AC Voltage AB", "size": 1, "unit": "V"},
            # ... etc for all 52 registers
            {"addr": 40083, "name": "AC Power", "size": 1, "unit": "W"},
            {"addr": 40084, "name": "AC Power SF", "size": 1, "sf": True},
            {"addr": 40085, "name": "AC Frequency", "size": 1, "unit": "Hz"},
            {"addr": 40107, "name": "Status", "size": 1},
        ],
    },
    {
        "name": "Nameplate (Model 120)",
        "start": 40121,
        "fields": [
            {"addr": 40121, "name": "DID", "size": 1},
            {"addr": 40122, "name": "Length", "size": 1},
            {"addr": 40123, "name": "DER Type", "size": 1},
            {"addr": 40124, "name": "W Rating", "size": 1, "unit": "W"},
            # ... etc
        ],
    },
    {
        "name": "Controls (Model 123)",
        "start": 40149,
        "fields": [
            {"addr": 40149, "name": "DID", "size": 1},
            {"addr": 40150, "name": "Length", "size": 1},
            {"addr": 40154, "name": "WMaxLimPct", "size": 1, "unit": "%"},
            {"addr": 40158, "name": "WMaxLim_Ena", "size": 1},
        ],
    },
]
```

### YAML Config Save with Atomic Write
```python
import os
import tempfile
import yaml

def save_config(config_path: str, config_data: dict) -> None:
    """Atomically write config to YAML file."""
    dir_path = os.path.dirname(config_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".yaml")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
        os.replace(tmp_path, config_path)  # Atomic on POSIX
    except Exception:
        os.unlink(tmp_path)
        raise
```

### API Response Format (Recommended)
```json
{
    "status": {
        "solaredge": "connected",
        "venus_os": "active"
    },
    "health": {
        "uptime_seconds": 86432,
        "last_poll_success": "2026-03-18T14:30:12Z",
        "poll_success_rate": 99.8,
        "cache_stale": false
    },
    "config": {
        "inverter": {
            "host": "192.168.3.18",
            "port": 1502,
            "unit_id": 1
        }
    }
}
```

### Frontend Dark Theme CSS Base
```css
:root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --border: #0f3460;
    --text: #e0e0e0;
    --text-dim: #8888aa;
    --accent: #e94560;
    --green: #00c853;
    --red: #ff1744;
    --yellow: #ffab00;
    --mono: 'Courier New', monospace;
}
body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    margin: 0; padding: 20px;
}
.register-value { font-family: var(--mono); }
.status-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.status-dot.green { background: var(--green); }
.status-dot.red { background: var(--red); }
.status-dot.yellow { background: var(--yellow); }
@keyframes flash { 0% { background: var(--accent); } 100% { background: transparent; } }
.changed { animation: flash 0.5s ease-out; }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| aiohttp `make_handler()` | `AppRunner`/`TCPSite` | aiohttp 3.0+ | Must use new API, old pattern is removed |
| `pkg_resources` for package data | `importlib.resources` | Python 3.9+ | Faster, no setuptools dependency |
| `loop.run_until_complete()` | `asyncio.run()` + async setup | Python 3.10+ | Cleaner event loop management |

**Deprecated/outdated:**
- `aiohttp.web.run_app()` is NOT deprecated but is blocking -- don't use when embedding in existing loop
- `pkg_resources` is deprecated for resource loading -- use `importlib.resources`

## Open Questions

1. **Venus OS client count**
   - What we know: pymodbus ModbusTcpServer manages TCP connections internally
   - What's unclear: Whether pymodbus 3.x exposes active connection count or callback hooks
   - Recommendation: Show "Venus OS: Server Running" when the Modbus server is up, and track "last read timestamp" by instrumenting `StalenessAwareSlaveContext.getValues()`. If a read happened recently, Venus OS is connected.

2. **SE30K source registers for register viewer**
   - What we know: `cache.datablock` has the translated Fronius target registers. The raw SE30K source registers are in the plugin's last poll result.
   - What's unclear: SolarEdgePlugin doesn't currently expose last raw poll data.
   - Recommendation: Store last raw SE30K poll result in `shared_ctx["last_se_poll"]` during `_poll_loop`. The register viewer left column reads this, right column reads `cache.datablock`.

3. **Plugin reconfigure API**
   - What we know: `SolarEdgePlugin.__init__` sets host/port/unit_id. `close()` sets `_client = None`.
   - What's unclear: Whether creating a new plugin instance is cleaner than mutating the existing one.
   - Recommendation: Add a `reconfigure(host, port, unit_id)` method that calls `close()`, updates params, and does NOT call `connect()` (the poll loop will reconnect naturally via ConnectionManager).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WEB-01 | aiohttp server starts and serves HTML on configured port | integration | `python -m pytest tests/test_webapp.py::test_server_starts -x` | No -- Wave 0 |
| WEB-02 | Config GET returns current config, POST validates + saves + reloads | unit+integration | `python -m pytest tests/test_webapp.py::test_config_endpoints -x` | No -- Wave 0 |
| WEB-03 | Status API returns connection state for SE and Venus OS | unit | `python -m pytest tests/test_webapp.py::test_status_endpoint -x` | No -- Wave 0 |
| WEB-04 | Health API returns uptime, poll stats, cache staleness | unit | `python -m pytest tests/test_webapp.py::test_health_endpoint -x` | No -- Wave 0 |
| WEB-05 | Register API returns grouped register data with field names | unit | `python -m pytest tests/test_webapp.py::test_register_endpoint -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_webapp.py` -- covers WEB-01 through WEB-05 (API handler tests using aiohttp test client)
- [ ] `tests/test_config_save.py` -- covers config write/reload logic (unit tests for save_config, validate_config)
- [ ] aiohttp dev dependency: add `aiohttp>=3.10,<4.0` to `[project.optional-dependencies].dev` or main deps

## Sources

### Primary (HIGH confidence)
- [aiohttp Web Server Advanced](https://docs.aiohttp.org/en/stable/web_advanced.html) -- AppRunner/TCPSite pattern, static files, app dict, middleware
- [aiohttp Server Reference](https://docs.aiohttp.org/en/stable/web_reference.html) -- API signatures for AppRunner, TCPSite, json_response, lifecycle hooks
- PyPI aiohttp 3.13.3 -- version verified 2026-03-18

### Secondary (MEDIUM confidence)
- Project source: `proxy.py`, `__main__.py`, `config.py`, `connection.py` -- verified integration points and shared_ctx pattern
- `docs/register-mapping-spec.md` -- full register layout for register viewer data model
- `config/venus-os-fronius-proxy.service` -- systemd unit with ReadOnlyPaths and CAP_NET_BIND_SERVICE

### Tertiary (LOW confidence)
- Venus OS client count via pymodbus -- no official docs found on exposing active connections; workaround documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- aiohttp is the locked decision, version verified on PyPI
- Architecture: HIGH -- AppRunner/TCPSite pattern verified in official docs, shared_ctx pattern exists in codebase
- Pitfalls: HIGH -- systemd ReadOnlyPaths and CAP_NET_BIND_SERVICE verified from existing service file
- Register viewer: MEDIUM -- data model derived from register-mapping-spec, but SE source register exposure needs implementation

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain, no fast-moving dependencies)
