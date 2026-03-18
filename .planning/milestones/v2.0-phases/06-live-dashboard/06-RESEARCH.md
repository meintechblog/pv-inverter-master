# Phase 6: Live Dashboard - Research

**Researched:** 2026-03-18
**Domain:** Real-time WebSocket dashboard with power gauge, 3-phase details, SVG sparklines
**Confidence:** HIGH

## Summary

Phase 6 transforms the placeholder dashboard page into a live energy monitoring interface. The backend infrastructure is already in place: `DashboardCollector` decodes registers every poll cycle, `TimeSeriesBuffer` stores 60 minutes of history, and the REST endpoint `/api/dashboard` already serves snapshot JSON. The remaining work is: (1) add a WebSocket endpoint to push snapshots to browsers, (2) hook the broadcast into the poll loop, (3) build frontend widgets -- power gauge, 3-phase cards, sparkline, and (4) replace polling with WebSocket event handlers in `app.js`.

All technology choices are settled: `aiohttp.web.WebSocketResponse` (zero deps), vanilla JavaScript, inline SVG for gauge and sparkline, Venus OS CSS palette. No new Python or JS dependencies are needed. The `shared_ctx` dict already passes the collector between proxy and webapp -- adding WebSocket broadcast is a 3-4 line change to `proxy.py`.

**Primary recommendation:** Build backend WebSocket first (testable with wscat), then frontend widgets. Keep all rendering as inline SVG (no chart libraries). Use `weakref.WeakSet` for client tracking and `heartbeat=30.0` on WebSocketResponse for connection liveness.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- WebSocket (or SSE) push from server to all connected browsers
- Data pushed after each poll cycle (~1 second)
- No manual refresh needed -- widgets update automatically
- Live Power Gauge -- current total power vs 30kW capacity
- 3-Phase Detail -- L1/L2/L3 voltage, current, power
- Mini-Sparkline -- 60-min power history from TimeSeriesBuffer
- Health metrics (carried from v1.0 -- uptime, poll rate, cache)
- Connection status dots (carried from v1.0)
- Config editor and Register Viewer from v1.0 remain as sidebar tabs
- Must use Venus OS palette (#387DC5 blue, #141414 bg, #FAF9F5 text)
- Venus OS Widget-Style (abgerundete Panels, GX Touch Feel)
- Responsive (Desktop, Tablet, Mobile)

### Claude's Discretion
- Power Gauge type (arc gauge, big number, tacho, donut, bar)
- Widget grid layout (arrangement, sizing, spacing)
- Sparkline styling (line color, fill, Y-axis, hover tooltips)
- 3-Phase detail presentation (table, cards, inline)
- Animation/transition effects on value updates
- Mobile widget stacking order
- Color coding for power levels (green->yellow->red thresholds)

### Deferred Ideas (OUT OF SCOPE)
- None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Real-time updates via SSE or WebSocket (push statt polling) | WebSocket handler pattern with `aiohttp.web.WebSocketResponse`, `weakref.WeakSet` client tracking, broadcast from poll loop |
| INFRA-05 | Config + Register Viewer integriert ins neue Dashboard (Tabs/Sections) | Already ported as sidebar tabs in Phase 5; Phase 6 keeps them working alongside new dashboard widgets |
| DASH-02 | Live Power Gauge -- zentrale Anzeige aktuelle Leistung vs 30kW Nennleistung | SVG arc gauge using `stroke-dasharray`/`stroke-dashoffset` on an SVG circle/arc, powered by `ac_power_w` from snapshot |
| DASH-03 | 3-Phasen Detail -- L1/L2/L3 Strom, Spannung, Leistung einzeln | Snapshot already contains `ac_current_l1_a`, `ac_current_l2_a`, `ac_current_l3_a`, `ac_voltage_an_v`, `ac_voltage_bn_v`, `ac_voltage_cn_v`; render as 3 phase cards |
| DASH-06 | Mini-Sparklines -- Leistungsverlauf letzte 60 Minuten (SVG, in-memory Ring Buffer) | SVG polyline from TimeSeriesBuffer history, sent once on WebSocket connect then incrementally updated |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | >=3.10,<4.0 | WebSocket server + HTTP | Already in deps, native WebSocketResponse support |
| collections.deque | stdlib | TimeSeriesBuffer (already built) | Zero deps, O(1) append, maxlen eviction |
| weakref.WeakSet | stdlib | WebSocket client tracking | Auto-cleanup of dead connections |
| json | stdlib | WebSocket message serialization | Standard JSON protocol |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time | stdlib | Timestamps in snapshots | Every collect() call |
| asyncio | stdlib | Event loop, task management | Broadcast coroutine |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WebSocket | SSE (EventSource) | SSE simpler but unidirectional; WebSocket needed for Phase 7 power control commands |
| Inline SVG gauge | Chart.js / D3.js | External deps violate zero-dep constraint; overkill for single gauge |
| Vanilla JS sparkline | sparklines.js library | Extra dep for trivial SVG polyline generation (~15 lines of code) |

**Installation:**
```bash
# No new dependencies needed -- all stdlib + existing aiohttp
```

## Architecture Patterns

### Recommended Project Structure
```
src/venus_os_fronius_proxy/
  proxy.py           # MODIFY: add broadcast call after collect() (3 lines)
  webapp.py          # MODIFY: add /ws route, ws_handler, broadcast_to_clients
  dashboard.py       # EXISTS: DashboardCollector (no changes)
  timeseries.py      # EXISTS: TimeSeriesBuffer (no changes)
  __main__.py        # MODIFY: store webapp app ref in shared_ctx for broadcast
  static/
    index.html       # MODIFY: add dashboard widget containers
    style.css        # MODIFY: add gauge, sparkline, phase-card styles
    app.js           # MODIFY: add WebSocket connection, widget renderers
```

### Pattern 1: WebSocket Handler with WeakSet Client Tracking
**What:** Server maintains a `weakref.WeakSet` of active WebSocket connections. On connect, sends initial snapshot + history. On each poll cycle, broadcasts latest snapshot to all clients.
**When to use:** Any server-push scenario with multiple browser tabs.
**Example:**
```python
# Source: aiohttp docs + verified pattern from GitHub issues
import weakref
import json
from aiohttp import web

async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)
    request.app["ws_clients"].add(ws)

    # Send current state immediately
    collector = request.app["shared_ctx"].get("dashboard_collector")
    if collector and collector.last_snapshot:
        await ws.send_json({"type": "snapshot", "data": collector.last_snapshot})

    # Send 60-min history for sparkline initialization
    if collector:
        history = {}
        for key, buf in collector._buffers.items():
            samples = buf.get_all()
            # Downsample: every 10th sample = ~360 points for 60 min
            history[key] = [[s.timestamp, s.value] for s in samples[::10]]
        await ws.send_json({"type": "history", "data": history})

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Phase 7 will handle power control commands here
                pass
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        request.app["ws_clients"].discard(ws)

    return ws

async def broadcast_to_clients(app: web.Application, snapshot: dict) -> None:
    if not app.get("ws_clients"):
        return
    payload = json.dumps({"type": "snapshot", "data": snapshot})
    dead = []
    for ws in set(app["ws_clients"]):
        try:
            await ws.send_str(payload)
        except (ConnectionError, RuntimeError):
            dead.append(ws)
    for ws in dead:
        app["ws_clients"].discard(ws)
```

### Pattern 2: SVG Arc Gauge (Pure CSS + SVG)
**What:** A semicircular arc gauge using SVG `<circle>` with `stroke-dasharray` and `stroke-dashoffset` to show power fill percentage.
**When to use:** Hero power display widget.
**Example:**
```html
<!-- SVG arc gauge: semicircle from 180deg, fill proportional to power/capacity -->
<svg viewBox="0 0 200 120" class="ve-gauge-svg">
  <!-- Background arc -->
  <path d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none" stroke="var(--ve-border)" stroke-width="12" stroke-linecap="round"/>
  <!-- Value arc (stroke-dashoffset controlled by JS) -->
  <path id="gauge-fill" d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none" stroke="var(--ve-blue)" stroke-width="12" stroke-linecap="round"
        stroke-dasharray="251" stroke-dashoffset="251"/>
  <!-- Center text -->
  <text x="100" y="85" text-anchor="middle" fill="var(--ve-text)"
        font-size="28" font-weight="700" id="gauge-value">0</text>
  <text x="100" y="105" text-anchor="middle" fill="var(--ve-text-dim)"
        font-size="12">kW / 30 kW</text>
</svg>
```
```javascript
// Update gauge: power in watts, capacity 30000W
function updateGauge(powerW) {
  const pct = Math.min(powerW / 30000, 1.0);
  const arcLength = 251; // length of the semicircle path
  const offset = arcLength * (1 - pct);
  document.getElementById('gauge-fill').style.strokeDashoffset = offset;
  document.getElementById('gauge-value').textContent = (powerW / 1000).toFixed(1);

  // Color coding: green < 50%, yellow 50-80%, red > 80%
  const color = pct < 0.5 ? 'var(--ve-green)' : pct < 0.8 ? 'var(--ve-orange)' : 'var(--ve-red)';
  document.getElementById('gauge-fill').style.stroke = color;
}
```

### Pattern 3: SVG Sparkline (Polyline)
**What:** Render 60-min power history as an SVG polyline. Initialize from history message, then append each snapshot's value.
**When to use:** Mini trend visualization below gauge.
**Example:**
```javascript
// Source: adapted from rousek.name/articles/svg-sparklines-with-no-dependencies
function renderSparkline(svgEl, data, color) {
  if (data.length < 2) return;
  const W = svgEl.viewBox.baseVal.width || 300;
  const H = svgEl.viewBox.baseVal.height || 60;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const dx = W / (data.length - 1);

  const points = data.map((v, i) => {
    const x = i * dx;
    const y = H - ((v - min) / range) * (H * 0.9); // 10% padding top
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Line
  let polyline = svgEl.querySelector('.sparkline-line');
  if (!polyline) {
    polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    polyline.classList.add('sparkline-line');
    polyline.setAttribute('fill', 'none');
    polyline.setAttribute('stroke', color);
    polyline.setAttribute('stroke-width', '1.5');
    svgEl.appendChild(polyline);
  }
  polyline.setAttribute('points', points);

  // Fill area
  let fillPath = svgEl.querySelector('.sparkline-fill');
  if (!fillPath) {
    fillPath = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    fillPath.classList.add('sparkline-fill');
    fillPath.setAttribute('fill', color);
    fillPath.setAttribute('opacity', '0.15');
    svgEl.appendChild(fillPath);
  }
  const fillPoints = `0,${H} ${points} ${W},${H}`;
  fillPath.setAttribute('points', fillPoints);
}
```

### Pattern 4: WebSocket Auto-Reconnect (Client-Side)
**What:** Browser reconnects automatically when WebSocket drops, with exponential backoff.
**When to use:** Always -- connections will drop on network glitches.
**Example:**
```javascript
function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws`);
  let reconnectDelay = 1000;

  ws.onopen = () => {
    reconnectDelay = 1000; // reset on success
    updateConnectionIndicator('connected');
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'snapshot') handleSnapshot(msg.data);
    if (msg.type === 'history') handleHistory(msg.data);
  };

  ws.onclose = () => {
    updateConnectionIndicator('disconnected');
    setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      connectWebSocket();
    }, reconnectDelay);
  };

  ws.onerror = () => ws.close(); // trigger onclose -> reconnect
  return ws;
}
```

### Anti-Patterns to Avoid
- **Polling from frontend for "real-time":** Existing `setInterval(fetch, 2000)` creates N*rate HTTP requests. Replace with single WebSocket.
- **Sending full history every second:** Send history once on connect, then only current snapshot (~0.5KB) each second.
- **Building gauge with Canvas:** SVG is better for this use case -- scalable, stylable with CSS variables, simpler code.
- **Using external chart libraries:** Zero-dep constraint. Inline SVG polyline is ~20 lines of JS.
- **Forgetting WebSocket reconnect:** Network drops WILL happen. Must auto-reconnect with backoff.
- **Not handling stale connection in WeakSet:** Use `heartbeat=30.0` on `WebSocketResponse` so aiohttp auto-closes dead connections.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket server | Raw TCP | `aiohttp.web.WebSocketResponse` | Protocol framing, ping/pong, error handling built in |
| Connection liveness | Manual ping loop | `WebSocketResponse(heartbeat=30.0)` | aiohttp sends pings, closes dead connections automatically |
| Client tracking cleanup | Manual set + periodic sweep | `weakref.WeakSet` + discard on error | Automatic GC of dead references |
| History downsampling | Complex windowing | Slice with `samples[::10]` | 3600 samples / 10 = 360 points is plenty for sparkline |
| SVG arc math | Complex trigonometry | `stroke-dasharray` + `stroke-dashoffset` on known-length path | Browser handles rendering; just set offset proportional to value |

**Key insight:** This phase has zero complexity that warrants external dependencies. aiohttp WebSocket is battle-tested, SVG gauges/sparklines are trivial with dasharray, and vanilla JS handles DOM updates fine for 5 widgets updating once per second.

## Common Pitfalls

### Pitfall 1: WebSocket Memory Leak from Abandoned Connections
**What goes wrong:** Browser tab closes without clean WebSocket close. Connection stays in `ws_clients` set, `send_str()` silently fails or throws.
**Why it happens:** Network drops, browser crashes, mobile backgrounding.
**How to avoid:** Use `heartbeat=30.0` parameter on `WebSocketResponse`. aiohttp sends ping frames every 30s and closes the connection if no pong is received. Also wrap `send_str()` in try/except and discard dead clients.
**Warning signs:** Growing `len(app["ws_clients"])` over time, increasing broadcast latency.

### Pitfall 2: Blocking the Event Loop During Broadcast
**What goes wrong:** Broadcasting to many clients with `await ws.send_str()` in a loop blocks the poll loop if a client is slow.
**Why it happens:** TCP backpressure from a slow client delays all subsequent sends.
**How to avoid:** For this project (1-5 clients max), sequential await is fine. If needed later, use `asyncio.gather(*sends, return_exceptions=True)`.
**Warning signs:** Poll cycle duration exceeding 1 second.

### Pitfall 3: Sparkline Data Growing Unbounded in Browser
**What goes wrong:** Frontend appends every snapshot's power value to sparkline array without trimming.
**Why it happens:** Easy to forget `shift()` when array exceeds max length.
**How to avoid:** Cap the browser-side array: `if (data.length > 3600) data.shift()`. Or use a fixed-size ring buffer approach.
**Warning signs:** Browser tab memory growing steadily, sparkline SVG points string getting enormous.

### Pitfall 4: JSON Serialization on Every Broadcast
**What goes wrong:** `json.dumps(snapshot)` called once per client instead of once per broadcast.
**Why it happens:** Putting `json.dumps` inside the per-client loop.
**How to avoid:** Serialize once before the loop: `payload = json.dumps(...)`, then `ws.send_str(payload)` for each client.
**Warning signs:** CPU usage proportional to client count.

### Pitfall 5: Initial History Payload Too Large
**What goes wrong:** Sending all 3600 samples * 6 buffers = 21,600 data points on connect. Payload > 200KB.
**Why it happens:** Sending raw 1-second resolution for all metrics.
**How to avoid:** Downsample: send every 10th sample for sparkline. Only send `ac_power_w` history (the only metric shown as sparkline in Phase 6). Total: ~360 points, ~5KB.
**Warning signs:** Slow initial page load, large WebSocket frame.

### Pitfall 6: SVG Gauge Arc Length Calculation Wrong
**What goes wrong:** `stroke-dashoffset` does not match actual path length, gauge shows wrong fill level.
**Why it happens:** Arc length depends on radius and angle; estimating it wrong.
**How to avoid:** Use `path.getTotalLength()` in JS to get exact path length, or pre-calculate for a known SVG viewBox. For a semicircle with radius 80: length = pi * 80 = ~251.3.
**Warning signs:** Gauge shows 100% when value is 70%, or needle overshoots.

## Code Examples

### WebSocket Route Registration (webapp.py)
```python
# In create_webapp(), add after existing routes:
app["ws_clients"] = weakref.WeakSet()
app.router.add_get("/ws", ws_handler)
```

### Poll Loop Broadcast Hook (proxy.py)
```python
# After existing dashboard_collector.collect() call (~line 275):
if shared_ctx is not None and "webapp" in shared_ctx:
    webapp_app = shared_ctx["webapp"]
    await broadcast_to_clients(webapp_app, snapshot)
```

### Storing App Reference (\_\_main\_\_.py)
```python
# After create_webapp() returns runner:
shared_ctx["webapp"] = runner.app
```

### Dashboard Widget Container (index.html)
```html
<!-- Replace placeholder in #page-dashboard -->
<div class="ve-dashboard-grid">
  <div class="ve-card ve-gauge-card" id="power-gauge-card">
    <h2>Power Output</h2>
    <svg id="power-gauge" viewBox="0 0 200 120"><!-- gauge arcs --></svg>
  </div>
  <div class="ve-card ve-phase-card" id="phase-l1">
    <h3>L1</h3>
    <div class="phase-voltage" id="l1-voltage">-- V</div>
    <div class="phase-current" id="l1-current">-- A</div>
    <div class="phase-power" id="l1-power">-- W</div>
  </div>
  <!-- L2, L3 similar -->
  <div class="ve-card ve-sparkline-card">
    <h2>Power (60 min)</h2>
    <svg id="sparkline-power" viewBox="0 0 300 60" preserveAspectRatio="none"></svg>
  </div>
</div>
```

### Value Update Animation (CSS)
```css
/* Smooth number transitions */
.ve-live-value {
  transition: color 0.3s ease;
  font-family: var(--ve-mono);
  font-variant-numeric: tabular-nums;
}

.ve-value-changed {
  color: var(--ve-blue-light);
}

/* Gauge arc transition */
#gauge-fill {
  transition: stroke-dashoffset 0.8s ease-out, stroke 0.5s ease;
}
```

### Snapshot Field Mapping for Widgets
```javascript
// Fields available in snapshot.inverter (from DashboardCollector):
// Power gauge:    ac_power_w
// Phase L1:       ac_current_l1_a, ac_voltage_an_v (L1 = phase A = AN)
// Phase L2:       ac_current_l2_a, ac_voltage_bn_v (L2 = phase B = BN)
// Phase L3:       ac_current_l3_a, ac_voltage_cn_v (L3 = phase C = CN)
// Sparkline:      ac_power_w (from history, then incremental)
// Status:         status (string like "MPPT", "OFF", "FAULT")
// Energy:         energy_total_wh
// Temperature:    temperature_sink_c
// Frequency:      ac_frequency_hz

function handleSnapshot(data) {
  const inv = data.inverter;
  updateGauge(inv.ac_power_w || 0);
  updatePhaseCard('l1', inv.ac_voltage_an_v, inv.ac_current_l1_a);
  updatePhaseCard('l2', inv.ac_voltage_bn_v, inv.ac_current_l2_a);
  updatePhaseCard('l3', inv.ac_voltage_cn_v, inv.ac_current_l3_a);
  sparklineData.push(inv.ac_power_w || 0);
  if (sparklineData.length > 3600) sparklineData.shift();
  renderSparkline(document.getElementById('sparkline-power'), sparklineData, 'var(--ve-blue)');
  // Update health/status from data.connection
  updateHealthMetrics(data.connection);
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setInterval(fetch, 2000)` | WebSocket push from server | Phase 6 | Single connection, sub-second updates, less server load |
| Raw register integers in UI | DashboardCollector decoded values | Phase 5 | Physical units (W, A, V, Hz) ready for display |
| Single placeholder dashboard | Widget grid with gauge + sparkline | Phase 6 | Professional energy monitoring appearance |
| No history visualization | 60-min SVG sparkline from TimeSeriesBuffer | Phase 6 | Trend visibility at a glance |

**Deprecated/outdated:**
- `pollStatus()` / `pollHealth()` / `pollRegisters()` in app.js: These `setInterval`-based polling functions should be replaced by WebSocket event handlers for dashboard data. Config and register polling can remain as-is since those pages are only active when selected.

## Design Recommendations (Claude's Discretion)

### Power Gauge: SVG Arc (Semicircle)
**Rationale:** Arc gauges are the most recognizable power visualization. Semicircle (180 degrees) gives a clean, modern look that fits the Venus OS GX Touch aesthetic. Big number in center for immediate readability.

### Widget Grid Layout
```
Desktop (>1024px):
+-------------------+--------+--------+--------+
|   Power Gauge     |   L1   |   L2   |   L3   |
|   (hero, 2 cols)  |        |        |        |
+-------------------+--------+--------+--------+
|        Sparkline (60min, full width)          |
+-----------------------------------------------+
| Connection Status |  Service Health           |
+-------------------+---------------------------+

Tablet (768-1024px):
+-------------------+-------------------+
|   Power Gauge     |   L1  |  L2  | L3|
+-------------------+-------------------+
|        Sparkline (full width)         |
+---------------------------------------+
| Status  |  Health                     |
+---------+-----------------------------+

Mobile (<768px):
+-------------------+
|   Power Gauge     |
+-------------------+
| L1 | L2 | L3     |
+-------------------+
|   Sparkline       |
+-------------------+
| Status | Health   |
+-------------------+
```

### Color Coding
- Power < 50% capacity: `var(--ve-green)` (#72B84C)
- Power 50-80%: `var(--ve-orange)` (#F0962E)
- Power > 80%: `var(--ve-red)` (#F35C58)
- Sparkline line: `var(--ve-blue)` (#387DC5)
- Phase card text: `var(--ve-text)` with `var(--ve-text-dim)` labels

### 3-Phase Cards
Three equal-width cards side by side. Each card shows:
- Phase name (L1/L2/L3) as header
- Voltage (e.g., "230.1 V") -- large, prominent
- Current (e.g., "6.1 A") -- medium
- Calculated power (V * I, e.g., "1,404 W") -- medium

### Animations
- Gauge arc: CSS transition on `stroke-dashoffset` (0.8s ease-out)
- Numbers: Brief color flash on change (0.3s transition)
- Sparkline: No animation needed (redrawn each second, appears smooth)
- Use `font-variant-numeric: tabular-nums` so numbers don't jump around

## Open Questions

1. **Per-phase power calculation**
   - What we know: Snapshot contains per-phase voltage (AN/BN/CN) and per-phase current (L1/L2/L3) but not per-phase power directly
   - What's unclear: Whether to compute V*I client-side or add per-phase power to DashboardCollector
   - Recommendation: Compute client-side (trivial multiplication, keeps snapshot lean)

2. **History message: monotonic vs wall-clock timestamps**
   - What we know: TimeSeriesBuffer uses `time.monotonic()` for timestamps, but snapshot uses `time.time()` for `ts` field
   - What's unclear: Frontend needs wall-clock for sparkline X-axis labels
   - Recommendation: Convert monotonic to wall-clock in history message by computing offset: `wall_offset = time.time() - time.monotonic()`, then `[s.timestamp + wall_offset, s.value]`

3. **WebSocket URL path for future proxy compatibility**
   - What we know: Using `/ws` as the WebSocket endpoint
   - What's unclear: If a reverse proxy (nginx) will be in front later
   - Recommendation: Use `/ws` for now. Reverse proxy configuration is a deployment concern, not a code concern.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | WebSocket connects and receives snapshot | integration | `pytest tests/test_websocket.py::test_ws_connect_receives_snapshot -x` | Wave 0 |
| INFRA-01 | Broadcast sends to all connected clients | integration | `pytest tests/test_websocket.py::test_broadcast_to_multiple_clients -x` | Wave 0 |
| INFRA-01 | Dead client removed from ws_clients | unit | `pytest tests/test_websocket.py::test_dead_client_cleanup -x` | Wave 0 |
| INFRA-05 | Config page still accessible as tab | smoke | `pytest tests/test_webapp.py::test_config_get -x` | Exists |
| INFRA-05 | Register viewer still accessible as tab | smoke | `pytest tests/test_webapp.py::test_registers_side_by_side -x` | Exists |
| DASH-02 | Snapshot contains ac_power_w for gauge | unit | `pytest tests/test_dashboard.py::test_collect_snapshot_keys -x` | Exists |
| DASH-03 | Snapshot contains per-phase voltage/current | unit | `pytest tests/test_dashboard.py::test_collect_snapshot_keys -x` | Exists (verify L1/L2/L3 fields) |
| DASH-06 | History message contains sparkline data | integration | `pytest tests/test_websocket.py::test_ws_connect_receives_history -x` | Wave 0 |
| DASH-06 | Sparkline data downsampled to ~360 points | unit | `pytest tests/test_websocket.py::test_history_downsampled -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_websocket.py` -- covers INFRA-01, DASH-06 (WebSocket connect, broadcast, history)
- [ ] Verify existing `test_dashboard.py` covers L1/L2/L3 per-phase fields for DASH-03

## Sources

### Primary (HIGH confidence)
- Existing codebase: `webapp.py`, `dashboard.py`, `timeseries.py`, `proxy.py`, `__main__.py` -- direct code analysis
- [aiohttp Server Reference (v3.13.3)](https://docs.aiohttp.org/en/stable/web_reference.html) -- WebSocketResponse constructor, heartbeat parameter
- [aiohttp WebSocket multiple clients (Issue #2940)](https://github.com/aio-libs/aiohttp/issues/2940) -- WeakSet broadcast pattern
- `.planning/research/ARCHITECTURE.md` -- WebSocket design, snapshot format, data flow

### Secondary (MEDIUM confidence)
- [SVG Sparklines with no dependencies (rousek.name)](https://rousek.name/articles/svg-sparklines-with-no-dependencies) -- polyline generation pattern
- [Easy SVG sparklines (alexplescan.com)](https://alexplescan.com/posts/2023/07/08/easy-svg-sparklines/) -- normalize + scale algorithm
- [SVG arc gauge tutorial (hongkiat.com)](https://www.hongkiat.com/blog/svg-meter-gauge-tutorial/) -- stroke-dasharray gauge technique

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources or existing codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all patterns verified in existing codebase
- Architecture: HIGH -- WebSocket handler pattern well-documented in aiohttp, integration points already identified in proxy.py and __main__.py
- Pitfalls: HIGH -- common WebSocket pitfalls well-known, heartbeat parameter verified in aiohttp docs
- Frontend widgets: MEDIUM -- SVG gauge/sparkline patterns verified from multiple sources but specific sizing/layout will need iteration

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- no moving targets, all stdlib + existing deps)
