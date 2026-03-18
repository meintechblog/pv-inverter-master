# Phase 7: Power Control - Research

**Researched:** 2026-03-18
**Domain:** Power control UI + backend refresh loop for SolarEdge SE30K via EDPC
**Confidence:** HIGH

## Summary

Phase 7 adds user-facing power control to the webapp: a read-only display of current limit state, a slider with confirmation dialog for manual testing, an enable/disable toggle, live feedback from the SE30K, Venus OS override detection, the EDPC refresh loop, and an override event log. All backend primitives exist: `ControlState` tracks limit values, `write_power_limit()` sends EDPC commands, and `async_setValues()` intercepts Venus OS writes. The gap is: (1) no source tracking in ControlState, (2) no REST endpoint for webapp-initiated writes, (3) no periodic refresh loop, (4) no override event ring buffer, (5) no frontend UI components.

The existing codebase is well-structured for extension. The webapp already has the aiohttp test client pattern, WebSocket broadcast, and Venus OS themed CSS variables. The dashboard snapshot already includes a `control` section. The WebSocket read loop in `ws_handler` has a comment "Keep connection alive; read loop for future commands (Phase 7)" -- it is explicitly ready for bidirectional messages.

**Primary recommendation:** Extend ControlState with source tracking and auto-revert timer, add POST /api/power-limit endpoint with confirmation-required semantics, implement EDPC refresh as an asyncio task, and build the frontend as a new "Power Control" nav page using existing ve-card/ve-panel patterns.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Confirmation dialog** before any power limit write -- modal with value preview
- **Venus OS always wins** -- if Venus OS writes a power limit, webapp shows "Venus OS has control" and disables manual slider
- **Webapp = test mode** -- clearly labeled as "Manual Test" to distinguish from Venus OS production control
- **Auto-revert timeout** -- webapp-initiated limits auto-revert after configurable timeout (default 5 min) as safety net
- **No accidental changes** -- slider requires explicit "Apply" button click after dragging (not real-time)
- **Read-only display** -- always visible: current power limit %, enabled/disabled, who set it, timestamp
- **Slider** -- 0-100% range, shows kW equivalent (e.g., "50% = 15.0 kW"), disabled when Venus OS has control
- **Enable/Disable toggle** -- with confirmation dialog
- **Live feedback** -- after applying, show SE30K acceptance confirmation (read-back from actual registers)
- **Status indicator** -- color-coded: green = no limit, orange = limited, red = Venus OS override active
- **EDPC Refresh Loop** -- refresh every 30s (CommandTimeout/2), only when limit actively set
- **Override detection** -- track last_source and last_change_ts in ControlState, push via WebSocket
- **Override log** -- in-memory ring buffer (last 50 events), not persistent

### Claude's Discretion
- Slider design (range input, custom styled, etc.)
- Confirmation dialog appearance and wording
- Override log layout (table, timeline, cards)
- Color coding thresholds
- Animation on value changes
- Mobile responsive behavior for control panel
- Toast/notification on override events
- Power Control placement in dashboard (new tab, inline section, or dedicated panel)

### Deferred Ideas (OUT OF SCOPE)
- None

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CTRL-04 | Read-only Anzeige -- aktueller Power Limit Wert + wer ihn gesetzt hat | Extend ControlState with last_source/last_change_ts; include in dashboard snapshot control section |
| CTRL-05 | Test-Slider mit Bestaetigungsdialog -- 0-100% mit Confirm vor Schreiben | POST /api/power-limit endpoint + frontend slider with Apply button + modal confirmation |
| CTRL-06 | Enable/Disable Toggle mit Bestaetigung | Same endpoint with enable/disable action + frontend toggle + confirmation |
| CTRL-07 | Live Feedback -- Bestaetigung vom SE30K dass Limit akzeptiert wurde | Include write result in POST response; WebSocket push updated control state on next poll |
| CTRL-08 | Venus OS Override Detection -- anzeigen wenn Venus OS die Kontrolle hat | Track source in _handle_control_write; push override events via WebSocket |
| CTRL-09 | EDPC Refresh Loop -- Backend haelt Power Limit aktiv | asyncio.Task that re-writes current limit every 30s when active |
| CTRL-10 | Override Log -- Logbuch wer wann welchen Wert gesetzt hat | In-memory deque(maxlen=50) of event dicts; exposed via snapshot and REST |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | (existing) | REST endpoint + WebSocket | Already in use, zero new dependencies |
| asyncio | stdlib | EDPC refresh task, auto-revert timer | Already the event loop |
| collections.deque | stdlib | Override event ring buffer (maxlen=50) | Proven pattern from TimeSeriesBuffer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time | stdlib | Monotonic timestamps for revert timer | Auto-revert countdown |
| json | stdlib | WebSocket message serialization | Already used in broadcast_to_clients |
| structlog | (existing) | Control event logging | Already used as control_log in proxy.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WebSocket commands | HTTP POST only | WebSocket already connected, but POST is simpler for commands. Use POST for writes, WebSocket for push-only |
| Dedicated power control WebSocket | Reuse existing /ws | Existing /ws is fine -- add message types, no new connection |

**Installation:**
```bash
# No new dependencies required
```

## Architecture Patterns

### Recommended Structure

```
Backend changes:
  control.py          # Extend ControlState + add OverrideLog + add EdpcRefreshLoop
  webapp.py           # Add POST /api/power-limit endpoint
  proxy.py            # Update _handle_control_write to set last_source="venus_os"
  dashboard.py        # Include extended control state + override log in snapshot

Frontend changes:
  static/index.html   # Add Power Control nav item + page section
  static/app.js       # Add power control UI logic (slider, toggle, confirmation, log)
  static/style.css    # Add power control component styles
```

### Pattern 1: Extended ControlState with Source Tracking

**What:** Add `last_source`, `last_change_ts`, and auto-revert fields to ControlState
**When to use:** Every control state mutation must update these fields

```python
# Extension to ControlState in control.py
import time
from collections import deque

class ControlState:
    def __init__(self) -> None:
        self.wmaxlim_ena: int = 0
        self.wmaxlimpct_raw: int = 0
        self.scale_factor: int = WMAXLIMPCT_SF
        # Phase 7 additions
        self.last_source: str = "none"          # "none" | "venus_os" | "webapp"
        self.last_change_ts: float = 0.0        # time.time() of last change
        self.webapp_revert_at: float | None = None  # monotonic deadline for auto-revert

    def set_from_webapp(self, raw_value: int, ena: int, revert_timeout: float = 300.0) -> None:
        """Update from webapp with auto-revert timer."""
        self.update_wmaxlimpct(raw_value)
        self.update_wmaxlim_ena(ena)
        self.last_source = "webapp"
        self.last_change_ts = time.time()
        self.webapp_revert_at = time.monotonic() + revert_timeout

    def set_from_venus_os(self) -> None:
        """Mark that Venus OS just wrote a control value."""
        self.last_source = "venus_os"
        self.last_change_ts = time.time()
        self.webapp_revert_at = None  # Cancel any webapp revert timer
```

### Pattern 2: Override Event Log (Ring Buffer)

**What:** In-memory deque storing last 50 control events for audit trail
**When to use:** Every control write (from any source) appends an event

```python
class OverrideLog:
    def __init__(self, maxlen: int = 50) -> None:
        self._events: deque = deque(maxlen=maxlen)

    def append(self, source: str, action: str, value: float | None, detail: str = "") -> None:
        self._events.append({
            "ts": time.time(),
            "source": source,       # "venus_os" | "webapp" | "system"
            "action": action,       # "set" | "enable" | "disable" | "revert"
            "value": value,         # limit_pct or None
            "detail": detail,       # e.g. "auto-revert after 5min"
        })

    def get_all(self) -> list[dict]:
        return list(self._events)
```

### Pattern 3: EDPC Refresh Loop (asyncio Task)

**What:** Periodic task that re-writes the current power limit to SE30K to prevent EDPC timeout revert
**When to use:** Whenever a power limit is actively enabled

```python
async def _edpc_refresh_loop(
    plugin: InverterPlugin,
    control_state: ControlState,
    override_log: OverrideLog,
    interval: float = 30.0,  # CommandTimeout/2
) -> None:
    """Periodically refresh power limit to prevent SE30K timeout revert."""
    while True:
        await asyncio.sleep(interval)
        if control_state.is_enabled and control_state.last_source != "none":
            # Check auto-revert deadline
            if (control_state.webapp_revert_at is not None
                    and time.monotonic() >= control_state.webapp_revert_at):
                # Auto-revert: disable power limiting
                await plugin.write_power_limit(False, 0.0)
                control_state.update_wmaxlim_ena(0)
                control_state.last_source = "none"
                control_state.webapp_revert_at = None
                override_log.append("system", "revert", None, "auto-revert after timeout")
                continue

            # Refresh current limit
            result = await plugin.write_power_limit(
                True, control_state.wmaxlimpct_float
            )
            if not result.success:
                logger.warning("EDPC refresh failed: %s", result.error)
```

### Pattern 4: REST Endpoint for Webapp Power Control

**What:** POST /api/power-limit accepts JSON with action and value
**When to use:** Webapp slider Apply button or enable/disable toggle

```python
async def power_limit_handler(request: web.Request) -> web.Response:
    """Handle power limit commands from webapp."""
    body = await request.json()
    action = body.get("action")  # "set" | "enable" | "disable"

    shared_ctx = request.app["shared_ctx"]
    control = shared_ctx["control_state"]
    plugin = request.app["plugin"]
    override_log = shared_ctx["override_log"]

    # Venus OS override check
    if control.last_source == "venus_os":
        age = time.time() - control.last_change_ts
        if age < 60:  # Venus OS wrote within last 60s
            return web.json_response(
                {"success": False, "error": "Venus OS is currently controlling power limit"},
                status=409,
            )

    if action == "set":
        limit_pct = float(body["limit_pct"])  # 0.0 - 100.0
        raw_value = int(limit_pct * 100)      # SF=-2: 50.0% -> 5000
        error = validate_wmaxlimpct(raw_value)
        if error:
            return web.json_response({"success": False, "error": error}, status=400)
        result = await plugin.write_power_limit(True, limit_pct)
        if result.success:
            control.set_from_webapp(raw_value, 1)
            override_log.append("webapp", "set", limit_pct)
        return web.json_response({"success": result.success, "error": result.error})

    # ... enable/disable actions similar
```

### Pattern 5: WebSocket Push for Override Events

**What:** Broadcast override events via existing WebSocket to all clients
**When to use:** When Venus OS takes control or auto-revert triggers

The existing `broadcast_to_clients()` sends `{"type": "snapshot", "data": ...}`. Add new message types:

```python
# New broadcast message types:
{"type": "snapshot", "data": {...}}           # existing - now includes extended control
{"type": "override_event", "data": {...}}     # new - pushed on Venus OS override or revert
```

### Anti-Patterns to Avoid
- **Real-time slider writes:** Never send Modbus writes on slider `oninput` events. Only on explicit Apply click.
- **Client-side state for control:** Always use server-authoritative state. Never cache limit values in browser JS as truth.
- **Bypassing Venus OS priority:** Never allow webapp to write when Venus OS recently wrote. The 409 response is mandatory.
- **Fire-and-forget writes:** Always check WriteResult.success and report back to the user.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Confirmation dialog | Custom modal from scratch | Simple HTML dialog element or overlay div | Standard pattern, accessible, works on mobile |
| Auto-revert timer | setTimeout on client | Server-side monotonic deadline in EDPC refresh loop | Client disconnect must not prevent revert |
| Ring buffer | Custom list with manual trim | collections.deque(maxlen=50) | Thread-safe append, auto-eviction, proven in codebase |
| WebSocket message routing | if/else chain | Message type dispatch object | Already the pattern in app.js onmessage |

**Key insight:** The auto-revert MUST be server-side. If the user closes the browser tab, the server must still revert the power limit after timeout. The EDPC refresh loop is the natural place for this check.

## Common Pitfalls

### Pitfall 1: Race Between Venus OS and Webapp Writes
**What goes wrong:** Webapp sets 100% while Venus OS just sent 50% for ESS feed-in limiting
**Why it happens:** Two independent write paths, no arbitration
**How to avoid:** Track `last_source` and `last_change_ts`. If Venus OS wrote within last 60s, reject webapp writes with 409. Update `_handle_control_write` in proxy.py to set `last_source = "venus_os"` immediately.
**Warning signs:** `last_source` flipping rapidly between "venus_os" and "webapp" in override log

### Pitfall 2: EDPC Timeout Causes Silent Revert
**What goes wrong:** Power limit set once but SE30K reverts to fallback after CommandTimeout (60s)
**Why it happens:** No periodic refresh of the EDPC command
**How to avoid:** EDPC refresh loop writes current limit every 30s. Only active when `is_enabled and last_source != "none"`.
**Warning signs:** Dashboard shows limit but actual inverter output exceeds it

### Pitfall 3: Auto-Revert on Client Side Gets Lost
**What goes wrong:** User sets limit, closes browser, limit stays forever
**Why it happens:** Client-side timer dies with tab close
**How to avoid:** Server-side `webapp_revert_at` monotonic deadline checked in EDPC refresh loop. No client involvement needed.
**Warning signs:** `webapp_revert_at` is not None but no revert happens

### Pitfall 4: Stale Control State After Reconnect
**What goes wrong:** Browser reconnects WebSocket but shows old control state
**Why it happens:** WebSocket reconnect doesn't fetch full state
**How to avoid:** Already handled -- `ws_handler` sends latest snapshot on connect, which includes control section. Extend control section with new fields.
**Warning signs:** Control UI shows "webapp" as source but server says "venus_os"

### Pitfall 5: Confirmation Dialog Bypassed by Direct API Call
**What goes wrong:** Someone curls POST /api/power-limit without confirmation
**Why it happens:** Confirmation is client-side only
**How to avoid:** This is acceptable for a LAN tool. The confirmation dialog prevents accidental UI clicks, not malicious API calls. The 5-min auto-revert is the real safety net.
**Warning signs:** N/A -- by design

## Code Examples

### Backend: Extend dashboard snapshot with control state

```python
# In dashboard.py DashboardCollector.collect(), extend control section:
control: dict = {}
if control_state is not None:
    control = {
        "enabled": control_state.is_enabled,
        "limit_pct": control_state.wmaxlimpct_float,
        "wmaxlimpct_raw": control_state.wmaxlimpct_raw,
        # Phase 7 additions:
        "last_source": control_state.last_source,
        "last_change_ts": control_state.last_change_ts,
        "revert_remaining_s": _revert_remaining(control_state),
    }
```

### Backend: Update proxy.py _handle_control_write for source tracking

```python
# In proxy.py _handle_control_write, after successful write:
self._control.last_source = "venus_os"
self._control.last_change_ts = time.time()
self._control.webapp_revert_at = None  # Venus OS cancels webapp revert

# Also log override event:
if shared_ctx and "override_log" in shared_ctx:
    shared_ctx["override_log"].append(
        "venus_os", "set", self._control.wmaxlimpct_float
    )
```

### Frontend: Power Control page structure

```html
<!-- New nav item in sidebar -->
<a class="nav-item" data-page="power">
  <svg class="nav-icon" ...><!-- power icon --></svg>
  <span class="nav-label">Power Control</span>
</a>

<!-- New page section -->
<div id="page-power" class="page">
  <div class="ve-card">
    <h2 class="ve-card-title">Power Control <span class="ve-badge ve-badge--test">Manual Test</span></h2>
    <!-- Status indicator -->
    <div id="ctrl-status" class="ve-ctrl-status">
      <span class="ve-dot" id="ctrl-dot"></span>
      <span id="ctrl-label">No limit active</span>
    </div>
    <!-- Read-only display -->
    <div class="ve-ctrl-readout">
      <div><label>Current Limit</label><span id="ctrl-limit">--</span></div>
      <div><label>Source</label><span id="ctrl-source">--</span></div>
      <div><label>Last Changed</label><span id="ctrl-ts">--</span></div>
    </div>
    <!-- Slider (disabled when Venus OS controls) -->
    <div class="ve-ctrl-slider-group" id="ctrl-slider-group">
      <input type="range" min="0" max="100" value="100" id="ctrl-slider" class="ve-ctrl-slider">
      <div class="ve-ctrl-slider-labels">
        <span>0%</span>
        <span id="ctrl-slider-value">100% = 30.0 kW</span>
        <span>100%</span>
      </div>
      <div class="ve-button-group">
        <button id="ctrl-apply" class="ve-btn ve-btn--primary">Apply</button>
        <button id="ctrl-toggle" class="ve-btn">Enable</button>
      </div>
    </div>
    <!-- Revert countdown -->
    <div id="ctrl-revert" class="ve-ctrl-revert" style="display:none">
      Auto-revert in: <span id="ctrl-revert-time">5:00</span>
    </div>
  </div>
  <!-- Override Log -->
  <div class="ve-card">
    <h2 class="ve-card-title">Override Log</h2>
    <div id="override-log" class="ve-override-log">
      <div class="ve-text-dim">No events yet</div>
    </div>
  </div>
</div>
```

### Frontend: Confirmation dialog pattern

```javascript
function showConfirmDialog(message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 've-modal-overlay';
    overlay.innerHTML = `
        <div class="ve-modal">
            <div class="ve-modal-body">${message}</div>
            <div class="ve-modal-actions">
                <button class="ve-btn" id="modal-cancel">Cancel</button>
                <button class="ve-btn ve-btn--danger" id="modal-confirm">Confirm</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#modal-cancel').onclick = () => overlay.remove();
    overlay.querySelector('#modal-confirm').onclick = () => {
        overlay.remove();
        onConfirm();
    };
}
```

### Frontend: Slider with kW preview (no real-time writes)

```javascript
const slider = document.getElementById('ctrl-slider');
const sliderValue = document.getElementById('ctrl-slider-value');

slider.addEventListener('input', () => {
    const pct = parseInt(slider.value);
    const kw = (pct / 100 * 30).toFixed(1);
    sliderValue.textContent = pct + '% = ' + kw + ' kW';
    // NO write here -- only preview
});

document.getElementById('ctrl-apply').addEventListener('click', () => {
    const pct = parseInt(slider.value);
    const kw = (pct / 100 * 30).toFixed(1);
    showConfirmDialog(
        'Set power limit to <strong>' + pct + '% (' + kw + ' kW)</strong>?<br>' +
        'This limit will auto-revert after 5 minutes.',
        () => applyPowerLimit(pct)
    );
});

async function applyPowerLimit(pct) {
    const res = await fetch('/api/power-limit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'set', limit_pct: pct})
    });
    const data = await res.json();
    // Show result toast
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fire-and-forget EDPC write | Periodic refresh loop | SE30K CommandTimeout discovery | Must refresh every 30s |
| Single write path (Modbus only) | Dual path (Modbus + REST) with arbitration | Phase 7 | Source priority tracking needed |
| No control UI | Webapp test bench with safety confirmations | Phase 7 | User can test power limiting safely |

## Open Questions

1. **SE30K CommandTimeout exact value**
   - What we know: Default is believed to be 60s based on community reports
   - What's unclear: Actual configured value on the target SE30K at 192.168.3.18
   - Recommendation: Read register 0xF310 at startup and set refresh interval to half. Default to 30s if read fails.

2. **Venus OS write frequency**
   - What we know: Venus OS writes Model 123 via Modbus when ESS needs power limiting
   - What's unclear: How frequently Venus OS writes when actively controlling (every second? Every 10s? Only on change?)
   - Recommendation: The 60s "last Venus OS write" window for rejecting webapp writes may need tuning. Start with 60s, log and observe.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-04 | ControlState has last_source/last_change_ts, snapshot includes them | unit | `pytest tests/test_control.py -x` | Extend existing |
| CTRL-05 | POST /api/power-limit sets limit with validation | unit | `pytest tests/test_webapp.py::test_power_limit -x` | Wave 0 |
| CTRL-06 | POST /api/power-limit enable/disable actions work | unit | `pytest tests/test_webapp.py::test_power_limit_toggle -x` | Wave 0 |
| CTRL-07 | POST response includes success/error from WriteResult | unit | `pytest tests/test_webapp.py::test_power_limit_feedback -x` | Wave 0 |
| CTRL-08 | Venus OS write sets last_source="venus_os", webapp rejected with 409 | unit | `pytest tests/test_proxy.py::test_venus_override -x` | Wave 0 |
| CTRL-09 | EDPC refresh loop re-writes limit every interval, handles auto-revert | unit | `pytest tests/test_control.py::test_edpc_refresh -x` | Wave 0 |
| CTRL-10 | OverrideLog stores events, maxlen enforced, serializable | unit | `pytest tests/test_control.py::test_override_log -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before verify

### Wave 0 Gaps
- [ ] `tests/test_control.py` -- extend with ControlState.last_source, OverrideLog, EDPC refresh tests
- [ ] `tests/test_webapp.py` -- add POST /api/power-limit tests (valid set, enable, disable, Venus OS rejection 409)
- [ ] `tests/test_proxy.py` -- add Venus OS override detection test (_handle_control_write sets last_source)

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `control.py`, `proxy.py`, `webapp.py`, `dashboard.py`, `app.js`, `index.html`, `style.css`
- Existing test suite: `test_control.py`, `test_webapp.py`, `test_proxy.py` (patterns verified)
- `.planning/research/PITFALLS.md` -- Pitfalls 1-3 (power control safety, race conditions, EDPC timeout)

### Secondary (MEDIUM confidence)
- SolarEdge EDPC CommandTimeout behavior (community reports, SolarEdge application notes referenced in PITFALLS.md)
- SE30K default CommandTimeout = 60s (from community discussion, needs field verification)

### Tertiary (LOW confidence)
- Venus OS write frequency for ESS power limiting (no direct source, needs observation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all existing patterns
- Architecture: HIGH -- direct extension of existing ControlState, webapp, and WebSocket patterns
- Pitfalls: HIGH -- thoroughly documented in PITFALLS.md with codebase-specific analysis
- Frontend patterns: MEDIUM -- UI implementation details are Claude's discretion, patterns match existing codebase

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain, no external dependency changes expected)
