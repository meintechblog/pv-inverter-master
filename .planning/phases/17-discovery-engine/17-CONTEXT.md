# Phase 17: Discovery Engine - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend network scanner that autonomously finds and identifies SunSpec-compatible inverters on the local network. Reads manufacturer, model, serial, firmware from SunSpec Common Block. No UI in this phase — that's Phase 20.

</domain>

<decisions>
## Implementation Decisions

### Scan Behavior & Timing
- Already-configured inverter IPs are SKIPPED during scan — no conflict with active polling
- Scan parallelism: 10-20 concurrent TCP connections via asyncio semaphore
- TCP timeout per IP: 0.5s (LAN devices respond under 50ms)
- Sequential Modbus reads after TCP connect (one at a time per host due to SolarEdge single-connection constraint)

### Ergebnis-Datenmodell
- Scanner returns ALL SunSpec-compatible devices, not just SolarEdge
- Non-SolarEdge devices are marked as "not yet supported" (plugin architecture exists but only SolarEdge tested)
- Data per discovered device: IP, Port, Unit ID, Manufacturer, Model, Serial Number, Firmware Version (full SunSpec Common Block)
- Supported flag: true if manufacturer == "SolarEdge", false otherwise

### Subnet-Erkennung
- Auto-detect from local network interface — no user input required
- Use first non-loopback, non-link-local interface (filter out 127.x and 169.254.x)
- On LXC typically only one real interface (eth0)
- No multi-subnet scanning — single detected subnet only

### Additional Context from User
- After successful inverter connection, Config page should show Manufacturer + Model inline (schlank, nur diese zwei Infos) — this applies to Phase 19 UI but scanner must provide this data
- Develop directly on production LXC at 192.168.3.191:80

### Claude's Discretion
- Exact asyncio concurrency pattern (Semaphore size within 10-20 range)
- Error handling for edge cases (partial Common Block reads, corrupted data)
- Logging verbosity during scan
- SunSpec verification details (how strict to validate DID/Length)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SunSpec Protocol
- `src/venus_os_fronius_proxy/sunspec_models.py` — Existing SunSpec register constants (SUNSPEC_HEADER_ADDR=40000, COMMON_ADDR=40002, COMMON_DID=1, COMMON_LENGTH=65), encode_string() helper
- SunSpec Common Block: Model 1 at register 40002, Manufacturer offset 2-17 (16 regs), Model offset 18-33 (16 regs), Serial offset 50-65 (16 regs), Firmware offset 42-49 (8 regs)

### Modbus Client Pattern
- `src/venus_os_fronius_proxy/plugins/solaredge.py` — AsyncModbusTcpClient usage, read_holding_registers(), error handling pattern
- `src/venus_os_fronius_proxy/connection.py` — ConnectionManager state machine, reconnection patterns

### Config & API
- `src/venus_os_fronius_proxy/config.py` — InverterConfig dataclass, validate_inverter_config(), load_config/save_config pattern
- `src/venus_os_fronius_proxy/webapp.py` — REST endpoint patterns, shared_ctx access, json_response format

### WebSocket
- `src/venus_os_fronius_proxy/webapp.py` lines 452-515 — ws_handler(), broadcast_to_clients() pattern for real-time progress updates

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsyncModbusTcpClient` from pymodbus: same library already in use, same connect/read pattern
- `sunspec_models.py` constants: SUNSPEC_HEADER_ADDR, COMMON_ADDR, COMMON_DID, COMMON_LENGTH, encode_string()
- `validate_inverter_config()`: can validate discovered devices before adding to config
- `webapp.py` REST endpoint pattern: json_response, shared_ctx, error handling
- WebSocket broadcast infrastructure: existing ws_clients set + broadcast_to_clients()

### Established Patterns
- Dataclasses for all data structures (InverterConfig, VenusConfig, etc.)
- Structlog for logging (not print or plain logging)
- asyncio throughout — no threads
- Validation functions return error string or None
- Atomic config save via temp file + os.replace()

### Integration Points
- New `scanner.py` module in `src/venus_os_fronius_proxy/`
- REST endpoint `/api/scanner/discover` in webapp.py
- WebSocket progress messages via existing broadcast infrastructure
- Scanner results stored in shared_ctx for API access
- Config skip-list: read current InverterConfig to exclude configured IPs

</code_context>

<specifics>
## Specific Ideas

- Scanner should feel instant on LXC — 0.5s timeout + 10-20 parallel = full /24 subnet in ~15s
- "SunS" magic check at register 40000 is the gatekeeper — no SunS, no further reads
- Unit ID scan: always try 1, then optionally 2-10 for RS485 chains behind gateways

</specifics>

<deferred>
## Deferred Ideas

- Manufacturer + Model inline display in Config page — Phase 19 (Inverter Management UI)
- Production LXC development setup (192.168.3.191:80) — operational concern, not phase-specific

</deferred>

---

*Phase: 17-discovery-engine*
*Context gathered: 2026-03-20*
