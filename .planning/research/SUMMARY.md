# Research Summary: Venus OS Fronius Proxy

**Domain:** Modbus TCP Proxy -- Inverter Protocol Translation (SolarEdge -> Fronius SunSpec emulation for Venus OS)
**Researched:** 2026-03-17
**Overall confidence:** MEDIUM

## Executive Summary

This project builds a Modbus TCP translation proxy that makes a SolarEdge SE30K three-phase inverter appear as a Fronius inverter to Venus OS (Victron). Venus OS natively supports Fronius inverters via its `dbus-fronius` driver, which expects SunSpec-compliant Modbus TCP communication. The proxy reads SolarEdge registers, translates them to Fronius-compatible SunSpec register layout, and serves them to Venus OS. It also handles the reverse path: power limiting commands from Venus OS are translated back to SolarEdge commands.

The stack is Python 3.12+ with pymodbus (3.8.x) for both Modbus TCP client and server, FastAPI + Jinja2 + htmx for a lightweight config webapp, and systemd for process management. All components run in a single asyncio event loop within one process -- appropriate for the I/O-bound, low-traffic nature of this workload. The architecture uses a polling model (not pass-through proxy) because SolarEdge and Fronius use different SunSpec register layouts that cannot be transparently relayed.

The most critical risk is that Venus OS's `dbus-fronius` driver may have Fronius-specific expectations beyond standard SunSpec compliance -- including manufacturer string matching, specific SunSpec model ordering, or reliance on the Fronius Solar API (HTTP) for power control instead of Modbus TCP. This must be verified by reading the `dbus-fronius` source code before any implementation begins. All library versions have been verified via PyPI.

## Key Findings

**Stack:** Python 3.12+ / pymodbus 3.8.x / FastAPI 0.128.x / uvicorn / Pydantic / TOML / systemd / uv. Single-process async architecture.

**Architecture:** Polling proxy (not pass-through). Three async subsystems on one event loop: Modbus client (polls SolarEdge), Modbus server (serves Venus OS), HTTP server (config webapp). Plugin interface for future inverter brands.

**Critical pitfall:** Venus OS `dbus-fronius` may require Fronius-specific behavior beyond SunSpec compliance. Must read `dbus-fronius` source code before writing any proxy code. This is the single biggest schedule/scope risk.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Research and Validation** - Verify critical unknowns before writing production code
   - Addresses: dbus-fronius discovery protocol, power control mechanism (Modbus vs HTTP), SolarEdge register map validation
   - Avoids: Building on wrong assumptions (Pitfalls 2, 7)
   - Output: Validated register mapping specification, confirmed discovery protocol

2. **Phase 2: Core Proxy (Read Path)** - Config + Modbus client + register translation + Modbus server
   - Addresses: All table-stakes features for monitoring (read path only)
   - Avoids: SunSpec model chain errors (Pitfall 1), address offset bugs (Pitfall 10), endianness issues (Pitfall 4)
   - Milestone: Venus OS discovers and monitors the SolarEdge inverter through the proxy

3. **Phase 3: Control Path** - Power limiting write path from Venus OS through proxy to SolarEdge
   - Addresses: Power curtailment feature (model 123 or HTTP, depending on Phase 1 findings)
   - Avoids: Wrong control mechanism (Pitfall 7), scale factor errors on writes (Pitfall 5)
   - Milestone: Venus OS can throttle SolarEdge output

4. **Phase 4: Operational** - Config webapp, health monitoring, systemd hardening, nighttime handling
   - Addresses: Differentiator features (webapp, status display, register viewer)
   - Avoids: Stale data at night (Pitfall 8), restart issues (Pitfall 14)
   - Milestone: Production-ready with web-based configuration

5. **Phase 5: Extensibility** - Plugin architecture formalization, documentation for adding inverter brands
   - Addresses: Future brand support requirement
   - Avoids: Over-engineering before first integration works (per Pitfalls phase warning)

**Phase ordering rationale:**
- Phase 1 (research) first because the entire architecture depends on knowing what `dbus-fronius` actually expects. Building before verifying risks rewrites.
- Phase 2 before Phase 3 because the read path is simpler and validates the entire translation approach before adding the more dangerous write path.
- Phase 4 after core functionality because the config webapp is not needed for initial validation (TOML + SSH suffice).
- Phase 5 last because the plugin interface should be extracted from a working implementation, not designed in the abstract.

**Research flags for phases:**
- Phase 1: REQUIRES deep research -- reading dbus-fronius source code, capturing Modbus traffic from real Fronius if possible
- Phase 2: Standard patterns once Phase 1 questions are answered. pymodbus docs will be needed.
- Phase 3: Likely needs research -- SolarEdge power limiting via Modbus may have quirks
- Phase 4: Standard patterns, unlikely to need additional research
- Phase 5: Low research needs, mostly design work

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified via PyPI. pymodbus is the undisputed Python Modbus library. FastAPI + Jinja2 is well-proven for config UIs. |
| Features | HIGH | SunSpec models are standardized. Table-stakes features are clear from the project requirements. |
| Architecture | MEDIUM | Single-process async design is sound. Register translation approach is correct. But the exact SunSpec model expectations of dbus-fronius are unverified. |
| Pitfalls | MEDIUM | Training-data-based knowledge of SolarEdge/Fronius quirks. Most pitfalls are well-known in the Modbus community, but Fronius-specific behaviors need verification. |

## Gaps to Address

- **dbus-fronius source code review** -- Must happen before Phase 2. Determines: manufacturer string requirements, SunSpec model expectations, discovery protocol (Modbus only vs HTTP Solar API), power control mechanism
- **SolarEdge SE30K register verification** -- Read actual registers from the inverter and compare against documentation. Especially important for scale factors and three-phase register layout
- **Venus OS version-specific behavior** -- The exact Venus OS version on 192.168.3.146 may affect which dbus-fronius features are present
- **SolarEdge concurrent connection limit** -- Need to verify how many Modbus TCP connections the SE30K firmware allows
- **htmx version** -- Version claimed from training data, should verify latest stable when building the webapp

## Sources

All package versions verified via PyPI (`pip3 index versions`). Architecture and domain knowledge from training data (cutoff ~May 2025). Web search and web fetch were unavailable during this research session, so dbus-fronius source code review and Fronius-specific integration details could not be verified live.
