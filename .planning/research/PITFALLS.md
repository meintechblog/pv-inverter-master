# Domain Pitfalls

**Domain:** Dashboard Redesign & Polish for vanilla JS industrial monitoring proxy
**Researched:** 2026-03-18

## Critical Pitfalls

Mistakes that cause rewrites, performance degradation, or safety incidents.

### Pitfall 1: Animation Jank from Layout Thrashing on Every WebSocket Update

**What goes wrong:** The current `flashValue()` function adds/removes a CSS class every 300ms on value changes, and `renderSparkline()` rebuilds SVG point strings on every 1/s snapshot. Adding CSS transitions/animations to more elements (gauge arc, phase cards, stat counters) while simultaneously updating `textContent` causes the browser to interleave style recalculation, layout, and paint on every WebSocket frame. On a data-heavy dashboard with 15+ animated elements updating at 1Hz, this produces visible jank -- especially on the LXC-hosted dashboard viewed from lower-powered devices.

**Why it happens:** Each `textContent` change invalidates layout. Adding `classList.add/remove` for flash animations forces style recalculation. If CSS transitions are applied to properties that trigger layout (width, height, padding, top/left), every update causes a full layout-paint-composite cycle instead of just a composite.

**Consequences:** Dashboard feels sluggish. CPU spikes on every WebSocket update. Mobile/tablet users see stuttering gauge animations. The smooth experience intended by animations becomes worse than having none.

**Prevention:**
1. **Only animate composite-layer properties:** `transform` and `opacity` exclusively. The gauge arc `stroke-dashoffset` transition (already in CSS line 617) is fine because SVG stroke changes are paint-only. But never animate `width`, `height`, `margin`, `padding`, or `top/left`.
2. **Batch DOM reads before writes:** The current `handleSnapshot()` reads `data` then writes to 15+ DOM elements sequentially -- this is acceptable because there are no interleaved reads. Keep it that way. Never read `offsetWidth`/`getBoundingClientRect()` between writes (the existing `void row.offsetWidth` in `updateRegisterValues` line 611 is a deliberate reflow-trigger for re-animation, which is fine for the register page since it is not on the main dashboard).
3. **Use `requestAnimationFrame` for sparkline rendering:** Wrap `renderSparkline()` in `requestAnimationFrame` to coalesce updates and prevent painting incomplete frames. The sparkline rebuilds an SVG polyline points string of 3600 entries every second -- this should be deferred to the next paint frame.
4. **Cap animation concurrency:** If 10 values change simultaneously, 10 flash animations start. Use a single `ve-updating` class on the parent container with a CSS transition, rather than per-element flash classes.
5. **Test with CPU throttling:** Chrome DevTools > Performance > CPU 4x slowdown simulates the experience on lower-powered devices accessing the dashboard.

**Detection:** Open Chrome DevTools Performance tab. Record 10 seconds of dashboard updates. Look for purple (layout) bars exceeding 16ms per frame. If layout events appear on every WebSocket message, animation is causing layout thrashing.

### Pitfall 2: Venus OS Lock Toggle Without Sufficient Safety Guard

**What goes wrong:** An Apple-style toggle for "Lock Venus OS Control" could accidentally disable Venus OS's ability to control the inverter. If the user toggles it on (locking out Venus OS) and forgets, Venus OS can no longer enforce grid feed-in limits. In Germany/Austria, this violates Einspeiseregelung requirements. The system currently has a 60-second Venus OS priority window -- a toggle that overrides this permanently is a safety regression.

**Why it happens:** Toggle switches invite casual interaction. Unlike the existing power limit slider (which has a confirmation dialog AND auto-revert after 5 minutes), a toggle feels reversible and low-stakes. Users toggle it "to test" and forget.

**Consequences:** Venus OS cannot enforce grid compliance. The inverter runs at full power without feed-in regulation. Potential grid operator violations. In worst case, grid operator disconnects the installation.

**Prevention:**
1. **Never permanently lock out Venus OS.** The toggle should only suppress Venus OS control temporarily, with a mandatory auto-unlock timer (max 15 minutes, same principle as the existing 5-minute power limit revert).
2. **Require confirmation dialog** identical to the power limit confirmation: "Lock Venus OS control for 15 minutes? Venus OS will not be able to limit power during this time. Auto-unlock at HH:MM."
3. **Visual urgency indicator:** When locked, the toggle area should show a persistent red warning banner (similar to the existing `ctrl-override-banner`), not just a subtle toggle state change.
4. **Backend enforcement:** The lock state must live in `ControlState` (Python), not just in the frontend. The backend should refuse to honor the lock after the timeout expires, regardless of what the frontend shows. The `edpc_refresh_loop` already checks control state every 30 seconds -- add lock timeout checking there.
5. **WebSocket broadcast on lock state change:** All connected browser tabs must see the lock state change immediately. The current broadcast mechanism (`broadcast_to_clients`) already handles this pattern.

**Detection:** If the toggle has no timeout and no confirmation dialog, it is a safety issue. If the lock state is frontend-only (localStorage or JS variable), it is a safety issue.

### Pitfall 3: Merging Power Control Page Into Dashboard Breaks Existing Element IDs

**What goes wrong:** The Power Control page (lines 224-273 of index.html) uses element IDs like `ctrl-slider`, `ctrl-apply`, `ctrl-dot`, `ctrl-override-banner`. The Dashboard page uses IDs like `gauge-fill`, `power-gauge`, `daily-energy`. When merging Power Control inline into the Dashboard page, developers copy the HTML but accidentally create duplicate IDs (by keeping the original page for backwards compatibility), or they break the JavaScript event handlers (lines 682-737 of app.js) that use `document.getElementById()` and IIFE patterns that bind on page load.

**Why it happens:** The current architecture uses display:none pages with a single HTML file. Power Control JavaScript initializes with IIFEs that bind to elements on DOMContentLoaded. If those elements are moved to a different page div, or if the original page-power div is removed, the bindings break silently (getElementById returns null, and the existing null-checks like `if (!slider || !sliderValue) return` cause the entire feature to silently fail).

**Consequences:** Power control slider stops responding. Apply button does nothing. No error visible to user. Or worse: dual elements with same ID cause JavaScript to bind to the wrong one, sending power limit commands from a hidden element.

**Prevention:**
1. **Remove the original `page-power` div entirely** when merging into dashboard. Do not keep both. There must be exactly one instance of each control element ID.
2. **Move the event bindings out of IIFEs** and into a single `initPowerControl()` function called after the DOM is ready. This makes it testable and relocatable.
3. **Update the navigation:** Remove the "Power Control" nav item from the sidebar. The dashboard is now the single source of truth.
4. **Test the merge incrementally:** First move just the HTML, verify all JS bindings still work, then adjust layout/styling. Do not combine layout changes with functional changes.
5. **Keep `updatePowerControl(data)` unchanged** -- it already uses getElementById and does not depend on which page-div the elements are in.

**Detection:** After merging, open the dashboard and check: Does the slider move? Does Apply show a confirmation dialog? Does the Venus OS override banner appear when Venus OS writes? If any of these are broken, the merge was incomplete.

### Pitfall 4: Toast Notification Stacking and Fatigue

**What goes wrong:** The current `showToast()` (line 670-678) creates a fixed-position div at `top: 16px; right: 16px` with a 3-second auto-dismiss. When v2.1 adds toast notifications for override events, fault alerts, temperature warnings, AND night mode transitions, multiple toasts fire simultaneously (e.g., inverter goes to fault + Venus OS override happens at the same time). All toasts render at the exact same position, stacking on top of each other and becoming unreadable. Over time, users learn to ignore all toasts ("notification fatigue"), defeating the purpose.

**Why it happens:** The current toast implementation has no stacking logic, no duplicate suppression, and no rate limiting. Each toast is independently positioned at the same fixed coordinates.

**Consequences:** Overlapping toasts obscure each other. Users cannot read the important fault notification because a routine "night mode" toast covers it. Users start ignoring all toasts. Critical alerts go unnoticed.

**Prevention:**
1. **Toast container with vertical stacking:** Create a `#toast-container` fixed at top-right. Each toast is appended as a child and gets `margin-top` based on existing toasts. When a toast is dismissed, remaining toasts animate upward.
2. **Priority levels:** Critical toasts (fault, temperature warning) should be persistent (require manual dismiss) and visually distinct (red background, dismiss button). Info toasts (night mode, routine status) auto-dismiss in 3 seconds.
3. **Duplicate suppression:** If the same message text is already showing, do not create another toast. Increment a counter badge instead: "Venus OS override (x3)".
4. **Rate limiting:** Maximum 3 visible toasts at once. If a 4th arrives, dismiss the oldest info-level toast to make room. Never auto-dismiss critical toasts.
5. **Exit animation:** The current implementation has `ve-toast-in` animation but removes the element instantly with `toast.remove()`. Add a fade-out animation before removal so users see the toast leaving.
6. **Accessibility:** Add `role="alert"` and `aria-live="assertive"` to the toast container so screen readers announce notifications. The current implementation has no ARIA attributes.

**Detection:** Trigger 3+ events simultaneously (disconnect + reconnect + override). If toasts overlap or become unreadable, the stacking logic is missing.

## Moderate Pitfalls

### Pitfall 5: Venus OS Info Widget Polling Creates Additional Modbus Overhead

**What goes wrong:** The Venus OS Info widget needs data about Venus OS (connection status, IP, last contact time, firmware version). Developers might add a second Modbus polling loop that reads Venus OS-specific registers, doubling the Modbus traffic on the bus. The SolarEdge SE30K has limited Modbus throughput, and additional polling can cause timeouts on the primary data path.

**Prevention:**
1. **Do not add new Modbus polling.** Venus OS info should come from existing data: the `conn_mgr` state (already tracked), the Venus OS write detection (already in `ControlState.set_from_venus_os()`), and the proxy's own knowledge of Venus OS IP (from config or from the source address of incoming Modbus connections).
2. **Track Venus OS contact passively:** When Venus OS reads registers (which it does every ~3 seconds), record the source IP and timestamp in the proxy's Modbus server handler. This costs zero additional Modbus traffic.
3. **Expose via existing snapshot:** Add `venus_os` section to the `DashboardCollector.collect()` snapshot dict, alongside `inverter`, `control`, and `connection`. The WebSocket broadcast already pushes snapshots at 1Hz.

**Detection:** If a new `asyncio.create_task` appears with a Modbus read loop for Venus OS data, the overhead is being added. The information should be derived from passive observation of Venus OS's existing Modbus reads.

### Pitfall 6: Peak Statistics Accumulate Memory Indefinitely

**What goes wrong:** Peak statistics (peak kW today, operating hours, efficiency) require tracking values over time. A naive implementation stores every sample to compute peaks. With 1 sample/second, that is 86,400 samples per day. If the peak tracking does not reset daily, or if it stores full sample history instead of just the running max, memory grows continuously.

**Prevention:**
1. **Running max, not sample history:** For peak kW, store a single float `peak_w` that updates via `peak_w = max(peak_w, current_w)`. Do not store the history of all samples.
2. **Daily reset tied to inverter status:** Reset peak stats when inverter status transitions from SLEEPING/OFF to STARTING/MPPT (indicating a new day). The existing `DashboardCollector._energy_at_start` already uses this pattern for daily energy.
3. **Operating hours as monotonic counter:** Increment a counter by 1 each second when `status == MPPT`. Store as a single integer, not a list of timestamps.
4. **Efficiency as derived value:** `efficiency = daily_energy_wh / (peak_w * operating_hours_s / 3600)`. Compute on-demand from the other tracked values, do not store separately.

**Detection:** If peak tracking code contains a list/deque that appends every sample, memory will grow. It should contain only scalar values (peak, hours_count, etc.).

### Pitfall 7: CSS Grid Layout Regression When Adding Inline Power Control

**What goes wrong:** The dashboard currently uses `ve-dashboard-grid` (4-column: gauge + 3 phase cards) and `ve-dashboard-bottom` (3-column: inverter status + connection + health). Adding Power Control inline below the gauge means inserting a new section between row 1 (gauge+phases) and row 2 (sparkline). This breaks the visual rhythm and the responsive breakpoints. On mobile (single column), the power control section pushes the sparkline far down, making the core monitoring data invisible without scrolling.

**Prevention:**
1. **Compact power control section:** Do not replicate the full power control page. Show only: status dot + current limit % + slider + apply button, in a single horizontal row. The override log and detailed readout can remain in an expandable/collapsible section.
2. **Place it inside the gauge card, below the daily energy widget.** This keeps it visually grouped with power output (logical association) and does not disrupt the grid layout.
3. **Test all three breakpoints:** Desktop (1024+), tablet (768-1024), mobile (<768). The current responsive CSS is well-structured -- maintain the same grid-template-columns patterns.
4. **Do not add a new grid row.** Keep the existing 3-row structure (gauge+phases, sparkline, status cards). Power control becomes a sub-section of the gauge card.

**Detection:** After adding power control, check mobile view. If the sparkline and status cards are not visible without scrolling past the fold, the layout is too tall.

### Pitfall 8: Smooth Gauge Animation Conflicts with 1/s Data Updates

**What goes wrong:** The gauge arc has `transition: stroke-dashoffset 0.8s ease-out` (style.css line 617). With 1-second WebSocket updates, the 0.8s transition barely completes before the next value arrives. If the new value arrives mid-transition, the browser must interrupt and start a new transition from the current interpolated position. This causes the gauge to never fully settle, creating a "always chasing" visual effect that looks jerky rather than smooth.

**Prevention:**
1. **Reduce transition duration to 0.5s** to ensure it completes well before the next 1s update arrives, leaving a 0.5s settled period.
2. **Use CSS `transition-timing-function: ease-out`** (already present) -- this front-loads the visual change so the gauge appears to reach its target quickly even if a new value arrives.
3. **Skip transition for small changes:** If the power change is less than 50W (noise), do not update the gauge at all. Add a `deadband` in `updateGauge()`: `if (Math.abs(newPower - lastPower) < 50) return;`. This prevents the gauge from jittering on measurement noise.
4. **Never use `transition: all`** -- this would animate background-color, opacity, and any other properties that change on the gauge card, causing unexpected visual artifacts.

**Detection:** Watch the gauge for 30 seconds with live data. If the arc never stops moving (even when power is stable at, say, 10.0 kW), the transition duration is too long or the deadband is missing.

## Minor Pitfalls

### Pitfall 9: IIFE Event Bindings Silently Fail When DOM Structure Changes

**What goes wrong:** The power control JavaScript uses three IIFEs (lines 682-697, 723-737, 741-772) that bind event handlers on script load. If the DOM structure is changed (e.g., the slider is wrapped in a new container div, or it is moved to a different page section), `document.getElementById('ctrl-slider')` might return null during the IIFE execution (if the script runs before that DOM element exists). The `if (!slider || !sliderValue) return` guard silently exits without any error logging.

**Prevention:** Add `console.warn('Power control elements not found, skipping initialization')` to the early-return guards. During development, this surfaces broken bindings immediately instead of requiring manual testing of every feature.

### Pitfall 10: WebSocket Reconnect Sends Stale Snapshot on Reconnect

**What goes wrong:** When the WebSocket reconnects (after a temporary disconnect), the server sends the latest cached snapshot. If the dashboard also has local state (e.g., a toast showing "disconnected"), the reconnect snapshot triggers `handleSnapshot()` which updates all UI elements. But if the user had been dragging the power limit slider during the disconnect (`ctrlSliderDragging === true`), the slider position is not updated on reconnect (line 830), which is correct. However, the local `sparklineData` array keeps its pre-disconnect data and continues appending post-reconnect data, potentially creating a time gap in the sparkline that appears as a flat line.

**Prevention:** On WebSocket reconnect (`ws.onopen`), clear `sparklineData` and wait for the server's `history` message to repopulate it. The server already sends downsampled history on connect (webapp.py lines 402-415).

### Pitfall 11: Toast z-index Conflicts with Modal Dialog

**What goes wrong:** The toast has `z-index: 2000` and the modal overlay has `z-index: 1000`. This means a toast appearing during a confirmation dialog will render above the modal. If the toast is an error toast ("Venus OS has control"), it partially obscures the modal content, confusing the user who is trying to confirm a power limit change.

**Prevention:** Suppress toast creation while a modal dialog is visible. Add a simple check: `if (document.querySelector('.ve-modal-overlay')) return;` at the top of `showToast()`. Alternatively, queue toasts and show them after the modal is dismissed.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Layout Merge (Power Control into Dashboard) | Pitfall 3: Duplicate IDs, broken event bindings | Remove original page-power, single source of truth |
| Layout Merge (Power Control into Dashboard) | Pitfall 7: Grid layout regression on mobile | Place control inside gauge card, test all breakpoints |
| CSS Animations | Pitfall 1: Layout thrashing at 1Hz updates | Only animate transform/opacity, rAF for sparkline |
| CSS Animations | Pitfall 8: Gauge transition never settles | Reduce to 0.5s, add power deadband |
| Toast Notifications | Pitfall 4: Stacking, fatigue, accessibility | Container with stacking, priority levels, ARIA |
| Toast Notifications | Pitfall 11: z-index conflict with modal | Suppress toasts during modal or queue them |
| Venus OS Info Widget | Pitfall 5: Extra Modbus polling overhead | Passive tracking from existing connections |
| Venus OS Lock Toggle | Pitfall 2: Safety regression without timeout | Mandatory auto-unlock timer, confirmation dialog |
| Peak Statistics | Pitfall 6: Memory growth from sample history | Running max scalars, daily reset on status transition |
| General JS Architecture | Pitfall 9: Silent IIFE binding failures | Add console.warn to early-return guards |
| WebSocket Reconnect | Pitfall 10: Sparkline time gap | Clear sparklineData on reconnect, rely on server history |

## Sources

- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/static/app.js` (945 lines)
- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/static/style.css` (998 lines)
- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/static/index.html` (280 lines)
- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/webapp.py` (broadcast, WebSocket, power limit handler)
- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/dashboard.py` (DashboardCollector, snapshot structure)
- Direct codebase analysis of `/Users/hulki/codex/venus os fronius proxy/src/venus_os_fronius_proxy/control.py` (ControlState, OverrideLog, EDPC refresh)
- CSS rendering pipeline knowledge: composite-only properties avoid layout thrashing (HIGH confidence, well-established browser behavior)
- Einspeiseregelung safety requirements for German/Austrian grid compliance (HIGH confidence, regulatory requirement referenced in PROJECT.md)
