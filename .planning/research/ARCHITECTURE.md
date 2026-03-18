# Architecture Patterns: v2.1 Dashboard Redesign & Polish

**Domain:** Embedded web dashboard for Modbus proxy (vanilla JS, aiohttp backend)
**Researched:** 2026-03-18

## Current Architecture Summary

```
proxy.py (_poll_loop) --> dashboard.py (DashboardCollector.collect)
                      --> webapp.py (broadcast_to_clients) --> WebSocket --> app.js

app.js: handleSnapshot(data) updates all dashboard widgets
        handleHistory(data) populates sparklines on connect

index.html: 4 "pages" (show/hide sections):
  - page-dashboard (gauge, phases, sparkline, inverter status, connection, health)
  - page-config (SolarEdge IP/port form)
  - page-registers (register viewer)
  - page-power (power control: slider, toggle, override log)
```

### Data Flow (Current)
1. `_poll_loop` polls SE30K every 1s via plugin
2. On success: `DashboardCollector.collect()` produces snapshot dict
3. `broadcast_to_clients()` pushes `{type: "snapshot", data: {...}}` to all WS clients
4. `app.js handleSnapshot()` updates DOM elements by ID

### Snapshot Structure (Current)
```json
{
  "ts": 1710754800.0,
  "inverter": { "ac_power_w", "ac_current_l1_a", ..., "status", "temperature_*", "dc_*", "daily_energy_wh" },
  "control": { "enabled", "limit_pct", "last_source", "revert_remaining_s", ... },
  "connection": { "state", "poll_success", "poll_total", "cache_stale" },
  "override_log": [{ "ts", "source", "action", "value", "detail" }]
}
```

## Recommended Architecture for v2.1

### Principle: Minimal Backend Changes

The existing snapshot already contains all data needed for most v2.1 features. The backend needs only two small additions (peak stats tracking, Venus OS details). Everything else is frontend restructuring.

### Component Boundaries

| Component | Responsibility | Changes for v2.1 |
|-----------|---------------|-------------------|
| `dashboard.py` (DashboardCollector) | Decode registers, produce snapshot | ADD: peak stats tracking (peak_kw, operating_hours, efficiency) |
| `webapp.py` (routes + WS) | Serve API, push snapshots | ADD: Venus OS info fields to status endpoint OR snapshot |
| `proxy.py` (_poll_loop) | Poll, broadcast | NO CHANGES |
| `control.py` (ControlState) | Track power limit state | NO CHANGES |
| `connection.py` (ConnectionManager) | Track SE30K connection | NO CHANGES -- already exposes state |
| `index.html` | Page structure, HTML skeleton | RESTRUCTURE: merge power control into dashboard, add Venus OS widget, toast container |
| `style.css` | Venus OS themed styles | ADD: animations, toast stacking, lock toggle, compact power control styles |
| `app.js` | WS client, DOM updates | RESTRUCTURE: remove page-power nav, inline power control, add toast system, add Venus OS widget updates, add animations |

### Data Flow Changes

```
EXISTING (unchanged):
  _poll_loop --> DashboardCollector.collect() --> broadcast --> WS --> handleSnapshot()

NEW additions to snapshot:
  DashboardCollector.collect() now also produces:
    snapshot.inverter.peak_power_w      (tracked in-memory, reset on restart)
    snapshot.inverter.operating_hours   (time when status=MPPT, in-memory)
    snapshot.inverter.efficiency_pct    (ac_power/dc_power ratio)

  snapshot.venus_os section (NEW):
    Populated from shared_ctx data already available:
    - control_state.last_source, last_change_ts  (already in snapshot.control)
    - conn_mgr connection state for Venus OS side  (needs: track last Venus OS Modbus read)
```

## Feature Integration Analysis

### Feature 1: Unified Dashboard (Power Control Inline)

**What changes:**
- `index.html`: Remove `page-power` section entirely. Move its content (slider, toggle, override banner, revert countdown) into `page-dashboard` as a new card between sparkline and bottom grid.
- `app.js`: Remove power control nav item click handler. Keep all `updatePowerControl()` logic -- it already updates by element ID regardless of which page section they are in. Remove the `page-power` nav-item event listener reference.
- `style.css`: Add compact power control card styles (`.ve-ctrl-inline`). The existing power control CSS already works; just needs a compact variant for the inline card.
- Sidebar nav: Remove "Power Control" nav-item from HTML. Keep Dashboard, Config, Registers.

**Backend changes:** NONE. The snapshot already includes `control` section and `override_log`.

**Risk:** LOW. This is purely HTML restructuring. All JS functions update by element ID, not by page context.

### Feature 2: Venus OS Info Widget

**What changes:**
- `index.html`: Add a new card in dashboard bottom grid showing Venus OS connection info.
- `dashboard.py`: Add Venus OS tracking fields to snapshot:
  - `venus_os.last_read_ts`: timestamp of last Modbus read from Venus OS (track in StalenessAwareSlaveContext.getValues)
  - `venus_os.connected`: bool (last read within ~10s)
  - `venus_os.ip`: from last connection (if available from pymodbus server context)
  - `venus_os.control_locked`: bool (new lock state, see Feature 3)
- `proxy.py`: Track last Venus OS read timestamp in shared_ctx when `StalenessAwareSlaveContext.getValues()` is called. Add a `_last_venus_read_ts` attribute updated on each successful getValues call.
- `webapp.py`: Include venus_os section in snapshot broadcast (or add to DashboardCollector).
- `app.js`: New `updateVenusInfo(data.venus_os)` function to populate the widget.

**Backend changes:** SMALL. Track Venus OS last-read timestamp in StalenessAwareSlaveContext and pass through shared_ctx to DashboardCollector.

### Feature 3: Venus OS Lock Toggle

**What changes:**
- `control.py`: Add `venus_locked: bool` to ControlState. When locked=True, StalenessAwareSlaveContext._handle_control_write() rejects all Model 123 writes with a "locked" error.
- `webapp.py`: New POST `/api/venus-lock` endpoint to toggle the lock state.
- `index.html`: Apple-style toggle switch in the Venus OS info widget.
- `app.js`: Toggle click handler calls `/api/venus-lock`, update visual state from snapshot.
- `style.css`: Apple-style toggle component (`.ve-toggle`).

**Backend changes:** SMALL. Add boolean to ControlState, guard in _handle_control_write, one new endpoint.

### Feature 4: Peak Statistics

**What changes:**
- `dashboard.py`: Track in DashboardCollector:
  - `_peak_power_w`: max(ac_power_w) seen since startup
  - `_peak_power_ts`: timestamp of peak
  - `_operating_seconds`: cumulative seconds where status == "MPPT"
  - `_last_collect_ts`: for calculating operating time deltas
  - Efficiency: computed per-snapshot as `ac_power_w / dc_power_w * 100` (only when dc_power > 0)
- Emit in snapshot under `inverter.peak_power_w`, `inverter.peak_power_ts`, `inverter.operating_hours`, `inverter.efficiency_pct`.
- `index.html`: Stats card in dashboard (or extend daily energy widget with additional stats).
- `app.js`: New `updatePeakStats(inv)` function.

**Backend changes:** SMALL. All tracking is in-memory in DashboardCollector, same reset-on-restart pattern as daily energy.

### Feature 5: Smooth Animations

**What changes:**
- `style.css`:
  - Gauge arc: already has `transition: stroke-dashoffset 0.8s ease-out` -- verified working.
  - Phase card values: add CSS number transitions via `transition: opacity` on value flash.
  - Card entrance: add `@keyframes ve-card-enter` for initial page load.
  - Sparkline: add smooth path morphing via `transition` on polyline (limited -- SVG polyline transitions don't interpolate points natively; use JS-based lerp for smooth sparkline updates).
- `app.js`:
  - Gauge: add easing function for smooth needle animation (currently direct DOM update, which already triggers CSS transition -- may just need tuning).
  - Value counter: optional `animateValue(el, from, to)` for the main kW display.
  - Sparkline: lerp between old and new point arrays for smooth updates.

**Backend changes:** NONE. Purely frontend CSS/JS.

### Feature 6: Smart Toast Notifications

**What changes:**
- Current state: `showToast()` already exists in app.js (used for power control feedback). Toasts are created dynamically, auto-remove after 3s. CSS for `.ve-toast` with slide-in animation exists.
- Missing:
  - Toast stacking (multiple simultaneous toasts pile up at same position)
  - Event-driven toasts from snapshot changes (override detected, fault, temp warning, night mode)
  - Toast container for proper stacking
- `index.html`: Add `<div id="toast-container"></div>` for stacked toast positioning.
- `style.css`: Toast container with flexbox column-reverse for bottom-up stacking. Add slide-out animation.
- `app.js`:
  - Refactor `showToast()` to append to toast container instead of body.
  - Add event detection in `handleSnapshot()`:
    - Override: if `control.last_source` changes to `venus_os` -> toast "Venus OS took control"
    - Fault: if `inverter.status` changes to `FAULT` -> toast with error style
    - Temperature: if `temperature_sink_c > 75` (or configurable threshold) -> toast warning
    - Night mode: if `connection.state` changes to `night_mode` -> toast info
  - Track previous snapshot values to detect changes (partial: `lastControlState` already exists for power control).

**Backend changes:** NONE. All detection is frontend-side by comparing consecutive snapshots.

## Anti-Patterns to Avoid

### Anti-Pattern 1: New WebSocket Message Types for Each Feature
**What:** Adding new WS message types like `type: "venus_info"`, `type: "peak_stats"`.
**Why bad:** Fragments the data flow. The snapshot already goes out every poll cycle (1s). Adding more message types means more handlers, more race conditions, more complexity.
**Instead:** Extend the existing snapshot dict with new sections. One message, one handler, one truth.

### Anti-Pattern 2: Separate REST Endpoints for Dashboard Data
**What:** Adding `/api/venus-info`, `/api/peak-stats` etc. and polling them.
**Why bad:** The WebSocket already pushes all data. Polling REST endpoints adds latency and complexity.
**Instead:** All live data goes through the snapshot via WebSocket. REST endpoints only for actions (power-limit, venus-lock, config).

### Anti-Pattern 3: Separate Animation Library
**What:** Adding a JS animation library (GSAP, anime.js) for smooth transitions.
**Why bad:** Violates zero-dependency constraint. CSS transitions handle 90% of the cases.
**Instead:** CSS `transition` for most animations. Small inline JS `requestAnimationFrame` loop for the gauge counter animation and sparkline lerp.

### Anti-Pattern 4: Breaking the Single-File Pattern
**What:** Splitting app.js into multiple JS files (toast.js, animations.js, etc.).
**Why bad:** No build tooling means manual script ordering in HTML. The current 3-file pattern (HTML+CSS+JS) works with importlib.resources serving.
**Instead:** Use clear section comments (already the pattern in app.js). Keep everything in one JS file with well-separated IIFE blocks.

## Patterns to Follow

### Pattern 1: Extend Snapshot, Not Add Messages
**What:** All new data (peak stats, Venus OS info) added as new keys in the existing snapshot dict.
**When:** Any time you need to show live data in the dashboard.
**Example:**
```python
# In DashboardCollector.collect():
snapshot = {
    "ts": time.time(),
    "inverter": {**inverter, "peak_power_w": self._peak_power_w, ...},
    "control": control,
    "connection": connection,
    "venus_os": {                          # NEW section
        "last_read_ts": shared_ctx.get("venus_last_read_ts"),
        "connected": ...,
        "control_locked": control_state.venus_locked if control_state else False,
    },
    "override_log": ...,
}
```

### Pattern 2: Detect Changes by Comparing Previous Snapshot
**What:** Track `previousSnapshot` in app.js, compare fields to trigger toasts.
**When:** Event-driven notifications from continuous data stream.
**Example:**
```javascript
let previousSnapshot = null;

function handleSnapshot(data) {
    if (previousSnapshot) {
        detectEvents(previousSnapshot, data);
    }
    // ... existing update logic ...
    previousSnapshot = data;
}

function detectEvents(prev, curr) {
    // Override detection
    if (prev.control.last_source !== 'venus_os' && curr.control.last_source === 'venus_os') {
        showToast('Venus OS took control', 'error');
    }
    // Fault detection
    if (prev.inverter.status !== 'FAULT' && curr.inverter.status === 'FAULT') {
        showToast('Inverter FAULT detected!', 'error');
    }
}
```

### Pattern 3: CSS-First Animations
**What:** Use CSS transitions and @keyframes for all visual transitions.
**When:** Any animation that involves a simple property change.
**Example:**
```css
/* Gauge fill already uses this pattern */
#gauge-fill {
    transition: stroke-dashoffset 0.8s ease-out, stroke 0.5s ease;
}

/* Extend to value updates */
.ve-live-value {
    transition: color 0.3s ease, opacity 0.15s ease;
}

/* Card entrance */
.ve-card {
    animation: ve-card-enter 0.3s ease-out;
}
@keyframes ve-card-enter {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
```

### Pattern 4: Compact Inline Control
**What:** Power control as a collapsible card within the dashboard, not a separate page.
**When:** Moving power control inline.
**Structure:**
```html
<!-- In page-dashboard, after sparkline, before bottom grid -->
<div class="ve-card ve-ctrl-card">
    <h2 class="ve-card-title">
        Power Control
        <span class="ve-badge ve-badge--test">Manual</span>
    </h2>
    <!-- Compact: override banner, status dot+label, slider, buttons in tighter layout -->
    <!-- Override log as collapsible section -->
</div>
```

## Suggested Build Order

Dependencies drive the order. Each step is independently testable.

```
Step 1: Peak Stats (backend-only, no HTML changes needed yet)
  dashboard.py: add _peak_power_w, _operating_seconds, efficiency tracking
  Tests: unit test DashboardCollector with mock data
  WHY FIRST: Pure backend addition, no restructuring, validates data flow extension pattern

Step 2: Unified Dashboard Layout (frontend-only restructuring)
  index.html: move power control HTML into page-dashboard, remove page-power
  index.html: remove Power Control nav-item from sidebar
  app.js: remove page-power references from navigation (nav-item click handlers still work)
  style.css: add compact power control card styles
  WHY SECOND: Biggest structural change. Do it early while code is stable.

Step 3: Venus OS Info Widget (small backend + frontend)
  proxy.py: track Venus OS last-read in StalenessAwareSlaveContext
  control.py: add venus_locked boolean
  dashboard.py: add venus_os section to snapshot
  webapp.py: add /api/venus-lock endpoint
  index.html: add Venus OS info card + lock toggle in dashboard
  app.js: updateVenusInfo() + lock toggle handler
  style.css: lock toggle component
  WHY THIRD: Depends on dashboard layout being finalized (Step 2).

Step 4: Toast System Enhancement (frontend-only)
  index.html: add toast container
  style.css: toast stacking, slide-out animation
  app.js: refactor showToast(), add event detection from snapshot diffs
  WHY FOURTH: Builds on top of all data being in snapshot (Steps 1+3).

Step 5: Smooth Animations (frontend polish, last)
  style.css: card entrance animations, value transition polish
  app.js: gauge counter animation, sparkline lerp
  WHY LAST: Polish layer. Everything must work first, then make it smooth.
```

## File Change Matrix

| File | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 |
|------|--------|--------|--------|--------|--------|
| `dashboard.py` | MODIFY (peak stats) | -- | MODIFY (venus_os section) | -- | -- |
| `proxy.py` | -- | -- | MODIFY (track venus read ts) | -- | -- |
| `control.py` | -- | -- | MODIFY (venus_locked) | -- | -- |
| `webapp.py` | -- | -- | MODIFY (venus-lock endpoint) | -- | -- |
| `index.html` | -- | RESTRUCTURE | MODIFY (venus widget) | MODIFY (toast container) | -- |
| `style.css` | -- | MODIFY (compact ctrl) | MODIFY (toggle) | MODIFY (toast stack) | MODIFY (animations) |
| `app.js` | -- | MODIFY (remove nav) | MODIFY (venus info) | MODIFY (toast refactor) | MODIFY (animations) |

## Scalability Considerations

Not applicable -- this is a single-user embedded dashboard on a LAN device. The WebSocket serves 1-3 concurrent browsers at most. The in-memory data resets on restart by design.

## Sources

- Direct code analysis of existing codebase (HIGH confidence)
- All architecture recommendations derived from actual file contents and data flow patterns
- No external sources needed -- this is integration architecture for an existing system
