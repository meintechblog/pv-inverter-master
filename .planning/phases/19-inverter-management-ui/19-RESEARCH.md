# Phase 19: Inverter Management UI - Research

**Researched:** 2026-03-20
**Domain:** Frontend UI — vanilla JS config page with CRUD inverter management
**Confidence:** HIGH

## Summary

Phase 19 replaces the static SolarEdge config panel with a dynamic inverter list UI. The backend CRUD API already exists from Phase 18 (`GET/POST/PUT/DELETE /api/inverters`), and `GET /api/config` already returns `inverters: [...]` with an `active` flag per entry. The frontend work is entirely in `index.html`, `app.js`, and `style.css` — no backend changes needed.

The core UI consists of compact one-line rows per inverter inside a `ve-panel`, with a plus-button for manual add, toggle sliders for enable/disable (instant save via PUT), inline-confirm delete, and an edit-on-click inline form. The existing `ve-toggle` (Apple-style), `ve-dot`, `showToast()`, `ve-hint-card`, and `ve-panel-header` patterns are all reusable.

**Primary recommendation:** Replace the static SolarEdge panel HTML (lines 262-282 of index.html) with a single empty container `div`, then build all inverter rows dynamically in JS from the `GET /api/inverters` response. Keep the Venus OS panel and its dirty-tracking logic untouched.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Compact single-line row per inverter (not card or editable card)
- Row contains: Status-Dot + Host:Port + Manufacturer/Model (if present) + Toggle-Slider + Delete-Icon
- Active (proxied) inverter: blue left border (`var(--ve-blue)` 3px left border)
- Read-only display — fields are NOT inline editable by default
- Edit mode: click on row or edit-icon expands inline form (Host, Port, Unit ID)
- Disabled inverter: text grayed out (`var(--ve-text-dim)`), status dot grey
- Toggle saves immediately via `PUT /api/inverters/{id}` — no extra Save button
- Toast confirms toggle change
- Delete: inline-confirm — delete icon turns red, text changes to "Wirklich loeschen?" with confirm/cancel buttons
- No modal for delete confirmation
- Last inverter can be deleted — empty list shows hint: "Kein Inverter konfiguriert"
- Delete via `DELETE /api/inverters/{id}`
- Old static SolarEdge panel replaced completely by dynamic inverter list
- Venus OS panel stays unchanged
- 2-column `ve-config-grid` layout preserved
- Plus-button in inverter panel header for manual add
- Add form expands with Host, Port, Unit ID fields, uses `POST /api/inverters`
- Empty state: hint card with "Kein Inverter konfiguriert. Fuege einen hinzu oder starte Auto-Discover."
- Manufacturer + Model displayed right of Host:Port in same line (e.g., `192.168.3.18:1502  SolarEdge SE30K`)
- If manufacturer/model empty: show nothing (no placeholder)
- Status dot: green = enabled, grey = disabled (no live connection polling)

### Claude's Discretion
- Exact CSS class names for inverter row components
- Edit form animation (slide-down vs. instant)
- Add form placement (top vs. bottom of list)
- Empty-state illustration/icon
- Toast text for toggle and delete actions
- Responsive behavior of inverter row on mobile

### Deferred Ideas (OUT OF SCOPE)
- Auto-Discover button and scan UI — Phase 20
- Live connection status dots (green/orange/red) — future enhancement
- Multi-proxy parallel output to Venus OS — Future scope (MPRX-01/02)
- Drag-and-drop reorder of inverter list — not discussed
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-02 | User kann jeden Inverter-Eintrag per Toggle-Slider aktivieren/deaktivieren | Toggle uses existing `ve-toggle` pattern, instant PUT to `/api/inverters/{id}` with `{enabled: bool}`, toast feedback via `showToast()` |
| CONF-03 | User kann Inverter-Eintraege loeschen | Inline-confirm pattern (no modal), `DELETE /api/inverters/{id}`, re-render list on success |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS | ES2017+ | All UI logic | Project convention: zero dependencies, no build tooling |
| CSS Custom Properties | N/A | Design tokens | All styling via `var(--ve-*)` tokens per CLAUDE.md |
| Fetch API | Native | HTTP CRUD calls | Already used for all API interactions in app.js |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiohttp | existing | Backend REST API | Already serves CRUD endpoints — no changes needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla JS DOM | lit-html/Preact | Would add build step, violates project convention |
| Inline confirm | Modal dialog | User explicitly rejected modals for delete |

## Architecture Patterns

### Recommended Project Structure
No new files. All changes in existing files:
```
src/venus_os_fronius_proxy/static/
  index.html    # Replace SolarEdge panel HTML with dynamic container
  app.js        # New inverter list CRUD functions, replace old config load/save
  style.css     # New ve-inv-* classes for inverter row components
```

### Pattern 1: Dynamic List Rendering
**What:** Render inverter list from API data using `document.createElement` and `innerHTML` for row templates.
**When to use:** Every time inverters change (load, add, toggle, delete).
**Example:**
```javascript
// Fetch and render inverter list
async function loadInverters() {
    var res = await fetch('/api/inverters');
    var data = await res.json();
    var container = document.getElementById('inverter-list');
    container.innerHTML = '';
    if (data.inverters.length === 0) {
        container.innerHTML = '<div class="ve-hint-card">...</div>';
        return;
    }
    data.inverters.forEach(function(inv) {
        container.appendChild(createInverterRow(inv));
    });
}
```

### Pattern 2: Immediate Toggle Save (Optimistic UI)
**What:** Toggle flips visually immediately, then PUT fires. On error, revert toggle and show error toast.
**When to use:** Enable/disable toggle interaction.
**Example:**
```javascript
async function toggleInverter(id, enabled) {
    try {
        var res = await fetch('/api/inverters/' + id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        var data = await res.json();
        if (data.error) {
            showToast(data.error, 'error');
            loadInverters(); // revert
            return;
        }
        showToast(enabled ? 'Inverter enabled' : 'Inverter disabled', 'success');
        // Re-render to update active flag (active inverter may change)
        loadInverters();
    } catch (e) {
        showToast('Toggle failed: ' + e.message, 'error');
        loadInverters();
    }
}
```

### Pattern 3: Inline Delete Confirmation
**What:** Delete icon click transforms the row to show confirm/cancel instead of opening a modal.
**When to use:** Delete action on any inverter row.
**Example:**
```javascript
function showDeleteConfirm(row, id) {
    var actions = row.querySelector('.ve-inv-actions');
    actions.innerHTML = '<span class="ve-inv-confirm-text">Delete?</span>' +
        '<button class="ve-btn ve-btn--sm ve-btn--cancel" data-action="cancel-delete">No</button>' +
        '<button class="ve-btn ve-btn--sm ve-btn--delete-confirm">Yes</button>';
    // Wire up confirm and cancel handlers
}
```

### Pattern 4: Inline Edit Form
**What:** Click on row or edit-icon expands an inline form below the row with Host, Port, Unit ID fields.
**When to use:** User wants to edit an existing inverter's connection details.
**Example:**
```javascript
function expandEditForm(row, inv) {
    var form = document.createElement('div');
    form.className = 've-inv-edit-form';
    form.innerHTML = '...'; // Host, Port, Unit ID inputs + Save/Cancel
    row.after(form);
}
```

### Anti-Patterns to Avoid
- **Global dirty tracking for inverters:** The old `_cfgOriginal` / `_cfgIsDirty()` pattern was for a single static form. Inverters use per-action CRUD (toggle=instant PUT, edit=inline form with own save). Do NOT extend the old dirty-tracking to inverters.
- **Rebuilding Venus config section:** Venus OS panel must remain untouched with its existing dirty-tracking. Only the inverter section changes.
- **Using `config_save_handler` for inverter changes:** The old `POST /api/config` endpoint still exists for Venus config. Inverter changes go through the dedicated CRUD endpoints.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast notifications | Custom notification system | Existing `showToast(msg, type)` | Already supports info/success/warning/error, auto-dismiss, duplicate suppression |
| Toggle slider | New checkbox CSS | Existing `ve-toggle` pattern | Apple-style toggle already in style.css with checked/disabled states |
| Status dots | Custom indicator | Existing `ve-dot` + `ve-dot--dim` / green background | Already styled with pulse animation for ok state |
| Empty state | Custom empty view | Existing `ve-hint-card` pattern | Orange hint card with icon already styled |
| Panel container | New container | Existing `ve-panel` + `ve-panel-header` | Consistent with Venus config panel |
| Form inputs | Custom inputs | Existing `ve-input` + `ve-form-group` | Dirty state highlighting already supported |

## Common Pitfalls

### Pitfall 1: Forgetting to re-render after toggle
**What goes wrong:** Toggle changes the `active` flag on the backend (first enabled inverter becomes active). If you only update the toggled row, the blue border (active indicator) may be wrong on other rows.
**Why it happens:** `get_active_inverter()` returns the first enabled entry. Toggling one inverter can change which is active.
**How to avoid:** Always call `loadInverters()` after a successful toggle to get fresh `active` flags from the API.
**Warning signs:** Blue left border stays on a disabled inverter or appears on the wrong one.

### Pitfall 2: Old SolarEdge event listeners leaking
**What goes wrong:** The old `btn-save-se`, `btn-cancel-se` event listeners (line 863-866 of app.js) reference DOM elements that no longer exist after replacing the SolarEdge panel.
**Why it happens:** Event listeners attached at load time to elements that get removed.
**How to avoid:** Remove or guard these listeners. The old `_cfgFields.inverter` and related code must be cleaned up entirely.
**Warning signs:** Console errors on config page load about null elements.

### Pitfall 3: loadConfig() breaks Venus section
**What goes wrong:** The existing `loadConfig()` reads `data.inverter.host` (singular). Phase 18 changed `config_get_handler` to return `inverters: [...]` (plural). If `loadConfig()` is not updated, Venus config loading breaks.
**Why it happens:** `loadConfig()` is a single function handling both sections.
**How to avoid:** Split: `loadInverters()` for the inverter list, keep Venus loading in `loadConfig()` reading `data.venus.*`.
**Warning signs:** Venus OS fields show `undefined` after config page load.

### Pitfall 4: Edit form and toggle competing
**What goes wrong:** User has edit form open, then toggles — the row re-renders and the edit form disappears.
**Why it happens:** `loadInverters()` rebuilds all rows.
**How to avoid:** Either close edit form before re-render, or track which inverter has edit open and re-open after render.
**Warning signs:** Edit form content lost on toggle click.

### Pitfall 5: Delete of active inverter leaves proxy without target
**What goes wrong:** Deleting the active (proxied) inverter is allowed. Backend handles this (`_reconfigure_active` picks next enabled or logs warning). But UI should inform user.
**Why it happens:** This is valid behavior — the backend handles it gracefully.
**How to avoid:** After deleting the active inverter, toast should indicate no active inverter if list is now empty or all disabled.
**Warning signs:** User deletes active inverter and doesn't understand why proxy stopped working.

## Code Examples

### API Response Format (from webapp.py)
```javascript
// GET /api/inverters response
{
    "inverters": [
        {
            "id": "a1b2c3d4e5f6",
            "host": "192.168.3.18",
            "port": 1502,
            "unit_id": 1,
            "enabled": true,
            "manufacturer": "SolarEdge",
            "model": "SE30K",
            "serial": "...",
            "firmware_version": "...",
            "active": true  // computed: first enabled entry
        }
    ]
}

// GET /api/config response (Phase 18 format)
{
    "inverters": [...],  // same as above
    "venus": { "host": "...", "port": 1883, "portal_id": "" }
}
```

### Inverter Row HTML Template
```html
<!-- Each row generated dynamically -->
<div class="ve-inv-row ve-inv-row--active" data-id="a1b2c3d4e5f6">
    <span class="ve-dot" style="background: var(--ve-green)"></span>
    <span class="ve-inv-host">192.168.3.18:1502</span>
    <span class="ve-inv-identity">SolarEdge SE30K</span>
    <div class="ve-inv-actions">
        <label class="ve-toggle">
            <input type="checkbox" checked>
            <span class="ve-toggle-track"></span>
        </label>
        <button class="ve-inv-delete" title="Delete">
            <!-- trash icon SVG -->
        </button>
    </div>
</div>
```

### Active Inverter Blue Border
```css
.ve-inv-row--active {
    border-left: 3px solid var(--ve-blue);
}
```

### Disabled Row Styling
```css
.ve-inv-row--disabled .ve-inv-host,
.ve-inv-row--disabled .ve-inv-identity {
    color: var(--ve-text-dim);
}
```

### Panel Header with Plus Button
```html
<div class="ve-panel-header">
    <h2>Inverters</h2>
    <button class="ve-btn ve-btn--sm ve-btn--primary" id="btn-add-inverter" title="Add Inverter">+</button>
</div>
```

### Add Inverter Form
```html
<div class="ve-inv-add-form" style="display:none">
    <div class="ve-form-group">
        <label>Host</label>
        <input type="text" class="ve-input" placeholder="192.168.1.100">
    </div>
    <div class="ve-form-group">
        <label>Port</label>
        <input type="number" class="ve-input" value="1502" min="1" max="65535">
    </div>
    <div class="ve-form-group">
        <label>Unit ID</label>
        <input type="number" class="ve-input" value="1" min="1" max="247">
    </div>
    <span class="ve-btn-pair">
        <button class="ve-btn ve-btn--sm ve-btn--cancel">Cancel</button>
        <button class="ve-btn ve-btn--sm ve-btn--save">Add</button>
    </span>
</div>
```

### Existing Toggle CSS (reuse as-is)
```css
/* Already in style.css — Apple-style toggle */
.ve-toggle { position: relative; display: inline-block; width: 36px; height: 20px; }
.ve-toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
.ve-toggle-track { /* ... rounded track with ::before knob */ }
.ve-toggle input:checked + .ve-toggle-track { background: var(--ve-green); }
.ve-toggle input:disabled + .ve-toggle-track { opacity: 0.4; cursor: not-allowed; }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single inverter config (`data.inverter`) | Multi-inverter list (`data.inverters[]`) | Phase 18 | Frontend must read array, not single object |
| `POST /api/config` for all changes | CRUD endpoints `/api/inverters/{id}` | Phase 18 | Toggle and delete use dedicated endpoints |
| Static HTML form for inverter | Dynamic JS-rendered list | Phase 19 (this) | Complete rewrite of inverter config section |

**Deprecated/outdated:**
- `se-host`, `se-port`, `se-unit` input IDs: removed, replaced by dynamic per-inverter elements
- `_cfgFields.inverter` dirty tracking: removed, inverters use instant CRUD
- `saveConfigSection('inverter')`: removed, replaced by per-inverter PUT/DELETE/POST
- `btn-save-se`, `btn-cancel-se`: removed with old panel

## Open Questions

1. **Should `loadConfig()` be split or kept unified?**
   - What we know: `GET /api/config` returns both `inverters` and `venus`. Could fetch once, populate both sections.
   - What's unclear: Whether to use `GET /api/config` (one call) or `GET /api/inverters` (separate call) for the inverter list.
   - Recommendation: Use `GET /api/config` on page load (one call populates both). Use `GET /api/inverters` for refreshing after toggle/delete/add (avoids touching Venus section). This avoids an extra network call on initial load while keeping targeted refreshes efficient.

2. **Edit form — slide animation or instant?**
   - What we know: User said Claude's discretion.
   - Recommendation: Use `max-height` CSS transition for subtle slide-down. Keeps it consistent with the project's animation tokens (`var(--ve-duration-normal)`).

3. **Add form placement — top or bottom?**
   - What we know: User said Claude's discretion.
   - Recommendation: Bottom of the list (above the empty-state hint if shown). This is the natural position — new items appear at the bottom of existing entries.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `tests/` directory, standard pytest discovery |
| Quick run command | `python -m pytest tests/test_webapp.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-02 | Toggle enable/disable persists via PUT | unit (API) | `python -m pytest tests/test_webapp.py -x -q -k "inverter"` | Partial (Phase 18 added CRUD tests) |
| CONF-03 | Delete inverter removes from config | unit (API) | `python -m pytest tests/test_webapp.py -x -q -k "inverter"` | Partial (Phase 18 added CRUD tests) |
| CONF-02 | Toggle UI renders correct state | manual-only | Visual: toggle slider reflects enabled state | N/A |
| CONF-03 | Delete confirmation UI flow | manual-only | Visual: inline confirm appears, delete removes row | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_webapp.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — Phase 19 is a frontend-only phase. Backend CRUD API tests already exist from Phase 18. No new backend test files needed. Frontend behavior is verified manually (vanilla JS, no test framework for browser UI in this project).

## Sources

### Primary (HIGH confidence)
- `src/venus_os_fronius_proxy/webapp.py` — CRUD handler implementations (lines 900-999), API response format verified
- `src/venus_os_fronius_proxy/config.py` — InverterEntry dataclass fields, `get_active_inverter()` logic verified
- `src/venus_os_fronius_proxy/static/app.js` — Current config JS (lines 728-869), `showToast()` (lines 1184-1232)
- `src/venus_os_fronius_proxy/static/style.css` — `ve-toggle`, `ve-dot`, `ve-panel-header`, `ve-hint-card` patterns verified
- `src/venus_os_fronius_proxy/static/index.html` — Current SolarEdge panel HTML (lines 262-282), config page structure
- `CLAUDE.md` — Design system tokens, naming conventions, component patterns

### Secondary (MEDIUM confidence)
- Phase 18 decisions from STATE.md — API format decisions (confirmed by reading code)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all existing patterns
- Architecture: HIGH — CRUD API exists, UI patterns well-established in codebase
- Pitfalls: HIGH — identified from reading actual code, concrete line references

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable — vanilla JS, no dependency churn)
