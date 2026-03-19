# Feature Landscape: Setup & Onboarding

**Domain:** IoT Modbus proxy setup/onboarding flow
**Researched:** 2026-03-19
**Milestone:** v3.0 Setup & Onboarding
**Confidence:** HIGH (existing codebase thoroughly analyzed, Venus OS MQTT/Modbus behavior verified against official sources)

## Table Stakes

Features users expect. Missing = setup feels broken or unfinished.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Config page pre-filled defaults** | Every IoT setup tool pre-fills known-good defaults; blank fields force guessing | Low | Existing `config.py` defaults (192.168.3.18:1502, unit 1) | Already have defaults in dataclass; frontend must load them on first visit via `/api/config` |
| **Connection status bobble after Save** | Users need immediate feedback that config works; "did it save?" anxiety is the #1 onboarding killer | Low | Existing `/api/status` endpoint, `conn_mgr.state` in WebSocket snapshots | Replace Test Connection button with auto-status dot that updates from WebSocket after Save & Apply |
| **MQTT configurable (Venus OS IP + Portal ID)** | Currently hardcoded in 3 places (`venus_reader.py` VENUS_HOST/PORTAL_ID, `webapp.py` venus_write/dbus handlers). Any user with different Venus OS IP is completely stuck | Medium | Existing `config.py` dataclass pattern | Add `VenusConfig` dataclass with `host`, `port`, `portal_id`; thread through to all MQTT consumers |
| **Dashboard MQTT gate** | Showing interactive Lock Toggle / Override Detection / Venus Settings when MQTT disconnected is misleading -- users click, nothing happens, assume proxy is broken | Medium | `venus_reader.py` connection state, WebSocket snapshot pipeline | "Responsive enabling" pattern: elements visible but disabled with overlay hint |
| **MQTT setup guide hint** | MQTT on Venus OS is off by default (must be enabled in Remote Console under Settings -> Services). Users who skip this see a dead dashboard | Low | None (pure frontend hint card) | Inline card when MQTT status disconnected; step-by-step Venus OS instructions |
| **Install script fix** | Generated YAML uses `solaredge:` key but `config.py` expects `inverter:` key -- fresh installs produce broken config | Low | Existing `install.sh` | Fix key mismatch, add Venus OS IP/Portal ID fields to generated YAML |
| **README with setup flow** | No documentation for install-to-working flow; GitHub visitors have zero guidance | Low | All other features (documents them) | Linear: Install -> Config -> Enable Venus OS MQTT -> Verify Dashboard |

## Differentiators

Features that set this apart from typical "edit YAML and restart" IoT tools.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Venus OS auto-config detection** | After proxy starts, Venus OS dbus-fronius scans all LAN IPs with SunSpec Modbus requests and finds the proxy automatically. Detecting this incoming connection and confirming "Venus OS found us!" eliminates the scariest setup step | Medium | Modbus server running (already is), need to track incoming TCP client IPs | dbus-fronius scans are automatic; feature is about *detecting and surfacing* the connection, not creating it |
| **Live connection status bobble** | Persistent colored dot instead of Test Connection button. Green/red/amber updates in real-time from WebSocket. Feels alive, reduces testing anxiety | Low | Existing WebSocket pipeline, `conn_mgr.state` already tracked | Remove Test Connection button from UI. Dot driven by `data.connection.state`: connected=green, reconnecting=amber, night_mode=blue, error=red |
| **Progressive setup checklist** | Banner showing completion: [x] Inverter configured [x] SolarEdge connected [ ] MQTT enabled [ ] Venus OS detected. Clear path and progress sense | Low | All status fields already exist in snapshot data | Pure frontend. Disappears when all items complete. No persistence needed |
| **Portal ID auto-discovery** | Venus OS publishes portal ID on MQTT `N/+/system/0/Serial`. If user provides Venus IP but not portal ID, proxy subscribes and discovers automatically | Medium | MQTT connection working | Saves user from digging through Venus OS menus for portal ID |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Multi-step setup wizard (Next/Back)** | Over-engineering for 6 fields total. Wizard UX adds navigation state, breaks browser back button, feels patronizing for users who run LXC containers | Single config page with all fields visible, grouped by section (Inverter / Venus OS). Setup checklist provides progressive guidance without wizard overhead |
| **Network scanner for SolarEdge** | Scanning 254 IPs with Modbus TCP probes takes 5+ minutes, generates noise, and the user already knows their inverter IP from SolarEdge portal | Pre-fill default IP, let user correct it. Connection bobble confirms instantly |
| **Venus OS auto-provisioning (writing dbus)** | Writing to Venus OS dbus to force-add proxy is fragile across firmware versions, bypasses consent, could conflict with existing configs | Document the Venus OS side: dbus-fronius auto-scans and finds the proxy within ~2 minutes. The proxy already responds correctly to SunSpec queries |
| **Separate onboarding page / first-run** | Adds routing, another HTML page, and "has user completed onboarding" state management. For a single-page LAN tool, overkill | Setup checklist banner on existing config page, auto-dismisses when complete |
| **Live Modbus probe on every keystroke** | Excessive Modbus traffic confuses SE30K, adds latency to typing | Validate format client-side (`validate_inverter_config`), test connection on Save only, show result via status bobble |
| **Full service restart for config change** | `plugin.reconfigure()` already hot-reloads inverter settings. Service restart risks downtime and loses in-memory state | Extend hot-reload pattern to MQTT: reconnect `venus_mqtt_loop` with new host/portal_id without restarting service |
| **Config validation modal / popup** | Modal dialogs interrupt flow and feel heavy for inline validation | Inline validation errors below fields (red text), status bobble for connection result |

## Feature Dependencies

```
Config pre-filled defaults ---------> (standalone, no deps)

MQTT configurable (VenusConfig) ----> Dashboard MQTT gate
                                  |-> MQTT setup guide (needs connection status to show/hide)
                                  |-> Portal ID auto-discovery
                                  |-> Venus OS auto-config detection (needs Venus IP for identification)

Connection status bobble -----------> (depends on existing WebSocket, standalone otherwise)

Install script fix -----------------> README (README references install command)

Setup checklist --------------------> All other features (aggregates their status signals)
```

**Critical path:** MQTT configurable must ship first because Dashboard MQTT gate, setup guide, and auto-discovery all depend on it.

## MVP Recommendation

### Must Ship (table stakes -- without these, v3.0 does not solve onboarding):

1. **MQTT configurable** -- Highest priority. Hardcoded in 3 places. No other user can run this proxy without modifying source code. This is a blocker.
2. **Config page pre-filled defaults** -- Trivial, high impact. Load defaults into form on first visit.
3. **Connection status bobble** -- Replace Test Connection with live dot. Immediate feedback after Save.
4. **Dashboard MQTT gate** -- Grey out Lock Toggle, Override Detection, Venus Settings when MQTT disconnected. CSS `opacity: 0.3` + `pointer-events: none` + overlay hint.
5. **MQTT setup guide** -- Inline hint: "Enable MQTT on LAN in Venus OS Remote Console: Settings -> Services -> MQTT on LAN -> Enable."
6. **Install script fix** -- Fix `solaredge:` / `inverter:` YAML key mismatch. Add venus config section.
7. **README** -- Last to write, documents everything else.

### Should Ship (differentiators):

8. **Venus OS auto-config detection** -- Track incoming Modbus TCP connections, show "Venus OS connected from 192.168.3.146!" Medium effort, high confidence boost.
9. **Progressive setup checklist** -- Pure frontend, aggregates existing status signals. Low effort once others exist.

### Defer to later milestone:

10. **Portal ID auto-discovery** -- Nice but not essential. User already needs to provide Venus OS IP for MQTT; portal ID is one more field (30s lookup in Venus OS Remote Console). Auto-discovery adds MQTT client initialization complexity.

## Implementation Notes

### Connection Status Bobble

Current flow: fill form -> Test Connection -> see result -> Save & Apply.
New flow: fill form -> Save & Apply -> dot goes amber (connecting) -> green or red within 1-2s from WebSocket snapshot.

Backend: Keep `/api/config/test` for backward compat but remove from UI. `config_save_handler` already calls `plugin.reconfigure()`. `conn_mgr.state` reflects result in next WebSocket broadcast.

Frontend: Colored dot next to "SolarEdge" label. Color from `data.connection.state`:
- `connected` = green (#2ECC71)
- `reconnecting` = amber (#F1C40F, CSS pulse animation)
- `night_mode` = blue (#387DC5)
- anything else = red (#E74C3C)

### MQTT Gate Pattern

`venus_settings` in WebSocket snapshot is only populated when `venus_mqtt_loop` connects. When absent or stale (ts > 30s ago):

```css
.mqtt-gated {
    opacity: 0.3;
    pointer-events: none;
    position: relative;
}
.mqtt-gated::after {
    content: 'Requires MQTT connection to Venus OS';
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    color: var(--ve-text-muted);
    font-size: 0.85rem;
}
```

**Gate these elements:** Venus OS Lock Toggle, Venus OS ESS Settings, Override Detection log, Grid power display.
**Keep enabled without MQTT:** Power gauge, phase cards, sparklines, inverter status, power control slider (writes directly to SE30K via Modbus).

### VenusConfig Dataclass

```python
@dataclass
class VenusConfig:
    host: str = ""          # Empty = MQTT disabled (initial state)
    port: int = 1883
    portal_id: str = ""     # Empty = try auto-discovery (future)
```

Empty `host` means MQTT intentionally disabled (user hasn't configured Venus OS yet). This is the normal initial state for new installs. `venus_mqtt_loop` checks `if not config.venus.host: return` and dashboard shows setup guide hint.

Three hardcoded locations to update:
1. `venus_reader.py` lines 19-20: `PORTAL_ID` and `VENUS_HOST` constants
2. `webapp.py` line 598: `venus_write_handler` uses `"192.168.3.146"` directly
3. `webapp.py` line 677: `_mqtt_write_venus` called with hardcoded host/portal_id

### Venus OS Auto-Config Detection

dbus-fronius on Venus OS scans LAN IPs by sending SunSpec Modbus TCP read requests (reads register 40000 for SunSpec "SunS" marker, then model chain). The proxy already responds correctly.

Implementation: Track incoming Modbus TCP client IPs in pymodbus server callbacks. When a non-localhost IP connects and successfully reads SunSpec registers, add it to a tracked set and expose in snapshot:

```python
# Add to snapshot
"venus_os_detected": {
    "connected": True,
    "client_ip": "192.168.3.146",
    "last_contact_ts": 1710850000.0
}
```

### Install Script YAML Fix

Current generated YAML:
```yaml
solaredge:    # WRONG -- config.py expects "inverter"
  host: "192.168.3.18"
```

Should be:
```yaml
inverter:
  host: "192.168.3.18"
  port: 1502
  unit_id: 1

venus:
  host: ""              # Venus OS IP (e.g., 192.168.3.146)
  port: 1883
  portal_id: ""         # Venus OS Portal ID (found in Remote Console)
```

## Complexity Budget

| Feature | Backend LOC | Frontend LOC | Total Effort |
|---------|-------------|--------------|--------------|
| Config pre-filled defaults | 0 | ~20 | Low |
| Connection status bobble | 0 | ~40 | Low |
| MQTT configurable | ~80 | ~60 | Medium |
| Dashboard MQTT gate | ~10 | ~50 | Medium |
| MQTT setup guide | 0 | ~40 | Low |
| Install script fix | ~30 | 0 | Low |
| README | 0 | 0 (~200 lines md) | Low |
| Venus OS auto-config | ~60 | ~30 | Medium |
| Setup checklist | 0 | ~80 | Low |

**Total: ~180 LOC backend, ~320 LOC frontend, ~200 lines markdown**

## Sources

- [Scenic West - IoT User Onboarding Guide](https://www.scenicwest.co/blog/a-fresh-approach-to-iot-user-onboarding-a-b2b-ux-designers-guide)
- [grandcentrix - IoT Onboarding Guide](https://medium.com/@janinerchrtz/your-iot-onboarding-guide-2e009535c050)
- [WithIntent - User-friendly Onboarding for IoT](https://www.withintent.com/blog/user-friendly-onboarding/)
- [Carbon Design System - Status Indicator Patterns](https://carbondesignsystem.com/patterns/status-indicator-pattern/)
- [KoruUX - Status Indicator Best Practices](https://www.koruux.com/blog/ux-best-practices-designing-status-indicators/)
- [LogRocket - Progressive Disclosure in UX](https://blog.logrocket.com/ux-design/progressive-disclosure-ux-types-use-cases/)
- [Medium - Responsive Enabling Pattern](https://medium.com/design-bootcamp/enhancing-ux-with-responsive-enabling-and-progressive-disclosure-patterns-92c07029a46a)
- [victronenergy/dbus-fronius - Inverter Detection](https://github.com/victronenergy/dbus-fronius)
- [victronenergy/dbus-mqtt - Venus MQTT Service](https://github.com/victronenergy/dbus-mqtt)
- [Venus OS MQTT Community Discussion](https://community.victronenergy.com/t/venus-os-v3-53-mqtt-local-communication-on-mqtt-explorer/18199)
- [Venus OS - Scan for Modbus Devices](https://community.victronenergy.com/t/venus-os-scan-for-modbus-devices/23121)
- Codebase analysis: `config.py`, `venus_reader.py`, `webapp.py`, `install.sh`, `app.js`
