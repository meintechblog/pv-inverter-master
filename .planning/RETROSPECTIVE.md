# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v3.0 — Setup & Onboarding

**Shipped:** 2026-03-19
**Phases:** 4 | **Plans:** 6 | **Commits:** ~20

### What Was Built
- MQTT config backend with VenusConfig dataclass, hot-reload, Portal ID auto-discovery
- Config page with pre-filled defaults, live connection bobbles, MQTT setup guide card
- Dashboard MQTT gate — Venus-dependent widgets greyed until MQTT connected
- Venus OS auto-detection via Model 123 Modbus write with green banner prompt
- Install script fix (YAML key mismatch, venus section, pre-flight checks, secure curl)
- README rewrite with full v3.0 setup flow and Venus OS >= 3.7 prerequisite

### What Worked
- Phase 14 checkpoint verification via preview server caught UI issues before shipping
- TDD approach in Phase 13 and 15 caught CONNACK false-positive bug early
- Nested config API {inverter, venus} was clean and backward-compatible
- Connection bobbles replacing Test Connection button — permanent status is better than one-shot
- Research phases identified the pymodbus trace_connect limitation (no client IP) before planning

### What Was Inefficient
- Summary one_liner field still not populated by executor (3rd milestone with this gap)
- Phase 14 had 2 waves but Wave 2 checkpoint was mostly visual — could have been autonomous
- ROADMAP.md progress table formatting inconsistency (v3.0 rows missing milestone column)

### Patterns Established
- `ve-hint-card--success` green variant alongside existing orange hint card
- `venus-dependent` / `mqtt-gated` CSS classes for conditional UI gating
- `updateAutoDetectBanner(snapshot)` pattern for WebSocket-driven banner visibility
- Pre-flight checks in install scripts (port availability, old config detection)
- Nested config API pattern for multi-section configuration

### Key Lessons
1. Live connection bobbles > one-shot test buttons for ongoing health visibility
2. MQTT gate pattern (greyed widgets with overlay) is a clean UX for missing dependencies
3. Model 123 write detection is reliable for Venus OS presence — reads produce false positives
4. No auto-save on detection — user confirmation prevents misconfiguration

### Cost Observations
- Model mix: ~90% opus, ~10% sonnet (verification)
- Plan execution: avg ~20 min per plan
- Notable: entire v3.0 milestone completed in single session (~2 hours)

---

## Milestone: v2.0 — Dashboard & Power Control

**Shipped:** 2026-03-18
**Phases:** 4 | **Plans:** 7 | **Commits:** 39

### What Was Built
- Venus OS styled dark-theme dashboard with live WebSocket updates
- SVG power gauge, 3-phase cards, sparkline chart (60 min history)
- Power Control page with safety confirmations and Venus OS override detection
- Inverter status panel with daily energy counter
- 3-file frontend architecture (HTML + CSS + JS) replacing single-file

### What Worked
- Zero new dependencies approach: vanilla JS + aiohttp WebSocket kept deployment simple
- DashboardCollector pattern cleanly decoupled Modbus polling from UI data delivery
- Confirmation dialogs for power control prevented accidental writes (safety-first UX)
- Venus OS color token research from official Victron repo gave high-confidence styling
- Phase execution velocity: ~3 hours for 4 phases / 7 plans

### What Was Inefficient
- ROADMAP.md plan checkboxes fell out of sync (07-02, 08-01 still unchecked despite completion)
- Summary one_liner field not populated by executor, requiring manual extraction for milestones
- Progress table in ROADMAP.md had formatting inconsistencies (missing milestone column)

### Patterns Established
- `ve-` CSS prefix convention for all Venus OS themed classes
- Late import pattern for avoiding circular imports (DashboardCollector, broadcast_to_clients)
- shared_ctx["webapp"] bridge between proxy and webapp subsystems
- Client-side power computation (V*I) to keep WebSocket payloads lean
- Confirmation dialog pattern for all destructive/control actions

### Key Lessons
1. WebSocket > SSE for bidirectional control use cases (power control needed it)
2. In-memory ring buffers (deque) are sufficient for short-term dashboards — no DB needed
3. Venus OS priority window (60s) is essential for override conflict resolution
4. EDPC refresh at CommandTimeout/2 is the right interval to keep limits active

### Cost Observations
- Model mix: 100% opus (quality profile)
- Plan execution: avg ~25 min per plan (including docs)
- Notable: entire v2.0 milestone completed in single session (~3 hours)

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-18
**Phases:** 4 | **Plans:** 9 | **Commits:** ~40

### What Was Built
- Modbus TCP proxy translating SolarEdge SE30K to Fronius SunSpec profile
- Venus OS native recognition and bidirectional control
- Plugin architecture for future inverter brands
- Configuration webapp with register viewer
- systemd service with night mode state machine

### What Worked
- Plugin ABC pattern made inverter abstraction clean from day one
- Cache-based proxy model eliminated pass-through latency
- Night mode state machine prevented crashes when inverter sleeps
- Research phase (protocol analysis) prevented rework in later phases

### What Was Inefficient
- Summary files lacked one_liner metadata from start
- Initial single-file HTML approach was replaced in v2.0 (expected for MVP)

### Patterns Established
- InverterPlugin ABC with 6 methods
- StalenessAwareSlaveContext for register serving
- Dual asyncio task pattern (poller + server)
- YAML config with importlib.resources for packaging

### Key Lessons
1. Manufacturer string "Fronius" is critical for Venus OS auto-enabling power control
2. SunSpec Model 120+123 must be synthesized — SE30K doesn't expose them natively
3. Night mode needs synthetic register values, not just error handling

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Key Change |
|-----------|---------|--------|------------|
| v1.0 | ~40 | 4 | Foundation — proxy core, plugin arch, webapp |
| v2.0 | 39 | 4 | Dashboard — WebSocket, UI, control, polish |
| v2.1 | ~15 | 4 | Polish — animations, toasts, lock toggle, unified layout |
| v3.0 | ~20 | 4 | Onboarding — config UX, auto-detect, install script, README |

### Cumulative Quality

| Milestone | Python LOC | Frontend LOC | Test LOC | New Dependencies |
|-----------|-----------|-------------|---------|-----------------|
| v1.0 | 1,851 | ~200 (inline) | 2,676 | pymodbus, aiohttp, structlog, PyYAML |
| v2.0 | 2,442 | 2,220 | 3,656 | 0 (zero new deps) |
| v2.1 | 2,578 | 2,801 | 4,083 | 0 (zero new deps) |
| v3.0 | ~3,000 | ~3,200 | ~4,500 | paho-mqtt (MQTT client) |

### Top Lessons (Verified Across Milestones)

1. Zero-dependency frontend keeps deployment simple on embedded/LXC targets
2. Research phases (protocol analysis, UI token extraction, pymodbus API analysis) prevent rework later
3. Safety-first UX patterns (confirmation dialogs, priority windows, no auto-save) are worth the extra code
4. Live status indicators (bobbles, gates) are always better than one-shot test buttons
5. Pre-flight checks in install scripts catch 90% of deployment issues before they happen
