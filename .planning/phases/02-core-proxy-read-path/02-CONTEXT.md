# Phase 2: Core Proxy (Read Path) - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Modbus TCP proxy that makes Venus OS discover and monitor the SolarEdge SE30K as a Fronius inverter. Covers: Modbus TCP server, SunSpec model chain serving, async SolarEdge polling, register cache, register translation, plugin interface for inverter brands. Does NOT cover: power control/write path (Phase 3), systemd service (Phase 3), webapp (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Polling & Caching
- Poll SE30K every 1 second (matches typical dbus-fronius polling rate, needed for ESS control loops)
- Full batch poll — read all needed registers (Common + Inverter model, ~120 registers) in one cycle, not on-demand
- Serve stale cache when SE30K is slow/unresponsive — keep serving last known values, mark staleness internally for logging
- Cache staleness timeout: 30 seconds — after 30s without a successful poll, start returning Modbus errors to Venus OS
- Polling runs asynchronously, independent of Venus OS request handling

### Venus OS Integration
- Proxy listens on port 502 (standard Modbus TCP) — requires root or CAP_NET_BIND_SERVICE on the LXC
- Proxy responds to Modbus unit ID 126 (Fronius convention, dbus-fronius scans for this)
- Support multiple simultaneous TCP connections (Venus OS + future config webapp register viewer)
- Bind to 0.0.0.0 (all interfaces) — all devices in same trusted LAN, no restriction needed

### Claude's Discretion
- Plugin interface design (ABC class vs protocol, method signatures, how brand-specific config is loaded)
- Error handling strategy for connection failures and edge cases
- Nighttime/sleeping inverter behavior (basic handling needed, production hardening in Phase 3)
- Async framework choice (asyncio with pymodbus async server is the obvious fit)
- Register translation implementation (lookup table, class hierarchy, etc.)
- How to handle concurrent Venus OS reads while polling is in progress (cache serves reads, no locking needed if using asyncio single-thread)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Protocol Specifications
- `docs/dbus-fronius-expectations.md` — Discovery flow, required SunSpec models, unit ID 126, Fronius-specific behaviors, proxy emulation checklist
- `docs/register-mapping-spec.md` — Register-by-register translation table (176 registers), translation types, scale factor math
- `docs/se30k-validation-results.md` — Live-validated register layout, model chain structure, Model 704 discovery

### Phase 1 Outputs
- `.planning/phases/01-protocol-research-validation/01-01-SUMMARY.md` — Project scaffolding decisions, register address calculations
- `.planning/phases/01-protocol-research-validation/01-02-SUMMARY.md` — Live validation findings, confirmed Model 120/123 absence
- `.planning/phases/01-protocol-research-validation/01-RESEARCH.md` — Protocol research findings

### Test Infrastructure
- `tests/test_register_mapping.py` — 27 unit tests for register mapping correctness (addresses, translation, scale factors)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_register_mapping.py` — 27 tests defining expected register behavior; proxy implementation must pass these
- `scripts/validate_se30k.py` — Reference for pymodbus ModbusTcpClient usage, register reading patterns, SunSpec model chain walking

### Established Patterns
- pymodbus is the chosen Modbus library (used in validation script, listed in pyproject.toml)
- SunSpec model chain walk pattern established in validate_se30k.py
- Register address calculations documented in register-mapping-spec.md

### Integration Points
- SE30K at 192.168.3.18:1502 (unit ID 1) — upstream data source
- Venus OS at 192.168.3.146 — downstream consumer, expects Fronius on port 502 unit ID 126
- LXC at 192.168.3.191 — deployment target

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

*Phase: 02-core-proxy-read-path*
*Context gathered: 2026-03-18*
