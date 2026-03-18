# Phase 4: Configuration Webapp - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Web-based configuration and monitoring interface for the proxy. Users can configure the SolarEdge inverter connection, view live connection status and service health, and inspect raw/translated Modbus registers — all without SSH access. Does NOT cover: log viewer (v2 WEB-10), multi-inverter management (v2 WEB-11), auto-discovery (v2 WEB-12).

</domain>

<decisions>
## Implementation Decisions

### Web Framework & Delivery
- Embedded aiohttp server running inside the existing asyncio event loop — no separate process
- Serves static HTML/JS/CSS + REST API endpoints for live data and config management
- Frontend: single vanilla HTML file with inline CSS/JS — zero build step, embedded as static file in Python package
- Live data via browser-side polling with fetch() every 2 seconds — no WebSocket/SSE complexity
- Webapp listens on port 80 (standard HTTP) — requires CAP_NET_BIND_SERVICE (already configured for port 502 in systemd unit)
- No authentication — all devices in same trusted LAN (per REQUIREMENTS out-of-scope)

### Config Editing Flow
- Only inverter connection settings editable via webapp: SE IP address, Modbus port, unit ID
- Other settings (poll interval, log level, night mode threshold) stay in config.yaml for advanced users via SSH
- Save to YAML + hot-reload: write new values to config.yaml, then apply changes without restarting (reconnect SE30K client with new address)
- Before saving: validate IP format/port range, then attempt a test Modbus TCP connection to the new address — show success/failure before committing
- Webapp reads config.yaml on page load — manual YAML edits via SSH are picked up on next page load, no file watcher

### Register Viewer Design
- Side-by-side columns: left = SE30K source registers, right = Fronius target registers — makes translation visible at a glance
- Registers grouped by SunSpec model (Common, Inverter 103, Nameplate 120, Controls 123) with collapsible sections
- Human-readable field names (e.g., "AC Power" not just "40083") alongside register addresses
- Auto-refresh every 2 seconds via fetch() polling
- Flash/highlight animation when a register value changes — easy to spot live updates

### Status Dashboard Layout
- Compact single-page layout: status indicators at top, config section, register viewer below — no tabs or navigation
- Connection status: colored dots (green/red/yellow) + text label ("SolarEdge: Connected", "Venus OS: 2 clients")
- Health metrics: service uptime, last successful poll timestamp, poll success rate (last 5 min) — maps to Phase 3 health heartbeat data
- Visual style: minimal dark theme — dark background, clean typography, monospace for register values. Technical/industrial feel for a solar monitoring tool.

### Claude's Discretion
- aiohttp route structure and middleware
- REST API endpoint design (paths, response format)
- CSS styling details (exact colors, spacing, fonts within the dark theme constraint)
- Hot-reload implementation (how to reconnect SE30K client, reinitialize cache)
- How to expose shared_ctx data to API endpoints
- Error handling for API requests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Register Specifications
- `docs/register-mapping-spec.md` — Full 176-register translation table, SunSpec model structure, field names and descriptions for register viewer
- `docs/dbus-fronius-expectations.md` — SunSpec model chain structure, model IDs for grouping

### Phase 3 Outputs (foundations to extend)
- `src/venus_os_fronius_proxy/config.py` — Config dataclass schema, YAML loading, `load_config()` — extend for webapp port, add save capability
- `src/venus_os_fronius_proxy/__main__.py` — Entry point with asyncio loop, shared_ctx pattern — extend to launch aiohttp server
- `src/venus_os_fronius_proxy/proxy.py` — `run_proxy()` with shared_ctx dict exposing runtime state (cache, control_state, conn_mgr)
- `src/venus_os_fronius_proxy/connection.py` — ConnectionManager with state machine (CONNECTED/STALE/NIGHT_MODE) for status display
- `config/config.example.yaml` — Current config schema to extend with webapp section

### Existing Infrastructure
- `config/venus-os-fronius-proxy.service` — systemd unit with CAP_NET_BIND_SERVICE — needs port 80 added
- `src/venus_os_fronius_proxy/logging_config.py` — Structured logging config for consistent log output from webapp

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared_ctx` dict in `run_proxy()`: Already exposes `cache`, `control_state`, `conn_mgr`, `poll_counter` — webapp API can read these directly
- `RegisterCache.datablock`: Contains all 177 Fronius target registers — can be read for register viewer
- `ConnectionManager.state`: Enum (CONNECTED/STALE/NIGHT_MODE) — maps directly to status dots
- `config.py` `load_config()`: Reads YAML and returns dataclass — extend with `save_config()` for write-back
- `InverterPlugin.connect()/close()`: Can be called for hot-reload reconnection

### Established Patterns
- asyncio single-thread model — aiohttp fits naturally as another coroutine in the event loop
- YAML config with dataclass schema — extend for webapp port
- Health heartbeat metrics already computed (poll_success_rate, cache_age) — reuse for API

### Integration Points
- asyncio event loop in `__main__.py` — add aiohttp server alongside proxy
- `shared_ctx` dict — bridge between proxy internals and webapp API
- `config.yaml` — single source of truth for all configuration
- systemd unit — add port 80 to AmbientCapabilities scope

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-configuration-webapp*
*Context gathered: 2026-03-18*
