# Phase 36: Auto-Throttle UI & Live Tuning - Research

**Researched:** 2026-03-25
**Domain:** Vanilla JS frontend (Venus OS dark theme), aiohttp REST API, WebSocket live updates
**Confidence:** HIGH

## Summary

Phase 36 is a pure frontend phase with minimal backend enrichment. The backend already exposes all the required data: `auto_throttle` boolean in config/snapshot/broadcast, `throttle_score` and `throttle_mode` per device in the device list API, and `measured_response_time_s` from the distributor's convergence tracking (all implemented in Phase 35). The contribution data from `_build_virtual_contributions()` already includes `device_id`, `power_w`, `throttle_order`, `throttle_enabled`, and `current_limit_pct`.

The frontend work consists of: (1) adding an Auto-Throttle toggle to the virtual Fronius dashboard page, (2) enriching the contributions payload with per-device throttle state (score, mode, cooldown status, relay state), (3) replacing the basic "Throttle Overview" table with a richer visualization showing throttle state per device, and (4) adding preset buttons that configure algorithm parameters via the existing config save API.

The only backend change needed is enriching `_build_virtual_contributions()` to include `throttle_score`, `throttle_mode`, `measured_response_time_s`, and device state (cooldown/active/disabled) in each contribution dict. A new endpoint or config fields may be needed for preset parameters.

**Primary recommendation:** Enrich the contributions payload in `_build_virtual_contributions()` with throttle metadata, then build all UI components in `app.js` and `style.css` following existing Venus OS design patterns (ve-toggle for the toggle, ve-card for cards, ve-throttle-table for the enhanced table).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THRT-10 | Virtual Fronius dashboard has Auto-Throttle toggle and shows live scores | `auto_throttle` already in virtual snapshot API + WS broadcast; toggle uses existing `ve-toggle` pattern; scores from enriched contributions |
| THRT-11 | Each device connection card shows throttle_score, mode, and measured response time | Device snapshot API already returns `throttle_score`, `throttle_mode`, `measured_response_time_s`; add display to inverter dashboard or connection info section |
| THRT-12 | Presets (Aggressive/Balanced/Conservative) adjust algorithm parameters | New config fields for convergence speed + hysteresis timers; preset buttons POST to `/api/config`; backend applies preset values |
</phase_requirements>

## Architecture Patterns

### Current Virtual PV Dashboard Structure

```
buildVirtualPVPage(container, data)
  -> Gauge card (total power, SVG arc, power limit dropdowns)
  -> Contribution bar card (stacked bar + legend)
  -> Throttle Overview card (basic table: Name | TO# | Throttle | Limit)
```

### Recommended Changes

```
buildVirtualPVPage(container, data)
  -> Gauge card (unchanged)
  -> Auto-Throttle control card (NEW)
     -> Toggle switch (on/off)
     -> Preset buttons (Aggressive | Balanced | Conservative)
     -> Active preset indicator
  -> Contribution bar card (ENHANCED)
     -> Segments colored by throttle state (active=green, throttled=orange, disabled=grey, cooldown=blue)
     -> Legend shows throttle state label per device
  -> Throttle Overview card (ENHANCED)
     -> Columns: Name | Score | Mode | Response Time | Limit | State
     -> Live-updated via WS virtual_snapshot
```

### Backend Enrichment: _build_virtual_contributions()

The contribution dict per device currently contains:
```python
{
    "device_id": inv.id,
    "name": display_name,
    "power_w": power_w,
    "throttle_order": inv.throttle_order,
    "throttle_enabled": inv.throttle_enabled,
    "current_limit_pct": device_limits.get(inv.id, 100.0),
}
```

Must add:
```python
{
    # ... existing fields ...
    "throttle_score": compute_throttle_score(caps),  # float 0-10
    "throttle_mode": caps.mode,                      # "proportional" | "binary" | "none"
    "measured_response_time_s": dist_ds.measured_response_time_s,  # float | None
    "throttle_state": "active" | "throttled" | "disabled" | "cooldown" | "startup",
    "relay_on": dist_ds.relay_on,  # bool (binary devices)
}
```

The `throttle_state` is a derived field computed from distributor state:
- `"disabled"` -- `throttle_enabled=False`
- `"cooldown"` -- binary device in cooldown period
- `"startup"` -- binary device in startup grace
- `"throttled"` -- `current_limit_pct < 100` or relay is off
- `"active"` -- running at full power

### Pattern 1: Auto-Throttle Toggle

**What:** A `ve-toggle` switch in the virtual dashboard that POSTs `auto_throttle: true/false` to `/api/config`.
**Reuses:** The existing config save API already handles `auto_throttle` in the request body (webapp.py line 404-406). The WS broadcast already includes `auto_throttle` in `virtual_snapshot` payloads (line 772).

```javascript
// Toggle HTML (follows ve-toggle-label pattern from config forms)
var toggleHtml =
    '<label class="ve-toggle-label">' +
    '  <input type="checkbox" class="ve-auto-throttle-toggle" ' + (data.auto_throttle ? 'checked' : '') + '>' +
    '  <span class="ve-switch"><span class="ve-switch-knob"></span></span>' +
    '  <span>Auto-Throttle</span>' +
    '</label>';

// Event handler: POST to config API
toggle.addEventListener('change', function() {
    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_throttle: toggle.checked })
    }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.success) showToast('Auto-Throttle ' + (toggle.checked ? 'enabled' : 'disabled'), 'success');
    });
});
```

**Live sync:** When WS `virtual_snapshot` arrives with `data.auto_throttle`, update toggle state without firing change event.

### Pattern 2: Preset Buttons (Aggressive/Balanced/Conservative)

**What:** Three button presets that adjust auto-throttle algorithm parameters.
**New config fields needed on Config:**

```python
# In config.py on Config dataclass:
auto_throttle_preset: str = "balanced"  # "aggressive" | "balanced" | "conservative"
```

**Preset definitions (constants, not config):**

| Parameter | Aggressive | Balanced | Conservative |
|-----------|-----------|----------|--------------|
| `convergence_tolerance_pct` | 10.0 | 5.0 | 3.0 |
| `convergence_max_samples` | 5 | 10 | 20 |
| `target_change_tolerance_pct` | 5.0 | 2.0 | 1.0 |
| `binary_off_threshold_w` | 100 | 50 | 25 |

These map to the existing constants in `distributor.py` (lines 24-27). Switching from constants to config-driven values lets presets change runtime behavior.

**UI pattern:** Three `ve-btn` buttons in a row, active one highlighted with `ve-btn--primary`.

```javascript
var presets = ['aggressive', 'balanced', 'conservative'];
presets.forEach(function(name) {
    var btn = document.createElement('button');
    btn.className = 've-btn ve-btn--sm' + (data.auto_throttle_preset === name ? ' ve-btn--primary' : '');
    btn.textContent = name.charAt(0).toUpperCase() + name.slice(1);
    btn.addEventListener('click', function() {
        fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_throttle_preset: name })
        }).then(function(r) { return r.json(); }).then(function(d) {
            if (d.success) showToast('Preset: ' + name, 'success');
        });
    });
});
```

### Pattern 3: Throttle State Contribution Bar

**What:** Color segments in the contribution bar by throttle state instead of cycling through `CONTRIBUTION_COLORS`.

```javascript
var THROTTLE_STATE_COLORS = {
    active: 'var(--ve-green)',
    throttled: 'var(--ve-orange)',
    disabled: 'var(--ve-text-dim)',
    cooldown: 'var(--ve-blue)',
    startup: 'var(--ve-blue-light)'
};

// In segment rendering:
var color = THROTTLE_STATE_COLORS[c.throttle_state] || 'var(--ve-text-dim)';
```

### Pattern 4: Enhanced Throttle Table

**What:** Replace the 4-column table with a richer 6-column table showing score, mode, and response time.

```javascript
var thead = '<thead><tr>' +
    '<th>Name</th>' +
    '<th>Score</th>' +
    '<th>Mode</th>' +
    '<th>Response</th>' +
    '<th>Limit</th>' +
    '<th>State</th>' +
    '</tr></thead>';

// Per row:
'<td>' + esc(ct.name) + '</td>' +
'<td class="ve-mono">' + (ct.throttle_score ? ct.throttle_score.toFixed(1) : '--') + '</td>' +
'<td>' + (ct.throttle_mode || '--') + '</td>' +
'<td class="ve-mono">' + (ct.measured_response_time_s != null ? ct.measured_response_time_s.toFixed(1) + 's' : '--') + '</td>' +
'<td class="ve-mono">' + (ct.current_limit_pct != null ? ct.current_limit_pct.toFixed(1) + '%' : '--') + '</td>' +
'<td><span class="ve-dot" style="background:' + (THROTTLE_STATE_COLORS[ct.throttle_state] || 'var(--ve-text-dim)') + '"></span></td>'
```

### Pattern 5: Per-Device Connection Card Enhancement (THRT-11)

The device snapshot API already returns `throttle_score`, `throttle_mode`, and `measured_response_time_s`. Display these in the inverter dashboard page (`buildInverterDashboard`), likely as a small info row below the gauge or in a dedicated "Throttle Info" card.

```javascript
// In buildInverterDashboard, after gauge card:
if (data.throttle_mode && data.throttle_mode !== 'none') {
    var throttleInfo = document.createElement('div');
    throttleInfo.className = 've-card';
    throttleInfo.innerHTML =
        '<h2 class="ve-card-title">Throttle Info</h2>' +
        '<div class="ve-throttle-info-grid">' +
        '  <span class="ve-text-dim">Score</span><span class="ve-mono">' + (data.throttle_score || 0).toFixed(1) + '</span>' +
        '  <span class="ve-text-dim">Mode</span><span>' + data.throttle_mode + '</span>' +
        '  <span class="ve-text-dim">Response</span><span class="ve-mono">' +
              (data.measured_response_time_s != null ? data.measured_response_time_s.toFixed(1) + 's' : 'Measuring...') +
        '</span>' +
        '</div>';
    container.appendChild(throttleInfo);
}
```

### Anti-Patterns to Avoid

- **Separate API endpoint for auto-throttle toggle:** The existing `/api/config` POST already handles `auto_throttle`. Do not create a new endpoint.
- **Rebuilding the entire virtual page on WS update:** The `updateVirtualPVPage()` function already does incremental DOM updates. Follow this pattern for new elements.
- **Hardcoded hex colors for throttle states:** Use `var(--ve-*)` tokens exclusively.
- **Complex preset logic in the frontend:** Presets are just named config bundles. The frontend sends a preset name; the backend maps it to parameter values. Keep the mapping in Python.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toggle switch | Custom checkbox + CSS | Existing `ve-toggle` / `ve-toggle-label` pattern | Already styled, tested, matches design system |
| Config save/load | New API endpoint | Existing `POST /api/config` with `auto_throttle` field | Already implemented in Phase 35 |
| Live data push | Polling interval | Existing WS `virtual_snapshot` broadcast | Already pushes every poll cycle |
| Throttle score computation | Frontend JS calculation | Backend `compute_throttle_score()` result in API payload | Score depends on ThrottleCaps which is backend-only |

## Common Pitfalls

### Pitfall 1: Toggle Flicker on WS Update
**What goes wrong:** Auto-throttle toggle visually flickers when WS virtual_snapshot arrives and re-sets the checked state.
**Why it happens:** `updateVirtualPVPage()` runs on every WS message. If it naively sets `toggle.checked = data.auto_throttle`, the toggle animates even when no change occurred.
**How to avoid:** Only update `toggle.checked` when the value actually differs from current state. Guard with `if (toggle.checked !== data.auto_throttle)`.
**Warning signs:** Toggle briefly unchecks/rechecks on each WS message.

### Pitfall 2: Stale Preset Indicator After Config Save
**What goes wrong:** User clicks "Aggressive" preset, but the button highlight does not update until next full page load.
**Why it happens:** Config POST returns success, but the WS broadcast does not include `auto_throttle_preset`.
**How to avoid:** Either (a) update button state optimistically on click, or (b) include `auto_throttle_preset` in the `virtual_snapshot` WS payload and update buttons in `updateVirtualPVPage()`.

### Pitfall 3: Throttle State Derivation Race Condition
**What goes wrong:** A device shows "active" state but is actually in cooldown because the contribution payload is stale.
**Why it happens:** `_build_virtual_contributions()` computes state at broadcast time, but the distributor may have changed state between broadcasts.
**How to avoid:** Derive `throttle_state` directly from `DeviceLimitState` fields at broadcast time (not cached). The broadcast runs every poll cycle (~1s), so staleness is bounded.

### Pitfall 4: Contribution Bar Segment Count Mismatch After Device Add/Remove
**What goes wrong:** The number of bar segments does not match the new contributions array, causing visual corruption.
**Why it happens:** `updateVirtualPVPage()` uses `querySelectorAll('.ve-contribution-segment')` and iterates by index. If devices change, the DOM has wrong count.
**How to avoid:** When contribution count changes (compare current segments vs new array length), rebuild the entire bar card instead of incrementally updating. This is an existing limitation of the current code.

### Pitfall 5: Preset Parameters Not Applied Until Distributor Restart
**What goes wrong:** User selects "Aggressive" but convergence behavior does not change.
**Why it happens:** If the distributor reads constants at import time, config changes are not picked up.
**How to avoid:** The distributor must read preset parameters from `self._config` on each `distribute()` call, not from module-level constants. This requires refactoring the constants in `distributor.py` to be config-driven.

## Code Examples

### Backend: Enriched Contributions

```python
def _build_virtual_contributions(
    app_ctx: Any, config: Config,
) -> tuple[float, float, list[dict]]:
    total_power_w = 0
    total_rated_w = 0
    contributions: list[dict] = []
    distributor = (
        getattr(app_ctx, "device_registry", None)
        and app_ctx.device_registry.distributor
    )
    device_limits = distributor.get_device_limits() if distributor is not None else {}

    for inv in config.inverters:
        ds = app_ctx.devices.get(inv.id)
        power_w = 0
        rated_w = inv.rated_power
        if ds and ds.collector and ds.collector.last_snapshot:
            snap_inv = ds.collector.last_snapshot.get("inverter", {})
            power_w = snap_inv.get("ac_power_w", 0)
            if not rated_w:
                rated_w = ds.collector.last_snapshot.get("rated_power_w", 0)
        total_power_w += power_w
        total_rated_w += rated_w
        display_name = inv.name or f"{inv.manufacturer} {inv.model}".strip() or "Inverter"

        # Throttle metadata enrichment (Phase 36)
        throttle_score = 0.0
        throttle_mode = "none"
        measured_response = None
        throttle_state = "disabled" if not inv.throttle_enabled else "active"
        relay_on = True

        if ds and ds.plugin and hasattr(ds.plugin, 'throttle_capabilities'):
            caps = ds.plugin.throttle_capabilities
            throttle_score = compute_throttle_score(caps)
            throttle_mode = caps.mode

        if distributor is not None:
            dist_ds = distributor._device_states.get(inv.id)
            if dist_ds is not None:
                if dist_ds.measured_response_time_s is not None:
                    measured_response = round(dist_ds.measured_response_time_s, 2)
                relay_on = dist_ds.relay_on
                limit_pct = device_limits.get(inv.id, 100.0)
                # Derive throttle state
                if not inv.throttle_enabled:
                    throttle_state = "disabled"
                elif distributor._is_in_startup(dist_ds):
                    throttle_state = "startup"
                elif (hasattr(dist_ds.plugin, 'throttle_capabilities')
                      and dist_ds.plugin.throttle_capabilities.mode == "binary"
                      and dist_ds.last_toggle_ts is not None
                      and time.monotonic() - dist_ds.last_toggle_ts < dist_ds.plugin.throttle_capabilities.cooldown_s):
                    throttle_state = "cooldown"
                elif limit_pct < 100.0 or not relay_on:
                    throttle_state = "throttled"
                else:
                    throttle_state = "active"

        contributions.append({
            "device_id": inv.id,
            "name": display_name,
            "power_w": power_w,
            "throttle_order": inv.throttle_order,
            "throttle_enabled": inv.throttle_enabled,
            "current_limit_pct": device_limits.get(inv.id, 100.0),
            "throttle_score": round(throttle_score, 1),
            "throttle_mode": throttle_mode,
            "measured_response_time_s": measured_response,
            "throttle_state": throttle_state,
            "relay_on": relay_on,
        })

    return total_power_w, total_rated_w, contributions
```

### Backend: Preset Config Fields

```python
# In config.py:
AUTO_THROTTLE_PRESETS = {
    "aggressive": {
        "convergence_tolerance_pct": 10.0,
        "convergence_max_samples": 5,
        "target_change_tolerance_pct": 5.0,
        "binary_off_threshold_w": 100.0,
    },
    "balanced": {
        "convergence_tolerance_pct": 5.0,
        "convergence_max_samples": 10,
        "target_change_tolerance_pct": 2.0,
        "binary_off_threshold_w": 50.0,
    },
    "conservative": {
        "convergence_tolerance_pct": 3.0,
        "convergence_max_samples": 20,
        "target_change_tolerance_pct": 1.0,
        "binary_off_threshold_w": 25.0,
    },
}

# On Config dataclass:
auto_throttle_preset: str = "balanced"
```

### Backend: Distributor Reads Preset Parameters

```python
# In distributor.py, replace module-level constants with config reads:
def _get_convergence_params(self) -> tuple[float, int, float, float]:
    from pv_inverter_proxy.config import AUTO_THROTTLE_PRESETS
    preset_name = getattr(self._config, 'auto_throttle_preset', 'balanced')
    params = AUTO_THROTTLE_PRESETS.get(preset_name, AUTO_THROTTLE_PRESETS['balanced'])
    return (
        params['convergence_tolerance_pct'],
        params['convergence_max_samples'],
        params['target_change_tolerance_pct'],
        params['binary_off_threshold_w'],
    )
```

### CSS: New Styles

```css
/* Auto-Throttle control card */
.ve-auto-throttle-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}

.ve-preset-group {
    display: flex;
    gap: 8px;
}

.ve-throttle-info-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
    font-size: 0.85rem;
}

/* Throttle state dot colors handled inline via style attr */
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_webapp.py -x -k throttle` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| THRT-10 | Virtual snapshot API includes auto_throttle; config POST toggles auto_throttle | unit | `python -m pytest tests/test_webapp.py -x -k auto_throttle` | Extend existing |
| THRT-11 | Device snapshot includes throttle_score, throttle_mode, measured_response_time_s | unit | `python -m pytest tests/test_webapp.py -x -k throttle_score` | Extend existing |
| THRT-12 | Config POST accepts auto_throttle_preset; distributor uses preset params | unit | `python -m pytest tests/test_distributor.py -x -k preset` | New tests |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_webapp.py tests/test_distributor.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Extend `tests/test_webapp.py` -- verify enriched contribution payload includes throttle metadata
- [ ] Extend `tests/test_distributor.py` -- verify preset parameter reads affect convergence behavior
- [ ] Add `auto_throttle_preset` to Config in `config.py` (must exist before tests)

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/pv_inverter_proxy/static/app.js` -- virtual PV page rendering (lines 1740-1953)
- Project codebase: `src/pv_inverter_proxy/webapp.py` -- `_build_virtual_contributions()` (lines 795-833), virtual snapshot handler (lines 1590-1612), config save with `auto_throttle` (lines 404-406)
- Project codebase: `src/pv_inverter_proxy/distributor.py` -- DeviceLimitState fields, convergence constants (lines 23-50)
- Project codebase: `src/pv_inverter_proxy/config.py` -- Config.auto_throttle (line 121)
- Project codebase: `src/pv_inverter_proxy/static/style.css` -- ve-toggle, ve-contribution-bar, ve-throttle-table styles
- Phase 35 research: `.planning/phases/35-smart-auto-throttle-algorithm/35-RESEARCH.md`
- CLAUDE.md: Venus OS gui-v2 design system (color tokens, naming conventions, component patterns)

### Secondary (MEDIUM confidence)
- Phase 35 summaries: convergence tracking implementation, auto_throttle config field, WS broadcast enrichment

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all vanilla JS, no new dependencies, extends existing patterns
- Architecture: HIGH - clear extension points in contributions builder, virtual page builder, and config API
- Pitfalls: HIGH - identified from actual DOM update patterns and config propagation paths
- Presets: MEDIUM - the specific parameter values (aggressive/balanced/conservative) may need tuning in practice

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable -- no external dependencies)
