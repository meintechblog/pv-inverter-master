# Phase 14: Config Page & Dashboard UX - Research

**Researched:** 2026-03-19
**Domain:** Web UI config form, live connection status, MQTT-gated dashboard elements
**Confidence:** HIGH

## Summary

Phase 14 is a pure frontend+API phase. Phase 13 shipped all backend infrastructure: VenusConfig dataclass, parameterized MQTT loop, CONNACK validation, portal ID auto-discovery, connection state in shared_ctx, and dashboard snapshot with `venus_mqtt_connected`. Phase 14 wires this into the user-facing config page and dashboard.

The scope is four requirements: (1) config page with pre-filled defaults for both inverter and Venus OS fields, (2) live connection bobbles replacing the Test Connection button, (3) MQTT setup guide card when Venus OS is not connected, and (4) dashboard MQTT-gate that greys out Venus-dependent widgets until MQTT is confirmed connected. No new Python modules or dependencies are needed -- it is API endpoint extensions in webapp.py and frontend changes in index.html/app.js/style.css.

**Primary recommendation:** Build backend API changes first (extend config GET/POST for venus fields, add venus config save with hot-reload), then frontend in a single pass (config page Venus section, connection bobbles, MQTT gate CSS, setup guide card).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | Config Page shows pre-filled defaults (192.168.3.18:1502, Unit 1) on first visit | `config_get_handler` already returns inverter config; extend to return venus config. Frontend `loadConfig()` already populates form fields. Add venus fields to both. |
| CFG-02 | After Save & Apply, live connection bobble (green/red/amber) shows SolarEdge and MQTT connection status | `venus_mqtt_connected` already in dashboard snapshot (Phase 13). `connection.state` already tracks SolarEdge. Drive bobbles from WebSocket snapshot data, not polling. |
| SETUP-02 | MQTT setup guide card when MQTT not connected | Pure frontend: show/hide an info card based on `venus_mqtt_connected` from snapshot. Card content is static text explaining Venus OS Remote Console path. |
| SETUP-03 | Dashboard MQTT-gate -- Lock Toggle, Override, Venus Settings greyed out with overlay hint until MQTT connected | CSS `.mqtt-gated` class on Venus-dependent widget containers. JS toggles class based on `venus_mqtt_connected` from snapshot. |
</phase_requirements>

## Standard Stack

### Core (unchanged from project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | >=3.10,<4.0 | HTTP server, REST endpoints, WebSocket | Already serves the webapp; extend existing handlers |
| PyYAML | >=6.0,<7.0 | Config persistence | Already used for config save/load |
| Vanilla JS | N/A | Frontend logic | Project convention; no framework needed for form + CSS toggle |

### Supporting (no additions needed)
No new dependencies required. All changes use existing infrastructure.

## Architecture Patterns

### Current State (Post-Phase 13)

**Backend data flow (already working):**
```
config.yaml -> Config.venus (host/port/portal_id)
    -> venus_mqtt_loop(shared_ctx, host, port, portal_id)
    -> shared_ctx["venus_mqtt_connected"] = True/False
    -> dashboard.collect() includes venus_mqtt_connected in snapshot
    -> broadcast_to_clients() sends snapshot via WebSocket
    -> browser receives { venus_mqtt_connected: true/false }
```

**What Phase 14 adds:**
```
Config Page:
  GET /api/config -> returns { inverter: {...}, venus: {...} }
  POST /api/config -> saves both inverter + venus, hot-reloads MQTT

Dashboard:
  snapshot.venus_mqtt_connected -> toggle .mqtt-gated class on Venus widgets
  snapshot.venus_mqtt_connected -> show/hide setup guide card
  snapshot.connection.state -> drive SolarEdge bobble color
  snapshot.venus_mqtt_connected -> drive Venus OS bobble color
```

### Pattern 1: Config GET/POST Extension
**What:** Extend existing `config_get_handler` and `config_save_handler` to include venus fields.
**When to use:** Config page needs to read and write both inverter and venus config.
**Implementation:**

```python
# config_get_handler - extend return value
async def config_get_handler(request):
    config = request.app["config"]
    return web.json_response({
        "inverter": {
            "host": config.inverter.host,
            "port": config.inverter.port,
            "unit_id": config.inverter.unit_id,
        },
        "venus": {
            "host": config.venus.host,
            "port": config.venus.port,
            "portal_id": config.venus.portal_id,
        },
    })
```

**CRITICAL: Backward compatibility.** The existing `loadConfig()` in app.js reads `data.host`, `data.port`, `data.unit_id` at the top level. The new response nests under `data.inverter.*`. Must update JS simultaneously.

### Pattern 2: Venus MQTT Hot-Reload on Config Save
**What:** When user saves Venus config, cancel existing `venus_task` and start new one with updated params.
**When to use:** After `config_save_handler` writes venus config to YAML.
**Implementation:**

```python
# In config_save_handler (or new venus_config_save_handler):
# 1. Validate venus config
# 2. Save to config.yaml atomically
# 3. Cancel old venus_task
old_task = shared_ctx.get("venus_task")
if old_task and not old_task.done():
    old_task.cancel()
    try:
        await old_task
    except asyncio.CancelledError:
        pass
# 4. Start new venus_mqtt_loop with updated params
if config.venus.host:
    from venus_os_fronius_proxy.venus_reader import venus_mqtt_loop
    new_task = asyncio.create_task(
        venus_mqtt_loop(shared_ctx, config.venus.host, config.venus.port, config.venus.portal_id)
    )
    shared_ctx["venus_task"] = new_task
else:
    shared_ctx["venus_mqtt_connected"] = False
```

**Design decision: Single save endpoint vs. separate.** Use a SINGLE `POST /api/config` that accepts both inverter and venus sections. Reason: simpler frontend (one "Save & Apply" button), atomic config write, and the existing pattern already works this way. The handler detects which sections changed and only hot-reloads what's needed.

### Pattern 3: Connection Bobble from WebSocket Snapshot
**What:** Replace the "Test Connection" button with live connection status dots driven by WebSocket data.
**When to use:** Config page and dashboard sidebar.
**Implementation:**

Bobble states:
- **Green (pulsing)** = connected (`connection.state === "connected"` for SolarEdge, `venus_mqtt_connected === true` for Venus)
- **Amber (pulsing)** = reconnecting/configuring (`connection.state === "reconnecting"` or transient)
- **Red (static)** = configured but disconnected
- **Grey (static)** = not configured (venus host empty)

CSS for pulsing dot:
```css
@keyframes ve-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
.ve-dot--ok { background: var(--ve-green); animation: ve-pulse 2s ease-in-out infinite; }
.ve-dot--warn { background: var(--ve-orange); animation: ve-pulse 1.5s ease-in-out infinite; }
```

Data source: The WebSocket already sends snapshots every ~1s. The config page JS reads `data.connection.state` and `data.venus_mqtt_connected` from the same WebSocket connection already open on dashboard. When user navigates to config page, the last snapshot is immediately available.

### Pattern 4: MQTT Gate (CSS Grey-out)
**What:** Wrap Venus-dependent dashboard widgets in a container div. Toggle `.mqtt-gated` class based on `venus_mqtt_connected`.
**When to use:** Dashboard page, applied to: Venus OS Lock toggle, Venus OS ESS panel, Override log.
**Implementation:**

**Keep enabled WITHOUT MQTT (inverter-only features):**
- Power gauge + phase cards + sparklines
- Inverter status panel
- Power control slider (min/max clamp)
- Today's Performance
- Service Health
- Connection panel

**Grey out WITH overlay hint (Venus-dependent):**
- Venus OS Lock toggle (`#venus-lock-container`)
- Venus OS ESS panel (`#venus-ess-panel`)
- Grid power values within Venus ESS

```css
.mqtt-gated {
    position: relative;
    opacity: 0.35;
    pointer-events: none;
    transition: opacity var(--ve-duration-normal) var(--ve-easing-default);
}
.mqtt-gated::after {
    content: 'Requires Venus OS MQTT connection';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--ve-text-dim);
    font-size: 0.85rem;
    text-align: center;
    white-space: nowrap;
    pointer-events: none;
}
```

```javascript
// In handleSnapshot():
function updateMqttGate(snapshot) {
    const gated = document.querySelectorAll('.venus-dependent');
    const connected = snapshot.venus_mqtt_connected;
    gated.forEach(el => {
        if (connected) {
            el.classList.remove('mqtt-gated');
        } else {
            el.classList.add('mqtt-gated');
        }
    });
}
```

### Pattern 5: MQTT Setup Guide Card
**What:** Inline hint card shown when MQTT is not connected. Static text with step-by-step instructions.
**When to use:** Config page and/or dashboard when `venus_mqtt_connected === false` and `config.venus.host !== ""`.

Two states:
1. **Venus not configured** (host empty): "Enter your Venus OS IP address above to enable MQTT integration."
2. **Venus configured but disconnected**: "MQTT connection failed. Ensure MQTT on LAN is enabled: Venus OS Remote Console -> Settings -> Services -> MQTT on LAN."

```html
<div id="mqtt-setup-guide" class="ve-hint-card" style="display:none">
    <h3>Enable MQTT on Venus OS</h3>
    <ol>
        <li>Open Venus OS Remote Console</li>
        <li>Navigate to Settings -> Services</li>
        <li>Enable "MQTT on LAN"</li>
        <li>Return here and click Save & Apply</li>
    </ol>
</div>
```

### Anti-Patterns to Avoid

- **Separate polling for connection status on config page:** Do NOT add a `/api/status` poll on config page. Use the existing WebSocket connection that is already open. The snapshot contains all status data.
- **New WebSocket message types:** Do NOT add `{"type": "mqtt_status"}`. Include status in existing snapshot (already done by Phase 13).
- **Frontend framework:** Do NOT introduce React/Vue/Svelte for the config page form. Vanilla JS is the project convention and 4 form fields do not warrant a framework.
- **Separate venus config save endpoint:** Do NOT create `POST /api/config/venus` separate from the existing config endpoint. Use a single unified config save.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IP validation (frontend) | Custom regex | `pattern` attr on input + existing `validate_venus_config` on backend | HTML5 validation covers format; backend catches edge cases |
| Connection status debounce | Custom timer system | CSS transition + 2-snapshot confirmation | Simple: only change bobble color if 2 consecutive snapshots agree |
| Config hot-reload race | Manual mutex/lock | asyncio task cancellation (already used for proxy_task pattern) | `old_task.cancel(); await old_task` is the standard asyncio pattern |
| Portal ID auto-discovery UX | Manual user workflow | Trigger `discover_portal_id()` on venus config save when portal_id is empty | Phase 13 already built `discover_portal_id()`; just call it |

## Common Pitfalls

### Pitfall 1: Config GET/POST Response Format Change Breaks Frontend
**What goes wrong:** Changing config GET response from flat `{host, port, unit_id}` to nested `{inverter: {host, port, unit_id}, venus: {...}}` without updating app.js simultaneously breaks the config page.
**Why it happens:** Backend and frontend changes deployed in different tasks.
**How to avoid:** Backend config handler change and frontend `loadConfig()` update MUST be in the same task. Test config page load after change.
**Warning signs:** Config page shows empty fields after save.

### Pitfall 2: Venus MQTT Hot-Reload Creates Duplicate Tasks
**What goes wrong:** Saving venus config without cancelling the old `venus_task` creates parallel MQTT connections. Both write to `shared_ctx`, causing flapping `venus_mqtt_connected` state.
**Why it happens:** Missing task cancellation before starting new task.
**How to avoid:** Always cancel+await the old task before creating a new one. Check `shared_ctx["venus_task"]` exists and is not done.
**Warning signs:** `venus_mqtt_connected` rapidly alternating between true/false.

### Pitfall 3: MQTT Gate Blocks Power Slider When It Should Not
**What goes wrong:** Power control slider (min/max clamp) is inside a greyed-out container because it was grouped with Venus-dependent widgets.
**Why it happens:** Incorrect HTML nesting -- power slider is adjacent to Venus OS controls.
**How to avoid:** The MQTT gate wrapper must ONLY contain Venus-dependent elements. Power gauge card, power slider, and inverter status are NOT Venus-dependent. Verify by checking: "Does this feature work without MQTT?" If yes, do not gate it.
**Warning signs:** User cannot control power limit when Venus OS is disconnected.

### Pitfall 4: Connection Bobble Shows Green Before Data Arrives
**What goes wrong:** `venus_mqtt_connected = True` is set in `venus_reader.py` immediately after CONNACK, before any subscription data arrives. The bobble shows green but dashboard shows stale/empty Venus data.
**Why it happens:** Connected != data flowing.
**How to avoid:** Accept this behavior. The bobble correctly shows "MQTT transport connected." Venus ESS widgets will populate within 1-2 seconds as MQTT messages arrive. Do NOT add artificial delay to the bobble.
**Warning signs:** Brief moment where bobble is green but ESS panel shows "--". This is acceptable.

### Pitfall 5: Config Page Not Receiving WebSocket Snapshots
**What goes wrong:** Connection bobbles on config page never update because the WebSocket connection is only used on the dashboard page.
**Why it happens:** The existing `connectWebSocket()` runs on DOMContentLoaded and is page-independent. Snapshots arrive regardless of which page is active. The issue would be if snapshot handling only updates dashboard elements.
**How to avoid:** Ensure `handleSnapshot()` also updates config page bobbles. Check for element existence before updating (elements may not be visible).
**Warning signs:** Bobbles remain grey even when services are connected.

### Pitfall 6: Status Handler Still Returns Hardcoded "active" for Venus OS
**What goes wrong:** `status_handler` in webapp.py currently returns `"venus_os": "active"` hardcoded. This must be updated to reflect actual MQTT connection state.
**Why it happens:** Pre-Phase 13 code that was not updated.
**How to avoid:** Update `status_handler` to read `shared_ctx.get("venus_mqtt_connected", False)` and return appropriate status string.
**Warning signs:** `/api/status` always shows venus_os: active even when disconnected.

## Code Examples

### Extending config_get_handler (webapp.py)
```python
async def config_get_handler(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    return web.json_response({
        "inverter": {
            "host": config.inverter.host,
            "port": config.inverter.port,
            "unit_id": config.inverter.unit_id,
        },
        "venus": {
            "host": config.venus.host,
            "port": config.venus.port,
            "portal_id": config.venus.portal_id,
        },
    })
```

### Extending config_save_handler for Venus hot-reload (webapp.py)
```python
async def config_save_handler(request: web.Request) -> web.Response:
    body = await request.json()

    # Inverter section (existing)
    inv = body.get("inverter", {})
    # ... validate and save inverter config ...

    # Venus section (new)
    venus = body.get("venus", {})
    venus_host = venus.get("host", "").strip()
    venus_port = venus.get("port", 1883)
    venus_portal_id = venus.get("portal_id", "").strip()

    if venus_host:
        error = validate_venus_config(venus_host, venus_port)
        if error:
            return web.json_response({"success": False, "error": error}, status=400)

    config = request.app["config"]
    venus_changed = (
        config.venus.host != venus_host
        or config.venus.port != venus_port
        or config.venus.portal_id != venus_portal_id
    )

    config.venus.host = venus_host
    config.venus.port = venus_port
    config.venus.portal_id = venus_portal_id
    save_config(request.app["config_path"], config)

    # Hot-reload MQTT if venus config changed
    if venus_changed:
        shared_ctx = request.app["shared_ctx"]
        old_task = shared_ctx.get("venus_task")
        if old_task and not old_task.done():
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass

        if venus_host:
            from venus_os_fronius_proxy.venus_reader import venus_mqtt_loop
            portal = venus_portal_id  # empty = auto-discover
            new_task = asyncio.create_task(
                venus_mqtt_loop(shared_ctx, venus_host, venus_port, portal)
            )
            shared_ctx["venus_task"] = new_task
        else:
            shared_ctx["venus_mqtt_connected"] = False
            shared_ctx.pop("venus_task", None)

    return web.json_response({"success": True})
```

### Frontend loadConfig update (app.js)
```javascript
async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        // Inverter fields
        document.getElementById('se-host').value = data.inverter.host;
        document.getElementById('se-port').value = data.inverter.port;
        document.getElementById('se-unit').value = data.inverter.unit_id;
        // Venus fields
        document.getElementById('venus-host').value = data.venus.host;
        document.getElementById('venus-port').value = data.venus.port;
        document.getElementById('venus-portal-id').value = data.venus.portal_id;
    } catch (e) {
        console.error('Config load failed:', e);
    }
}
```

### MQTT Gate toggle in handleSnapshot (app.js)
```javascript
function updateMqttGate(snapshot) {
    var mqttConnected = snapshot.venus_mqtt_connected;
    var gatedEls = document.querySelectorAll('.venus-dependent');
    for (var i = 0; i < gatedEls.length; i++) {
        if (mqttConnected) {
            gatedEls[i].classList.remove('mqtt-gated');
        } else {
            gatedEls[i].classList.add('mqtt-gated');
        }
    }
    // Setup guide visibility
    var guideCard = document.getElementById('mqtt-setup-guide');
    if (guideCard) {
        var venusHost = document.getElementById('venus-host');
        var hostConfigured = venusHost && venusHost.value.trim() !== '';
        if (!mqttConnected && hostConfigured) {
            guideCard.style.display = '';
        } else {
            guideCard.style.display = 'none';
        }
    }
}
```

## State of the Art

| Old Approach (pre-Phase 13) | Current Approach (post-Phase 13) | Impact on Phase 14 |
|-----|-----|-----|
| Venus host hardcoded in 5 places | VenusConfig dataclass, all references use config | Config page can read/write venus config via existing pattern |
| No MQTT connection state tracking | `shared_ctx["venus_mqtt_connected"]` in snapshot | Frontend can drive bobbles and MQTT gate directly from snapshot |
| CONNACK never validated | CONNACK return code checked, ConnectionError raised | Connection bobble accurately reflects transport state |
| Portal ID hardcoded | Auto-discovery via `discover_portal_id()` | Config page can offer "leave blank for auto-discovery" |
| `status_handler` returns `"venus_os": "active"` hardcoded | Still hardcoded -- **must be fixed in Phase 14** | Update to read actual connection state from shared_ctx |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | Config GET returns both inverter and venus sections | unit | `python -m pytest tests/test_webapp.py::test_config_get_returns_venus -x` | Wave 0 |
| CFG-01 | Config GET returns pre-filled defaults for venus (empty host, port 1883) | unit | `python -m pytest tests/test_webapp.py::test_config_get_venus_defaults -x` | Wave 0 |
| CFG-02 | Config POST saves venus fields and hot-reloads MQTT | unit | `python -m pytest tests/test_webapp.py::test_config_save_venus -x` | Wave 0 |
| CFG-02 | Status handler returns real venus_mqtt_connected state | unit | `python -m pytest tests/test_webapp.py::test_status_venus_mqtt_state -x` | Wave 0 |
| SETUP-02 | Setup guide visibility logic (JS) | manual-only | Visual: navigate to config page, verify guide card shows when MQTT disconnected | N/A |
| SETUP-03 | Dashboard MQTT gate applied to Venus-dependent widgets | manual-only | Visual: verify Venus ESS and lock toggle are greyed when MQTT disconnected | N/A |
| SETUP-03 | Power gauge, slider, inverter status remain functional without MQTT | manual-only | Visual: verify inverter-only features work with venus.host="" | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_webapp.py::test_config_get_returns_venus` -- covers CFG-01 config response structure
- [ ] `tests/test_webapp.py::test_config_save_venus` -- covers CFG-02 venus config save
- [ ] `tests/test_webapp.py::test_status_venus_mqtt_state` -- covers CFG-02 status endpoint fix

## Open Questions

1. **Portal ID auto-discovery trigger on save**
   - What we know: `discover_portal_id()` exists and works. When venus config is saved with empty portal_id, the MQTT loop will auto-discover.
   - What's unclear: Should the config save response include the discovered portal_id so the UI can display it? Currently the discovery happens in the background MQTT loop.
   - Recommendation: Let the MQTT loop discover in background. The config page does not need to show portal_id -- it is an internal detail. The connection bobble turning green is sufficient feedback.

2. **Test Connection button -- remove or keep?**
   - What we know: Requirements say "Test Connection button replaced by live connection bobble." The existing Test Connection button tests SolarEdge Modbus connectivity.
   - What's unclear: Should SolarEdge test also be removed, or only Venus OS test is replaced by bobble?
   - Recommendation: Remove the Test Connection button entirely. The live bobble provides faster feedback than a manual test. The SolarEdge bobble turns green/red immediately after Save & Apply via the existing `plugin.reconfigure()` + `conn_mgr.state` flow. Keep `/api/config/test` endpoint for backward compatibility but remove the button from the UI.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all source files (webapp.py, config.py, venus_reader.py, __main__.py, dashboard.py, app.js, index.html, style.css) -- current state post-Phase 13
- Phase 13 summaries (13-01-SUMMARY.md, 13-02-SUMMARY.md) -- what was shipped
- REQUIREMENTS.md -- CFG-01, CFG-02, SETUP-02, SETUP-03 definitions

### Secondary (MEDIUM confidence)
- Project research (ARCHITECTURE.md, FEATURES.md, SUMMARY.md) -- architecture patterns and feature analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all changes within existing modules
- Architecture: HIGH - all integration points directly observed in code, data flow verified end-to-end
- Pitfalls: HIGH - all pitfalls derived from actual code analysis (e.g., hardcoded status_handler, config response format change)

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain, no external dependency changes)
