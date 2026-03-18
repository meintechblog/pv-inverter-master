# Phase 3: Control Path & Production Hardening - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Write path for Venus OS power control via SunSpec Model 123, translated to SolarEdge proprietary registers. Production hardening: systemd service, automatic reconnection with exponential backoff, night/sleeping inverter handling, structured JSON logging. Does NOT cover: webapp (Phase 4), multi-inverter (v2), scheduled power limiting (v2).

</domain>

<decisions>
## Implementation Decisions

### Power Limit Behavior
- Forward WMaxLimPct writes immediately to SE30K proprietary registers — no proxy-side ramping (SolarEdge firmware handles its own internal ramp)
- Reject invalid values (>100%, negative, NaN) with Modbus ILLEGAL_DATA_VALUE (0x03) exception — never forward bad values to inverter
- Model 123 registers are readable — proxy stores last-written WMaxLimPct and returns it on read
- WMaxLim_Ena defaults to DISABLED (0) on proxy startup — Venus OS must explicitly enable throttling before power limits take effect
- On graceful shutdown (SIGTERM): send WMaxLimPct=100% (no limit) to SE30K before stopping
- After reconnect: restore last-set power limit to SE30K

### Reconnection & Night Mode
- Exponential backoff on connection loss: start at 5s, double each attempt, max 60s, reset to 5s after successful reconnect
- Night/sleeping detection: if SE30K connection fails consistently for >5 minutes, enter night mode
- Night mode behavior: serve zero-power registers (AC power=0, energy unchanged, inverter status=SLEEPING/4), keep SunSpec model chain intact — no staleness errors
- Short outages (<5 min): use existing 30s staleness timeout from Phase 2 (return Modbus errors)
- Exit night mode when SE30K becomes reachable again — resume normal polling

### Logging & Observability
- JSON structured logging to stdout (systemd journal captures it)
- Log fields: timestamp, level, message, component (poller/server/control/health)
- INFO level events: startup/shutdown with config summary, connection state changes (connect/disconnect/reconnect/night mode), every control command (power limit writes with value + result), health heartbeat every 5 minutes
- Health heartbeat includes: poll success rate, cache age, active connections count, last control value
- DEBUG level: per-poll register dumps (raw SE30K values + translated Fronius values) — only visible when explicitly enabled
- WARNING level: validation rejections, reconnect attempts, staleness events
- ERROR level: unrecoverable failures, repeated reconnect failures

### Service Lifecycle
- YAML config file at /etc/venus-os-fronius-proxy/config.yaml — SE30K IP/port, poll interval, log level, night mode timeout
- systemd unit: Restart=on-failure, RestartSec=5, clean shutdown on SIGTERM doesn't trigger restart
- Run as dedicated user with AmbientCapabilities=CAP_NET_BIND_SERVICE for port 502 binding
- Graceful shutdown: catch SIGTERM, remove power limit from SE30K (set 100%), close connections, exit 0

### Claude's Discretion
- Plugin interface extension for write path (add write method to InverterPlugin ABC)
- YAML config schema and defaults
- Exact systemd unit file structure (After=, Wants=, etc.)
- Night mode state machine implementation details
- Python logging configuration (structlog vs stdlib json formatter)
- How to handle concurrent control writes (queue vs last-write-wins)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Control Path Specification
- `docs/register-mapping-spec.md` — Model 123 write translation table, SE30K proprietary power control registers (0xF300-0xF322), WMaxLimPct mapping
- `docs/dbus-fronius-expectations.md` — How Venus OS ESS writes Model 123, expected register behavior

### Phase 2 Outputs (foundations to extend)
- `src/venus_os_fronius_proxy/plugin.py` — InverterPlugin ABC to extend with write method
- `src/venus_os_fronius_proxy/proxy.py` — Proxy server to extend with write handler, StalenessAwareSlaveContext
- `src/venus_os_fronius_proxy/plugins/solaredge.py` — SolarEdge plugin to extend with write capability
- `src/venus_os_fronius_proxy/register_cache.py` — RegisterCache to extend with write-back tracking

### Validation
- `docs/se30k-validation-results.md` — Live-validated register layout, Model 704 DER Controls discovery

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `InverterPlugin` ABC: Already defines connect/poll/close — needs write method addition
- `StalenessAwareSlaveContext`: Intercepts reads, can be extended to intercept writes for control path
- `RegisterCache`: Wraps ModbusSequentialDataBlock, can be extended to track written values
- `proxy.py run_proxy()`: Async server+poller orchestration — needs control path and reconnection logic

### Established Patterns
- asyncio single-thread model — no locking needed for concurrent access
- pymodbus 3.8.6 for both client (SE30K polling) and server (Venus OS serving)
- TDD with pytest — 101 tests passing, test infrastructure established
- Each integration test uses unique port via _next_port() to avoid TCP TIME_WAIT conflicts

### Integration Points
- SE30K at 192.168.3.18:1502 (unit ID 1) — upstream target for write-through
- Venus OS at 192.168.3.146 — writes Model 123 registers for ESS control
- LXC at 192.168.3.191 — deployment target for systemd service

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

*Phase: 03-control-path-production-hardening*
*Context gathered: 2026-03-18*
