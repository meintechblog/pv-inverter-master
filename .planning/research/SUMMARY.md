# Project Research Summary

**Project:** Venus OS Fronius Proxy — v3.0 Setup & Onboarding
**Domain:** IoT Modbus proxy — MQTT configuration, connection status, onboarding flow
**Researched:** 2026-03-19
**Confidence:** HIGH

## Executive Summary

This project is a Python-based Modbus TCP proxy that bridges a SolarEdge inverter to Venus OS (Victron Energy). The v3.0 milestone is a setup and onboarding hardening release: making MQTT connection details configurable (currently hardcoded in three source locations), adding live connection status indicators, and fixing broken installer behavior. Research confirms all required features can be built with the existing stack — no new dependencies are needed. Every building block (raw MQTT client, async WebSocket broadcast, config dataclass pattern, atomic config save) already exists in the codebase.

The recommended approach is to treat this as a pure plumbing and UX improvement rather than a feature expansion. MQTT configurability is the critical path: five other features (dashboard grey-out, setup guide, auto-discovery banner, portal ID discovery, connection status bobble) all depend on it. The correct build order is backend-first — config dataclass extension, parameter threading, connection state signals — before any UI work, so each UI layer has a real data source rather than mocked state.

The primary risks are not architectural but implementational: silent MQTT failures (CONNACK return code is never parsed in the current raw socket client), race conditions between config hot-reload and live Venus OS writes, and config schema drift on updates (the install script already generates a YAML key mismatch that silently falls back to hardcoded defaults). All three are known patterns with documented prevention strategies that can be addressed within the planned phases.

## Key Findings

### Recommended Stack

No stack changes are required for v3.0. The existing Python 3.12 / pymodbus / aiohttp / vanilla JS combination handles all planned features. Adding paho-mqtt or aiomqtt would introduce a dependency with no user-visible benefit while conflicting with the asyncio event loop. The config system (PyYAML + Python dataclasses + atomic file writes) already implements the exact pattern needed for the new `VenusConfig` dataclass.

**Core technologies (all unchanged):**
- Python 3.12 + aiohttp: async HTTP/WebSocket server — extend with new config endpoints, no framework change
- pymodbus >=3.6,<4.0: Modbus TCP server + client — no version bump needed for any v3.0 feature
- Raw socket MQTT (Python stdlib): Venus OS MQTT reader — extend with CONNACK parsing, parameter injection, connection state signaling
- PyYAML + dataclasses: Config persistence — extend `Config` with `VenusConfig` field using the existing dataclass pattern
- Vanilla JS: Frontend — config form fields + CSS state classes, no framework needed

### Expected Features

**Must have (table stakes):**
- MQTT configurable (host, port, portal_id) — currently hardcoded in 3 backend locations; any user with a different Venus OS IP cannot run the proxy without modifying source code
- Config page pre-filled defaults — form must load current config via `/api/config` on first visit; blank fields force guessing
- Connection status bobble — live green/red/amber dot after Save, driven by WebSocket snapshot; replaces the existing Test Connection button
- Dashboard MQTT gate — Venus OS Lock Toggle, Override Detection, ESS Settings, and Grid power must be visually disabled when MQTT is not connected; power gauge, inverter status, and power slider stay enabled without MQTT
- MQTT setup guide hint — inline card when MQTT disconnected: "Enable MQTT on LAN in Venus OS Remote Console: Settings -> Services -> MQTT on LAN"
- Install script fix — `solaredge:` YAML key must be changed to `inverter:` (current mismatch causes silent fallback to hardcoded defaults); add `venus:` section to generated config

**Should have (differentiators):**
- Venus OS auto-config detection — detect first Modbus write from Venus OS (Model 123 register), show "Venus OS is connected to your proxy!" banner prompting MQTT IP entry
- Progressive setup checklist — frontend-only banner showing completion state across inverter, MQTT, and Venus OS detection; disappears when all steps complete
- Portal ID auto-discovery — subscribe to `N/+/system/0/Serial` MQTT wildcard after user enters Venus IP; extract portal ID from topic prefix automatically

**Defer to later milestone:**
- README overhaul — documents everything else; last to write, not a blocker for functionality
- Network scanner for SolarEdge — user already knows their inverter IP; 5-minute scan is overkill
- Multi-step setup wizard — patronizing for LXC operators; checklist banner is sufficient progressive disclosure

### Architecture Approach

All new features integrate into existing modules via `shared_ctx` (the central state dict) and the existing WebSocket snapshot pipeline. No new Python modules are needed. The key structural change is threading `VenusConfig` (host, portal_id, port) from `config.yaml` through the `Config` dataclass into `venus_mqtt_loop()`, `venus_write_handler()`, and `_mqtt_write_venus()` — replacing five hardcoded string literals. MQTT connection state flows from `venus_reader.py` into `shared_ctx["venus_mqtt_connected"]`, into the dashboard snapshot, and out to the browser via the existing WebSocket broadcast.

**Major components and their v3.0 changes:**
1. `config.py` — Add `VenusConfig` dataclass (host, port=1883, portal_id); extend `Config` with `venus` field
2. `venus_reader.py` — Parameterize `venus_mqtt_loop(host, portal_id)`; add CONNACK parsing; write `shared_ctx["venus_mqtt_connected"]`; add `discover_portal_id(host)` helper
3. `webapp.py` — De-hardcode all three Venus IP/portal_id references; extend config GET/POST for venus section; add `POST /api/config/venus-test` endpoint; add autodetect status endpoint
4. `proxy.py` — Set `shared_ctx["venus_autodetect_triggered"]` on first Model 123 write from external Modbus client
5. `dashboard.py` — Include `venus_mqtt_connected` in snapshot
6. `__main__.py` — Conditional venus_mqtt_loop start; store task ref in `shared_ctx["venus_task"]` for cancellable hot-reload
7. `index.html / app.js / style.css` — Venus config section, connection bobbles, MQTT gate CSS, setup checklist banner

### Critical Pitfalls

1. **Config hot-reload mutates shared state without rollback** — Build a new `Config` object, validate it, then atomically swap the reference. Cancel and restart `venus_mqtt_loop` with updated params rather than patching module globals. Match the existing atomic file write pattern for in-memory state.

2. **MQTT CONNACK return code never parsed (silent false-positive connection)** — The current `s.recv(4)` in `venus_reader.py` reads but ignores the CONNACK return code. A rejected connection appears connected, dashboard shows stale Venus OS data indefinitely. Fix: `if connack[3] != 0: raise ConnectionError(...)` before declaring MQTT connected.

3. **Three hardcoded Venus IPs and two hardcoded portal IDs** — `venus_reader.py:19-20`, `webapp.py:598`, `webapp.py:677`. All five must be updated together. Partial migration means different operations connect to different hosts silently. Add a CI grep guard to prevent future hardcoding.

4. **Install script config schema drift on updates** — Existing users who update via `curl | bash` keep old config without the new `venus:` section. Keep all defaults in the `Config` dataclass (never removed to force config), log a startup warning for any missing config section, and print the effective config on startup.

5. **Connection status bobble false positives during transient states** — `venus_os: "active"` is currently hardcoded in `status_handler`. Debounce status transitions (3 consecutive failures before showing disconnected), use WebSocket for status on config page (not polling), and add "last successful communication" timestamps to both SolarEdge and MQTT status fields.

## Implications for Roadmap

Research strongly supports an 8-phase build order driven by dependency chains. The backend config foundation must precede all UI work. MQTT reliability fixes must precede making MQTT configurable — you cannot expose a broken connection model through a new UI.

### Phase 1: Config Foundation
**Rationale:** Every other feature depends on Venus config being in the config system. Pure backend, zero UI risk, immediately testable in isolation.
**Delivers:** `VenusConfig` dataclass, `venus_mqtt_loop(host, portal_id)` parameterized, `__main__.py` starts loop conditionally, `shared_ctx["venus_task"]` stored for future cancellation
**Addresses:** MQTT configurable (table stakes critical path), pitfall 10 (hardcoded constants), pitfall 13 (fire-and-forget task not cancellable)
**Avoids:** Pitfall 1 (config hot-reload mutation) — design the atomic swap pattern here before any UI depends on it

### Phase 2: MQTT Connection State Signaling
**Rationale:** Required by all UI features that show connection status. Small, high-value backend change. Resolves the silent CONNACK failure before it is exposed through a new UI.
**Delivers:** CONNACK return code parsing, `shared_ctx["venus_mqtt_connected"]` flag, `mqtt_last_message_ts`, `venus_mqtt_connected` in dashboard snapshot
**Addresses:** Pitfall 2 (silent CONNACK failure), pitfall 5 (false positive bobble), pitfall 8 (UI re-enable before MQTT stable)
**Avoids:** Exposing a broken connection model to users through new status indicators

### Phase 3: De-hardcode webapp.py
**Rationale:** Depends on Phase 1 config being available. Eliminates all remaining hardcoded Venus OS references. Must be complete before any UI work references these endpoints.
**Delivers:** `venus_write_handler`, `venus_dbus_handler`, `_mqtt_write_venus` all read from `config.venus`; all five hardcoded literals removed
**Addresses:** Pitfall 10 (three hardcoded IPs, two portal IDs)
**Avoids:** Partial migration where MQTT reads and writes connect to different hosts

### Phase 4: Config Page UI — Venus Section + Bobbles
**Rationale:** Depends on Phases 1-3. This is the primary user-facing setup experience. Users can enter Venus OS IP and save it persistently with immediate connection feedback.
**Delivers:** Venus OS fields in config page, connection status bobbles (green/amber/red/grey), `POST /api/config/venus-test` with portal ID discovery, extend config GET/POST for venus section
**Addresses:** Config pre-filled defaults, connection status bobble, MQTT setup guide hint (all table stakes)
**Avoids:** Pitfall 5 (debounce status transitions, WebSocket for status), pitfall 7 (queue Modbus writes during reconfigure), pitfall 12 (broadcast reconfigure events to WebSocket clients)

### Phase 5: Portal ID Auto-Discovery
**Rationale:** Quality-of-life improvement that depends on Phase 4 venus-test endpoint. User enters only the Venus OS IP; portal ID is discovered automatically via MQTT wildcard subscription.
**Delivers:** `discover_portal_id(host)` in venus_reader.py, integrated into venus-test endpoint, UI shows discovered portal ID for confirmation before saving
**Addresses:** Pitfall 6 (wrong portal ID gives silent empty subscription — auto-discovery sidesteps this entirely)

### Phase 6: Dashboard MQTT Gate
**Rationale:** Depends on Phase 2 (connection state in snapshot). Pure frontend change that prevents user confusion when MQTT is not connected.
**Delivers:** `.mqtt-disconnected` CSS class on `#venus-widgets` wrapper, grey-out with overlay hint text, stability threshold (10s + 3 messages) before re-enable, toast on MQTT loss after stable period
**Addresses:** Dashboard MQTT gate (table stakes), pitfall 8 (stability threshold before re-enabling interactive controls)

### Phase 7: Venus OS Auto-Detect Banner
**Rationale:** Progressive onboarding enhancement that depends on Phases 4-5 being complete. Detects first Modbus write from Venus OS and prompts the user to configure MQTT.
**Delivers:** `shared_ctx["venus_autodetect_triggered"]` flag in `proxy.py`, autodetect status endpoint in `webapp.py`, config page banner with "Test & Apply" flow (not auto-save)
**Addresses:** Venus OS auto-config detection (differentiator), pitfall 3 (detect -> suggest -> test -> confirm state machine, never auto-saves config before MQTT is verified)

### Phase 8: Install Script Polish
**Rationale:** Independent of all code changes. Must be done after config format is finalized (Phases 1-3 must be complete).
**Delivers:** Fix `solaredge:` -> `inverter:` key mismatch, add `venus:` section to config template, secure curl flags (`-fsSL --proto '=https' --tlsv1.2`), version pinning, port 502 pre-flight check, setup URL printed at end, skip apt-get if deps already present
**Addresses:** Install script fix (table stakes), pitfall 4 (schema drift), pitfall 11 (YAML key mismatch), pitfall 14 (apt-get on every update), pitfall 15 (file permissions)

### Phase Ordering Rationale

- Phases 1-3 are backend-only and form the foundation that all UI work depends on. UI built before the backend is ready requires mocking and creates integration debt.
- Phase 2 (CONNACK parsing) is explicitly sequenced before any user-visible connection UI because you cannot show reliable status indicators until the underlying connection model is accurate.
- Phases 4-6 are the primary user experience. Phase 6 (CSS grey-out) depends on Phase 2's snapshot field but is otherwise independent of Phases 4-5, so frontend CSS work can start in parallel once Phase 2 is done.
- Phase 7 requires Phases 4-5 to be useful. Detection without a working test+apply flow would confuse users.
- Phase 8 is last because the config YAML format must be stable before writing the installer template.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4:** `POST /api/config/venus-test` must use `asyncio.open_connection()` not blocking `socket.socket`, otherwise the aiohttp event loop blocks during the MQTT test. Verify this approach against the existing raw socket reader pattern before implementation.
- **Phase 7:** pymodbus `ModbusTcpServer` does not expose client connection events natively. Detection via first `async_setValues` on Model 123 registers is the planned fallback. Validate this intercept point works reliably against Venus OS dbus-fronius behavior on the hardware in use.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Dataclass extension and parameter threading are pure Python with zero ambiguity.
- **Phase 2:** CONNACK byte parsing is MQTT 3.1.1 spec, byte 4 = return code. Fully documented.
- **Phase 3:** Find-and-replace hardcoded strings with config reads. No research needed.
- **Phase 6:** CSS `opacity + pointer-events` grey-out is a standard, well-documented pattern.
- **Phase 8:** Bash install script patterns are well-documented.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies confirmed. All building blocks exist in codebase. Verified against official Victron sources and pymodbus docs. |
| Features | HIGH | Codebase thoroughly analyzed. Venus OS MQTT/Modbus behavior verified against official Victron documentation. Feature set is tightly scoped to existing infrastructure. |
| Architecture | HIGH | Based on direct code analysis of all source files. All integration points identified with exact file and line references. No speculation. |
| Pitfalls | HIGH | Primary source is direct code analysis. MQTT 3.1.1 spec for CONNACK. asyncio docs for blocking call patterns. All 15 pitfalls are concrete and observed in the codebase. |

**Overall confidence:** HIGH

### Gaps to Address

- **pymodbus peer IP in async_setValues context (MEDIUM):** During Phase 7 implementation, verify whether pymodbus write handler context exposes the peer address, or whether a connection-level hook is available. If not, the auto-detect banner can still fire (Venus OS connected) without knowing the IP — user enters the IP manually, which is acceptable.
- **Venus OS firmware version variance:** Auto-discovery timing (when dbus-fronius scans vs. when MQTT broker is ready) may vary between Venus OS firmware versions. Phase 7's state machine (detect -> suggest -> test -> confirm) mitigates this, but real-hardware testing against the target Venus OS version should confirm timing assumptions before shipping.
- **`_mqtt_write_venus` blocking event loop (pre-existing):** This function makes synchronous blocking socket calls with `time.sleep(0.5)` inside an aiohttp handler, blocking the event loop for 500ms+ per Venus OS dbus write. It is not in v3.0 scope but should be tracked for a follow-on fix. Wrapping in `run_in_executor` is the immediate mitigation.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis — `venus_reader.py`, `webapp.py`, `config.py`, `proxy.py`, `__main__.py`, `dashboard.py`, `install.sh`, `app.js`
- [victronenergy/dbus-mqtt](https://github.com/victronenergy/dbus-mqtt) — MQTT keep-alive mechanism, R/ topic requirement every 60s
- [victronenergy/venus-html5-app TOPICS.md](https://github.com/victronenergy/venus-html5-app/blob/master/TOPICS.md) — MQTT topic reference, `N/+/system/0/Serial` wildcard for portal ID discovery
- [victronenergy/dbus-flashmq](https://github.com/victronenergy/dbus-flashmq) — Current MQTT broker in Venus OS v3.20+
- MQTT 3.1.1 specification — CONNACK return code byte structure

### Secondary (MEDIUM confidence)
- [Victron Community: MQTT local via broker](https://community.victronenergy.com/questions/155407/mqtt-local-via-mqtt-broker.html) — Portal ID wildcard pattern confirmed by community usage
- [victronenergy/dbus-fronius](https://github.com/victronenergy/dbus-fronius) — Inverter detection scan behavior (SunSpec register reads on all LAN IPs)
- [Idempotent Bash scripts (Arslan, 2019)](https://arslan.io/2019/07/03/how-to-write-idempotent-bash-scripts/) — Install script idempotency patterns
- [Curl best practices in shell scripts (Joyful Bikeshedding, 2020)](https://www.joyfulbikeshedding.com/blog/2020-05-11-best-practices-when-using-curl-in-shell-scripts.html) — Security flags for curl-pipe-bash

### Tertiary (LOW confidence — informational only)
- IoT UX onboarding guides (Scenic West, grandcentrix, WithIntent) — Status indicator and progressive disclosure patterns; referenced for feature rationale only, not technical decisions

---
*Research completed: 2026-03-19*
*Ready for roadmap: yes*
