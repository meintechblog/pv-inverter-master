# Feature Landscape

**Domain:** Industrial solar inverter monitoring dashboard (v2.1 redesign & polish)
**Researched:** 2026-03-18
**Confidence:** HIGH (existing codebase thoroughly analyzed, patterns well-established in monitoring UX)

## Table Stakes

Features users expect from a polished v2.1 monitoring dashboard. Missing = product feels half-finished after the v2.0 foundation.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **Unified Dashboard (inline Power Control)** | Users already navigate between Dashboard and Power Control pages; merging eliminates context-switching. Every serious monitoring tool (SolarEdge app, Victron VRM, Grafana) puts controls near the data they affect. | Medium | Existing Power Control page HTML/JS, dashboard grid layout, `updatePowerControl()` in app.js | Must be compact -- slider + enable/disable + status in a collapsible card section below the gauge. Keep the separate Power Control nav item as an anchor/scroll-to, or remove it entirely. Override banner and revert countdown must work inline. |
| **Connection/System Info Widget** | v2.0 already has a Connection card and Service Health card in dashboard-bottom grid. Consolidating SolarEdge + Venus OS + WebSocket status into one coherent "System" widget is expected polish. | Low | Existing `#status-panel`, `#health-panel` HTML, `updateConnectionStatus()`, `pollHealth()` | Merge connection dots + uptime + poll rate + cache into a single "System Status" card. Venus OS IP and last-contact timestamp are new data points the backend must expose. |
| **Toast Notification Stacking** | v2.0 already has a `showToast()` function but toasts overlap (no stacking), no max-count, no pause-on-hover. Users expect non-overlapping stacked toasts in any notification-enabled UI. | Low | Existing `.ve-toast` CSS, `showToast()` function in app.js | Replace current single-toast implementation with a toast container (fixed top-right), vertical stacking with gap, max 3 visible, FIFO dismissal, slide-in/slide-out animations. Keep it vanilla JS -- no library needed. |
| **Smooth Gauge Animation** | v2.0 gauge already has `transition: stroke-dashoffset 0.8s ease-out` on `#gauge-fill`. But no entrance animation, no pulsing on high power, no color transition smoothing. Users expect fluid gauge motion in 2026. | Low | Existing SVG gauge, `updateGauge()` function, CSS transition on `#gauge-fill` | Add: initial draw-in animation on page load, smoother color transitions (CSS transition on stroke), subtle pulse glow at >80% capacity. All CSS -- no JS animation library. |

## Differentiators

Features that elevate the dashboard from "functional" to "polished industrial tool." Not strictly expected, but create delight and trust.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| **Venus OS Lock Toggle (Apple-style)** | Unique to this proxy: ability to lock/unlock Venus OS control from the webapp. The iOS-style toggle communicates "this is a serious on/off decision" better than a checkbox. No competing product has this because this proxy concept is unique. | Medium | Backend: new API endpoint or WS command to toggle Venus OS lock state. Frontend: pure CSS toggle with hidden checkbox + styled label. Must integrate with existing override detection logic (`isVenusOverride` in `updatePowerControl()`). | Pure CSS implementation: hidden `<input type="checkbox">` + `<label>` with `::after` pseudo-element for the thumb. Track color: `--ve-green` (unlocked) / `--ve-red` (locked). Smooth 0.3s transition. Must preserve keyboard accessibility (opacity:0, not display:none). Backend needs a lock/unlock state persisted in memory with WS broadcast. |
| **Peak Statistics (Today's Peak kW, Operating Hours, Efficiency)** | Solar monitoring apps universally show daily peak power. SolarEdge monitoring shows peak power, weighted efficiency, lifetime stats. This data exists in-memory already (sparkline buffer has all power readings). Displaying it proves the dashboard is a real monitoring tool, not just a live readout. | Low-Medium | Backend: new fields in DashboardCollector snapshot (`peak_power_w`, `operating_hours`, `efficiency_pct`). `peak_power_w` = max of all `ac_power_w` since midnight. `operating_hours` = count of seconds where power > 0 / 3600. Efficiency = `ac_power_w / dc_power_w * 100` (already have both values). Frontend: new stat row or card. | Display as a compact stats bar: `Peak: 14.2 kW | Hours: 8.3h | Eff: 97.2%`. Position below sparkline or in the gauge card. In-memory only (resets on restart, consistent with project's no-database constraint). |
| **CSS Micro-Interactions (value flash, card hover, transitions)** | Polished industrial UIs use subtle animations to convey liveness. v2.0 has `ve-value-flash` and `ve-changed` animations already. Extending to card hover effects, smooth page transitions, and status-dot pulsing creates a cohesive "alive" feeling. | Low | Existing CSS animation infrastructure (`@keyframes ve-flash`, `.ve-value-flash`, transition properties). | Add: card hover lift (`transform: translateY(-2px)` + subtle box-shadow), status dot pulse animation for active states (`@keyframes pulse`), smooth opacity transitions when panels appear. Use only `transform` and `opacity` for GPU-accelerated performance. Avoid animating `width`, `height`, `margin`, `padding`. |
| **Smart Notifications (contextual toasts)** | Beyond basic "action succeeded" toasts: notify on Venus OS override start/end, inverter fault, high temperature warning, night mode transition. v2.0 already handles `override_event` via WS. Extending to fault/temp/night creates situational awareness. | Medium | Backend: must emit new WS event types for fault, temperature threshold, night mode change. Frontend: extend `ws.onmessage` handler, add toast types with icons, add notification deduplication (don't spam same event). | Define thresholds: temp warning at >70C (cabinet) or >85C (heatsink). Fault = any non-MPPT/SLEEPING/OFF status that persists >2 polls. Night mode = status transitions to SLEEPING/OFF after sunset. Use distinct toast colors: orange for warnings, red for faults, blue for info (night mode). |
| **Venus OS Info Widget** | Dedicated sub-section showing Venus OS instance details: IP address, firmware version (if available), last Modbus contact timestamp, current control mode (manual/Venus OS/none). Differentiates from generic "Connection: Active" dot. | Low-Medium | Backend: track Venus OS client IP from Modbus server connections, last-contact timestamp. Some data may not be available (Venus OS version requires additional Modbus reads -- may be out of scope). Frontend: new section in unified System Status card. | Venus OS connects as a Modbus TCP client. The proxy's Modbus server can log the client IP and timestamp of last request. Display: `Venus OS: 192.168.3.146 | Last contact: 3s ago | Control: Active`. Version detection is stretch -- flag as optional. |

## Anti-Features

Features to explicitly NOT build. Tempting but wrong for this project.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Drag-and-drop widget customization** | Overkill for a single-purpose proxy dashboard with 1-2 users. Adds massive JS complexity (drag library, layout persistence, responsive recalculation). | Fixed layout designed for the specific data this proxy provides. The grid is already responsive via CSS Grid media queries. |
| **Historical data persistence / charting** | Explicitly out of scope (PROJECT.md). Venus OS and SolarEdge portal handle long-term data. Adding SQLite/InfluxDB contradicts the "60-min in-memory" design decision. | Keep the 60-min sparkline ring buffer. Peak stats reset on restart. Link to Venus OS VRM for history. |
| **Sound alerts / browser notifications** | Intrusive for an always-on LAN dashboard. Browser notification permission prompts are hostile UX. Sound in an industrial setting is wrong. | Visual-only toast notifications with color severity coding. |
| **Multi-inverter support in the UI** | The proxy is 1:1 (one SolarEdge, one Fronius identity). UI multi-inverter adds routing complexity for zero benefit. | Single-inverter dashboard. Plugin architecture handles backend flexibility if needed later. |
| **Dark/light theme toggle** | Venus OS IS dark theme. The entire UI identity is built on the `#141414` / `#11263B` / `#387DC5` palette. A light theme undermines the brand promise of "looks like Venus OS." | Keep dark-only. It's a feature, not a limitation. |
| **Animated SVG energy flow diagram** | PROJECT.md explicitly lists "Vollstaendiger Energy Flow Diagram" as out of scope. Proxy only has PV data, not grid/battery/load. A partial flow diagram is worse than none. | The gauge + phase cards + sparkline already convey power flow direction (PV production only). |
| **Complex notification preferences / settings** | One or two users on a LAN. A settings page for notification types, durations, and sounds is over-engineering. | Hardcoded sensible defaults: 3s auto-dismiss, max 3 visible, fixed thresholds for warnings. |

## Feature Dependencies

```
Unified Dashboard ─── requires ──> Existing Power Control JS/HTML (refactor, not rewrite)
                  └── requires ──> Toast stacking (inline control feedback needs reliable toasts)

Venus OS Lock Toggle ── requires ──> Backend lock/unlock API endpoint
                    └── requires ──> Venus OS Info Widget (toggle lives in this widget)

Peak Statistics ── requires ──> Backend DashboardCollector changes (new snapshot fields)
               └── requires ──> Sparkline data (already exists for peak calculation)

Smart Notifications ── requires ──> Toast stacking (must handle multiple simultaneous events)
                   └── requires ──> Backend WS event types for fault/temp/night

CSS Micro-Interactions ── independent (pure CSS, no backend changes)

Toast Stacking ── independent (refactor existing showToast(), no backend changes)
```

## MVP Recommendation

**Phase 1 -- Layout unification (do first, enables everything else):**
1. Toast notification stacking (refactor existing `showToast()` -- foundation for all feedback)
2. Unified Dashboard with inline Power Control (biggest UX win, eliminates page navigation)
3. CSS micro-interactions (low effort, immediate polish)

**Phase 2 -- Data enrichment (backend + frontend):**
4. Peak statistics display (backend: new snapshot fields, frontend: stat bar)
5. Venus OS Info Widget with Lock Toggle (backend: lock API + client tracking, frontend: toggle + info display)

**Phase 3 -- Situational awareness:**
6. Smart notifications for faults, temperature, night mode (backend: new WS events, frontend: toast types)

**Rationale:** Phase 1 is pure frontend refactoring with zero backend changes. Phase 2 requires backend DashboardCollector and API changes. Phase 3 requires backend event detection logic. This ordering minimizes risk -- if Phase 1 ships alone, the dashboard is already significantly better.

**Defer:** Venus OS firmware version detection (requires reverse-engineering Modbus register reads from Venus OS, uncertain feasibility).

## Sources

- Existing codebase analysis: `index.html`, `style.css`, `app.js` (v2.0 shipped code)
- [UXPin - Dashboard Design Principles 2025](https://www.uxpin.com/studio/blog/dashboard-design-principles/) -- unified layout, visual hierarchy
- [Smashing Magazine - UX Strategies for Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/) -- inline controls, real-time feedback patterns
- [Pure CSS iOS Toggle Switch](https://codepen.io/designcouch/pen/BaJOJg) -- checkbox hack pattern for Apple-style toggle
- [CSS Toggle Switch Best Practices](https://nikitahl.com/toggle-switch-button-css) -- accessibility (opacity:0 vs display:none)
- [Pixel Free Studio - Micro-Interaction Best Practices](https://blog.pixelfreestudio.com/best-practices-for-animating-micro-interactions-with-css/) -- GPU-accelerated properties, performance
- [SolarEdge Monitoring Platform](https://www.solaredge.com/en/products/software-tools/monitoring-platform) -- peak power, efficiency display patterns
- [SolarAssistant](https://solar-assistant.io/) -- Raspberry Pi solar monitoring reference design
- PROJECT.md -- out-of-scope constraints, design decisions
