# Phase 19: Inverter Management UI - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Config page displays a dynamic inverter list replacing the old static SolarEdge panel. Users can view all configured inverters, enable/disable them via toggle slider, delete with inline confirmation, and manually add new entries. The active (proxied) inverter is visually distinguished. Auto-Discover UI is Phase 20 scope.

</domain>

<decisions>
## Implementation Decisions

### Inverter-Karten Layout
- Kompakte einzeilige Darstellung pro Inverter (nicht Card oder editierbare Karte)
- Zeile enthält: Status-Dot + Host:Port + Manufacturer/Model (wenn vorhanden) + Toggle-Slider + Delete-Icon
- Aktiver (proxied) Inverter: blauer linker Rand (`var(--ve-blue)` left border)
- Read-only Anzeige — Felder sind nicht inline editierbar
- Edit-Modus: Klick auf Zeile oder Edit-Icon klappt Inline-Formular auf (Host, Port, Unit ID)
- Disabled Inverter: Text wird ausgegraut (`var(--ve-text-dim)`), Status-Dot grau

### Toggle & Delete Interaktion
- Toggle-Slider speichert sofort via `PUT /api/inverters/{id}` — kein extra Save-Button nötig
- Toast-Nachricht bestätigt Toggle-Änderung
- Delete: Inline-Confirm — Delete-Icon wird rot, Text ändert sich zu "Wirklich löschen?" mit Bestätigungs/Abbruch-Buttons
- Kein Modal für Delete-Bestätigung
- Letzten Inverter löschen ist erlaubt — leere Liste zeigt Hinweis: "Kein Inverter konfiguriert"
- Delete via `DELETE /api/inverters/{id}`

### Config-Seite Umbau
- Altes statisches "SolarEdge Inverter" Panel wird komplett durch dynamische Inverter-Liste ersetzt
- Venus OS Panel bleibt unverändert daneben
- 2-Spalten `ve-config-grid` Layout bleibt erhalten
- Plus-Button im Inverter-Panel-Header für manuelles Hinzufügen
- "Add Inverter" klappt Formular auf mit Host, Port, Unit ID Feldern
- Nutzt `POST /api/inverters` zum Anlegen
- Leerer Zustand: Hinweis-Card mit Text "Kein Inverter konfiguriert. Füge einen hinzu oder starte Auto-Discover."

### Manufacturer + Model Anzeige
- Anzeige rechts vom Host:Port in der gleichen Zeile: `192.168.3.18:1502  SolarEdge SE30K`
- Wenn manufacturer/model leer: nichts anzeigen (kein Platzhalter)
- Schlank — nur diese zwei Infos, kein Serial, keine Firmware-Version in der Zeile

### Status Dot
- Nur enabled-Status anzeigen (kein live Connection-Polling)
- Grüner Dot (`var(--ve-green)`) = enabled
- Grauer Dot (`var(--ve-text-dim)`) = disabled
- Kein orange/rot für Connection-Status in dieser Phase

### Claude's Discretion
- Exact CSS class names for inverter row components
- Edit-Formular Animation (slide-down vs. instant)
- Add-Formular Platzierung (oben vs. unten in der Liste)
- Empty-state Illustration/Icon
- Toast-Text für Toggle und Delete Aktionen
- Responsive Verhalten der Inverter-Zeile auf Mobile

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Config API (Phase 18 output)
- `src/venus_os_fronius_proxy/webapp.py` — CRUD endpoints: GET/POST/PUT/DELETE `/api/inverters`, updated config_get_handler returning `inverters: [...]`
- `src/venus_os_fronius_proxy/config.py` — InverterEntry dataclass (id, host, port, unit_id, enabled, manufacturer, model, serial, firmware_version), get_active_inverter()

### Frontend
- `src/venus_os_fronius_proxy/static/index.html` lines 248-323 — Current config page HTML (SolarEdge panel to be replaced)
- `src/venus_os_fronius_proxy/static/app.js` lines 728-869 — Current config load/save JS (must be rewritten for multi-inverter)
- `src/venus_os_fronius_proxy/static/style.css` — Venus OS design system tokens, ve-panel, ve-toggle, ve-dot patterns

### Design System
- `CLAUDE.md` — Full design system reference: color tokens, typography, spacing, component patterns, naming conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ve-panel` + `ve-panel-header` — Container pattern for the inverter list panel
- `ve-dot` — Status indicator (10px circle), existing grey/green/orange/red states
- `ve-toggle` / `ve-switch` — Two existing toggle implementations (consolidate to one)
- `ve-btn-pair` — Save/Cancel button group pattern (reusable for inline-confirm delete)
- `ve-hint-card` — Empty state hint card pattern (orange border, icon + text)
- `showToast()` — Existing toast notification system for feedback
- `ve-input` + `ve-input--dirty` — Form input with dirty-state highlighting
- `ve-form-group` — Label + input wrapper

### Established Patterns
- Config dirty-tracking: `_cfgOriginal` + `_cfgIsDirty()` + `_cfgUpdateSaveBtn()` — Venus section keeps this pattern
- Per-section save: each section saves independently via fetch POST
- WebSocket broadcast: `broadcast_to_clients()` for real-time updates
- Hash-based navigation: `#config` shows config page

### Integration Points
- `loadConfig()` in app.js — Must be rewritten to fetch from `GET /api/inverters` and render list dynamically
- `saveConfigSection('inverter')` — Replaced by per-inverter CRUD calls
- `config-form` element — Inverter section becomes dynamic, Venus section stays static
- Old SE input IDs (`se-host`, `se-port`, `se-unit`) — Removed, replaced by dynamic per-inverter elements

</code_context>

<specifics>
## Specific Ideas

- "Schlank, nur Manufacturer und Model — ohne weiteres BlaBla" — User wants minimal identity display
- Toggle should feel instant — no loading spinner, just flip and toast
- Inline-confirm for delete: delete icon turns red, row expands slightly to show confirm/cancel
- Active inverter blue border should be subtle but clear — like a 3px left border accent

</specifics>

<deferred>
## Deferred Ideas

- Auto-Discover button and scan UI — Phase 20
- Live connection status dots (green/orange/rot) — future enhancement
- Multi-proxy parallel output to Venus OS — Future scope (MPRX-01/02)
- Drag-and-drop reorder of inverter list — not discussed, could be future

</deferred>

---

*Phase: 19-inverter-management-ui*
*Context gathered: 2026-03-20*
