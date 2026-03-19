# Architecture: Setup & Onboarding Integration

**Domain:** Modbus TCP proxy with web dashboard — setup/onboarding flow
**Researched:** 2026-03-19
**Confidence:** HIGH (all based on direct code analysis of existing codebase)

## Current Architecture Overview

```
                        shared_ctx (dict)
                              |
    __main__.py ──────────────┼────────────────────────────
        |                     |                            |
   run_proxy()           create_webapp()           venus_mqtt_loop()
   (proxy.py)            (webapp.py)               (venus_reader.py)
        |                     |                            |
   ┌────┴─────┐          aiohttp app                raw socket MQTT
   │ poll_loop│          REST + WS + static         to 192.168.3.146
   │ + server │              |                      (hardcoded)
   └──────────┘         browser (vanilla JS)
```

**Key observation:** `shared_ctx` is the central nervous system. Every component reads/writes from it. This is the correct integration point for new features — no new messaging needed.

## Integration Analysis: Feature by Feature

### 1. MQTT Host/Portal Configurable (venus_reader.py)

**Current state:** `VENUS_HOST = "192.168.3.146"` and `PORTAL_ID = "88a29ec1e5f4"` are module-level constants in venus_reader.py. Also hardcoded in webapp.py `venus_write_handler` (line 598) and `_mqtt_write_venus` / `venus_dbus_handler` (line 677).

**Files modified:**
| File | Change |
|------|--------|
| `config.py` | Add `VenusConfig` dataclass (host, port=1883, portal_id, enabled=false) to `Config` |
| `venus_reader.py` | Accept `host` + `portal_id` as parameters to `venus_mqtt_loop()` instead of constants |
| `webapp.py` | `venus_write_handler` and `_mqtt_write_venus` and `venus_dbus_handler` read venus host/portal from `request.app["config"]` instead of hardcoded |
| `__main__.py` | Pass `config.venus.host` + `config.venus.portal_id` to `venus_mqtt_loop()`. Only start venus_task if `config.venus.enabled` or host is set |
| `install.sh` | Add `venus:` section to default config template |

**New components:** None. Pure parameter threading.

**Data flow change:**
```
Before: venus_reader.py -> hardcoded HOST -> socket.connect()
After:  config.yaml -> Config.venus -> venus_mqtt_loop(host, portal_id) -> socket.connect()
```

**Design decision: `enabled` flag vs empty host.** Use empty string as "not configured" (no separate enabled flag). Reason: simpler config file for users, one less concept. `venus_mqtt_loop` simply does not start if host is empty. The webapp shows "MQTT not configured" state.

### 2. MQTT Connection State in shared_ctx

**Current state:** `venus_mqtt_loop` writes `shared_ctx["venus_settings"]` on every message. If MQTT fails, it reconnects after 5s but never clears or signals the disconnect. The dashboard has no concept of "MQTT disconnected."

**Files modified:**
| File | Change |
|------|--------|
| `venus_reader.py` | Write `shared_ctx["venus_mqtt_connected"] = True/False` on connect/disconnect/error |
| `dashboard.py` | Include `venus_mqtt_connected` in snapshot |
| `webapp.py` | Include `venus_mqtt_connected` in status_handler and broadcast |
| `app.js` | Read `venus_mqtt_connected` from snapshot, grey out Venus-dependent UI elements |

**New components:** None.

**Data flow:**
```
venus_reader.py -> shared_ctx["venus_mqtt_connected"] = bool
    |
dashboard.py snapshot -> { ..., venus_mqtt_connected: true/false }
    |
WebSocket broadcast -> browser
    |
app.js -> toggle CSS class "mqtt-disconnected" on Venus widgets
```

**Which UI elements get greyed out:**
- Venus OS Lock toggle
- Venus OS Override indicator
- Venus ESS Settings (MaxFeedIn, PreventFeedback, etc.)
- Grid power display

**Which elements stay active (inverter-only, no MQTT needed):**
- Power gauge + phase details
- Inverter status
- Power control slider
- Sparklines
- Peak statistics
- Today's performance

**CSS approach:** Single `.mqtt-disconnected` class on a parent container. Child elements inherit opacity + pointer-events via CSS. No per-element JS toggling.

### 3. Config Page with Defaults + Connection Status Bobble

**Current state:** Config page exists at `#page-config` with inverter host/port/unit_id form, test button, and save. No Venus OS config. No live connection indicators.

**Files modified:**
| File | Change |
|------|--------|
| `config.py` | Add `VenusConfig` dataclass (already done in feature 1) |
| `webapp.py` | Extend `config_get_handler` to return venus config. Extend `config_save_handler` to accept venus fields. Add `POST /api/config/venus-test` endpoint for MQTT connection test |
| `index.html` | Add Venus OS section to config page: host, portal_id fields. Add connection status bobbles (green/red dots) next to SolarEdge and Venus OS sections |
| `app.js` | Fetch connection status, animate bobbles, handle venus config save |
| `style.css` | Status bobble styles (green pulse, red static, grey unknown) |

**New REST endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/config/venus-test` | POST | Test MQTT connection to provided host:1883 |

**Status bobble data source:** The existing `/api/status` endpoint already returns `solaredge` state. Extend it to include `venus_mqtt: "connected" / "disconnected" / "not_configured"`.

**Connection bobble states:**
```
Green (pulsing)  = connected
Red (static)     = configured but disconnected
Grey (static)    = not configured
```

### 4. Venus OS Auto-Config After Modbus Connection

**Current state:** When Venus OS connects to the proxy's Modbus server on port 502, the proxy has no awareness of who connected. pymodbus `ModbusTcpServer` does not expose client connection events.

**Approach: Detect first Modbus write to Model 123.**

Venus OS writes `WMaxLimPct` (register 40154) within seconds of connecting. The `StalenessAwareSlaveContext.async_setValues` already intercepts these. This is the detection point — no network-level connection tracking needed.

**Files modified:**
| File | Change |
|------|--------|
| `proxy.py` | In `_handle_control_write`, on first Venus OS write, if venus config is empty, set `shared_ctx["venus_autodetect_triggered"] = True` |
| `webapp.py` | New `GET /api/venus-autodetect` endpoint returns autodetect status. New `POST /api/venus-autodetect/apply` saves detected config |
| `app.js` | Poll autodetect status or receive via WebSocket. Show banner: "Venus OS detected! Configure MQTT to enable full integration." with one-click setup |
| `index.html` | Auto-config banner component in config page |

**What auto-detect can determine:**
- Venus OS is connected (it wrote to our Modbus server) -- YES
- Venus OS IP address -- NO (pymodbus does not expose client IP in async_setValues context)
- Portal ID -- NO (requires MQTT discovery or user input)

**Realistic auto-detect flow:**
1. Venus OS writes to Model 123 registers
2. Proxy detects first write, sets flag in shared_ctx
3. Config page shows: "Venus OS is connected to your proxy! To enable full dashboard features, enter Venus OS IP and Portal ID below."
4. User enters Venus OS IP (they know it — it is their Victron device)
5. Proxy attempts MQTT connection to that IP, reads portal ID from MQTT topic prefix
6. If successful, saves config and starts venus_mqtt_loop

**Portal ID auto-discovery:** Connect to MQTT, subscribe to `N/+/system/0/Serial`, read the portal ID from the topic. This avoids user needing to know the hex portal ID.

**Files modified (additional):**
| File | Change |
|------|--------|
| `venus_reader.py` | Add `discover_portal_id(host: str) -> str | None` function: connect MQTT, subscribe wildcard, parse portal ID from first N/ topic |
| `webapp.py` | `POST /api/config/venus-test` also calls `discover_portal_id` and returns it |

### 5. Dashboard Element Grey-out (MQTT not connected)

Covered in feature 2 above. Implementation detail:

**HTML structure change:**
```html
<!-- Wrap Venus-dependent widgets -->
<div id="venus-widgets" class="venus-dependent">
  <!-- Lock toggle, Override, ESS settings, Grid power -->
</div>
```

**JS logic:**
```javascript
// In snapshot handler
const venusSection = document.getElementById('venus-widgets');
if (snapshot.venus_mqtt_connected) {
    venusSection.classList.remove('mqtt-disconnected');
} else {
    venusSection.classList.add('mqtt-disconnected');
}
```

**CSS:**
```css
.mqtt-disconnected {
    opacity: 0.35;
    pointer-events: none;
    position: relative;
}
.mqtt-disconnected::after {
    content: 'MQTT not connected';
    /* overlay text */
}
```

### 6. Install Script Improvements

**Current gaps identified:**
- Config template uses `solaredge:` key but `config.py` expects `inverter:` key (mismatch on line 94 of install.sh vs config.py dataclass)
- No Venus OS section in config template
- No version pinning or update mechanism
- No pre-flight check for port 502 availability
- Starts service immediately without user editing config first

**Files modified:**
| File | Change |
|------|--------|
| `install.sh` | Fix config key mismatch. Add venus section. Add port check. Print setup URL at end. |

## Component Boundary Map

```
+-----------------------------------------------------------+
|                    __main__.py                             |
|  Orchestrator: loads config, starts tasks, shutdown       |
|  MODIFIED: conditional venus_mqtt_loop start              |
+------+----------------+------------------+----------------+
       |                |                  |
+------v------+  +------v------+  +-------v--------+
|  proxy.py   |  |  webapp.py  |  | venus_reader.py|
|             |  |             |  |                |
| poll_loop   |  | REST API    |  | MQTT subscribe |
| ModbusTCP   |  | WebSocket   |  | MQTT publish   |
| server      |  | Static files|  |                |
|             |  |             |  | NEW: discover  |
| MODIFIED:   |  | MODIFIED:   |  | portal_id()    |
| autodetect  |  | venus config|  |                |
| flag on     |  | endpoints   |  | MODIFIED:      |
| first write |  | venus-test  |  | parameterized  |
|             |  | autodetect  |  | host/portal    |
|             |  | status API  |  | connection     |
+-------------+  +-------------+  | state flag     |
                                   +----------------+
       |                |                  |
       +----------------+------------------+
                        |
                 shared_ctx (dict)
                        |
           +------------+----------------+
           |            |                |
    +------v------+  +--v-----+  +------v------+
    |  config.py  |  |app.js  |  | index.html  |
    |             |  |        |  |             |
    | MODIFIED:   |  |MODIFIED|  | MODIFIED:   |
    | +VenusConfig|  |venus UI|  | venus config|
    |             |  |greyout |  | section     |
    |             |  |bobbles |  | bobbles     |
    |             |  |autodet |  | autodetect  |
    +-------------+  +--------+  | banner      |
                                  +-------------+
```

## New vs Modified Components

### New Components: NONE
No new Python modules needed. All features integrate into existing files.

### New Functions (within existing modules):
| Module | Function | Purpose |
|--------|----------|---------|
| `venus_reader.py` | `discover_portal_id(host: str) -> str \| None` | Connect to MQTT, sniff portal ID from topic prefix |
| `webapp.py` | `venus_test_handler()` | Test MQTT connectivity + discover portal ID |
| `webapp.py` | `venus_autodetect_handler()` | Return autodetect status |

### Modified Functions:
| Module | Function | Change |
|--------|----------|--------|
| `config.py` | `Config` dataclass | Add `venus: VenusConfig` field |
| `config.py` | `load_config()` | Parse `venus:` section |
| `venus_reader.py` | `venus_mqtt_loop()` | Accept host/portal params, write connection state to shared_ctx |
| `webapp.py` | `config_get_handler()` | Return venus config fields |
| `webapp.py` | `config_save_handler()` | Accept/save venus config fields |
| `webapp.py` | `status_handler()` | Include `venus_mqtt` connection state |
| `webapp.py` | `venus_write_handler()` | Read host from config instead of hardcoded |
| `webapp.py` | `_mqtt_write_venus()` | Read host/portal from config |
| `webapp.py` | `venus_dbus_handler()` | Read host/portal from config |
| `proxy.py` | `_handle_control_write()` | Set autodetect flag on first Venus write |
| `__main__.py` | `run_with_shutdown()` | Conditional venus_mqtt_loop start |
| `dashboard.py` | `collect()` | Include `venus_mqtt_connected` in snapshot |

### Frontend Changes:
| File | Change |
|------|--------|
| `index.html` | Venus config section in config page, connection bobbles, autodetect banner, `.venus-dependent` wrapper |
| `app.js` | Venus config form handling, bobble animation, grey-out logic, autodetect polling |
| `style.css` | Bobble styles, `.mqtt-disconnected` styles, autodetect banner styles |

## Suggested Build Order

Build order is driven by dependency chains and testability:

### Phase 1: Config Foundation (backend only, no UI)
**What:** Add `VenusConfig` to config.py, parameterize venus_reader.py, thread config through __main__.py
**Why first:** Everything else depends on venus config being in the config system. Pure backend, easy to test in isolation.
**Files:** config.py, venus_reader.py, __main__.py
**Test:** Unit test config loading with venus section, verify venus_mqtt_loop accepts params

### Phase 2: MQTT Connection State
**What:** Write `shared_ctx["venus_mqtt_connected"]` in venus_reader.py, include in dashboard snapshot
**Why second:** Required by UI grey-out and config bobbles. Small change, high value.
**Files:** venus_reader.py, dashboard.py
**Test:** Unit test state transitions (connected/disconnected/reconnecting)

### Phase 3: De-hardcode webapp.py
**What:** Replace all hardcoded `192.168.3.146` and `88a29ec1e5f4` in webapp.py with config reads
**Why third:** Depends on Phase 1 config being available. Eliminates all hardcoded references.
**Files:** webapp.py
**Test:** Verify venus_write_handler, venus_dbus_handler use config values

### Phase 4: Config Page UI (venus section + bobbles)
**What:** Add Venus OS fields to config page, connection status bobbles, venus-test endpoint
**Why fourth:** Depends on Phases 1-3. This is the primary user-facing setup experience.
**Files:** index.html, app.js, style.css, webapp.py (new endpoint)
**Test:** Manual — fill in Venus IP, test connection, save, verify MQTT starts

### Phase 5: Portal ID Auto-Discovery
**What:** `discover_portal_id()` function, integrate into venus-test endpoint
**Why fifth:** Quality-of-life improvement. User enters IP, portal ID is found automatically.
**Files:** venus_reader.py, webapp.py
**Test:** Integration test against real Venus OS MQTT broker

### Phase 6: Dashboard Grey-out
**What:** CSS grey-out for Venus-dependent widgets when MQTT disconnected
**Why sixth:** Depends on Phase 2 (connection state in snapshot). Pure frontend.
**Files:** index.html, app.js, style.css
**Test:** Manual — disconnect MQTT, verify widgets grey out

### Phase 7: Venus OS Auto-Detect Banner
**What:** Detect first Modbus write, show banner in config page prompting MQTT setup
**Why seventh:** Nice-to-have onboarding hint. Depends on Phases 4-5.
**Files:** proxy.py, webapp.py, app.js, index.html
**Test:** Manual — connect Venus OS to proxy without MQTT config, verify banner appears

### Phase 8: Install Script Polish
**What:** Fix config key mismatch, add venus section, port check, setup URL
**Why last:** Independent of code changes. Can be done anytime but makes sense after config format is finalized.
**Files:** install.sh
**Test:** Fresh install on clean Debian 13 LXC

## Patterns to Follow

### Pattern: Config Hot-Reload for Venus Settings
The existing inverter config hot-reload pattern (`config_save_handler` -> `plugin.reconfigure()`) should be replicated for Venus config. When user saves new Venus host/portal:
1. Save to config.yaml (atomic write)
2. Cancel existing venus_mqtt_loop task
3. Start new venus_mqtt_loop with updated params

**Implementation:** Store the venus_task reference in `shared_ctx["venus_task"]`. On config save, cancel it and create a new one.

### Pattern: shared_ctx as State Bus
Every new state flows through shared_ctx. Do not create parallel state channels.
```python
# Good
shared_ctx["venus_mqtt_connected"] = True

# Bad -- new WebSocket message type
await ws.send_json({"type": "mqtt_status", "connected": True})
```

This follows the existing "client-side event detection" decision: extend the snapshot, not the protocol.

### Pattern: Graceful Degradation
The proxy must work fully without Venus MQTT. Current hardcoded values break the app if Venus OS is unreachable. After this milestone:
- No Venus config = proxy runs fine, dashboard shows inverter data only
- Venus config set but MQTT down = dashboard shows inverter data, Venus widgets greyed out
- Venus config set and MQTT up = full dashboard

## Anti-Patterns to Avoid

### Anti-Pattern: New Python Module for Auto-Detect
Do not create a separate `autodetect.py` module. The detection is a single flag set in `_handle_control_write`. Keep it inline.

### Anti-Pattern: Polling for Connection Status
Do not add a separate polling loop for MQTT status. The existing `venus_mqtt_loop` already runs continuously — just have it write status to shared_ctx.

### Anti-Pattern: WebSocket Message Types for Status
Do not add `{"type": "mqtt_status"}` WebSocket messages. Include `venus_mqtt_connected` in the existing snapshot. This follows the locked decision "extend snapshot, not protocol."

### Anti-Pattern: Frontend Framework for Config Page
Keep vanilla JS. The config page is a simple form. No React/Vue/Svelte needed.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Config key mismatch (install.sh `solaredge:` vs code `inverter:`) already exists | CERTAIN | Medium — fresh installs broken | Fix in Phase 8, or immediately |
| MQTT reconnect race condition when hot-reloading venus config | Medium | Low — worst case is duplicate MQTT connections | Cancel old task before starting new one, use asyncio.Event for clean shutdown |
| Portal ID discovery fails (Venus OS MQTT not accessible) | Low | Low — user can enter manually | Show "could not auto-discover" message, provide manual field |
| pymodbus does not expose client IP in write handlers | CERTAIN | Low — auto-detect can only detect "someone connected" not "who" | Detect via first write, prompt user for Venus IP |

## Sources

- Direct code analysis of all source files in the repository (HIGH confidence)
- Existing architecture decisions documented in PROJECT.md (HIGH confidence)
- pymodbus 3.x API (ModbusTcpServer, ModbusDeviceContext) — verified via code usage patterns (HIGH confidence)
- Venus OS MQTT topic structure — verified from existing venus_reader.py subscriptions: `N/{portal}/...`, `R/{portal}/...`, `W/{portal}/...` (HIGH confidence)
