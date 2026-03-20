# Phase 20: Discovery UI & Onboarding - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

UI for triggering network scans, displaying real-time progress, previewing discovered inverters, and auto-scanning on first setup. Connects the Phase 17 scanner backend to the Phase 19 inverter management UI. No new backend scanner logic — this phase is frontend + API wiring.

</domain>

<decisions>
## Implementation Decisions

### Scan-Fortschritt
- Horizontale Progress-Bar mit Phasen-Text darunter: "Scanning 192.168.3.x (142/253)..." dann "Verifying SunSpec (3/5)..."
- Progress-Bar nutzt `var(--ve-blue)` Füllfarbe
- Fortschritt wird über bestehende WebSocket-Infrastruktur gestreamt (scanner `progress_callback` → WS broadcast)
- Progress-Bar erscheint unter dem Inverter-Panel (nicht darin, nicht als Overlay)
- Scan ist nicht-blockierend: Venus OS Config bleibt während des Scans bedienbar
- Nur der Discover-Button wird während des Scans disabled

### Ergebnis-Vorschau & Übernahme
- Ergebnis-Liste mit Checkboxen: jeder gefundene Inverter als Zeile mit Checkbox + Manufacturer + Model + Host:Port + Unit ID
- "Alle übernehmen" Button oben über der Ergebnis-Liste
- Bereits konfigurierte Inverter werden ausgegraut mit "Bereits konfiguriert" Label anstatt Checkbox (Checkbox disabled)
- Leerer Scan: Orange `ve-hint-card` mit Tipps: "Keine Inverter gefunden. Prüfe: Sind die Geräte eingeschaltet? Ist Modbus TCP aktiviert? Stimmen die Ports?"
- Übernommene Inverter werden sofort als enabled=true gespeichert
- Erster übernommener Inverter wird automatisch aktives Proxy-Target

### Auto-Scan Onboarding
- Wenn Config-Seite geöffnet wird und Inverter-Liste leer: Scan startet automatisch im Hintergrund
- Trigger: jedes Mal wenn Liste leer (nicht nur erstes Mal, kein localStorage-Flag)
- Einfache Logik: `loadInverters()` → Liste leer? → Scan starten
- Bei genau 1 Ergebnis: automatisch übernehmen + Toast ("Inverter gefunden und hinzugefügt")
- Bei mehreren Ergebnissen: Checkbox-Liste anzeigen, User bestätigt
- Bei 0 Ergebnissen: Hint-Card mit Tipps

### Scan-Button Platzierung & Ports-Feld
- Auto-Discover Button im Inverter-Panel-Header, links vom + Button: [Inverters 🔍 +]
- Icon: Lupe oder Radar-Symbol (16x16 SVG, konsistent mit Edit/Delete Icons)
- Während Scan: Button disabled + Icon wechselt zu Spinner. Tooltip: "Scan läuft..."
- Ports-Feld unter der Inverter-Liste, immer sichtbar, kompakt
- Label: "Scan-Ports:" mit `ve-text-dim` Styling, Input-Feld mit Default "502, 1502"
- Ports werden persistent in Config YAML gespeichert unter `scanner.ports`
- Komma-getrennte Werte im Feld

### Claude's Discretion
- Exact SVG icon for discover button (magnifying glass vs radar)
- Progress-Bar height and animation style
- Checkbox styling in result list
- Transition/animation when results appear after scan
- Toast text variations
- Responsive behavior of scan results on mobile

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scanner Backend (Phase 17)
- `src/venus_os_fronius_proxy/scanner.py` — `scan_subnet(config, progress_callback)`, `ScanConfig` (ports, concurrency, skip_ips, scan_unit_ids), `DiscoveredDevice` dataclass, `detect_subnet()`
- `src/venus_os_fronius_proxy/webapp.py` lines 856-882 — `scanner_discover_handler()` POST /api/scanner/discover endpoint (must be enhanced for WS progress)

### WebSocket Infrastructure
- `src/venus_os_fronius_proxy/webapp.py` lines 502-540 — `ws_handler()`, existing WS client management
- `src/venus_os_fronius_proxy/webapp.py` line 545 — `broadcast_to_clients()` pattern for WS broadcast

### Multi-Inverter Config (Phase 18)
- `src/venus_os_fronius_proxy/config.py` — `InverterEntry` dataclass, `Config.inverters` list, `get_active_inverter()`, `load_config()`/`save_config()`
- `src/venus_os_fronius_proxy/webapp.py` — CRUD endpoints GET/POST/PUT/DELETE `/api/inverters`

### Frontend (Phase 19)
- `src/venus_os_fronius_proxy/static/app.js` — `loadInverters()`, `createInverterRow()`, inverter CRUD JS, `showToast()`
- `src/venus_os_fronius_proxy/static/index.html` — `#inverter-list` container, `#btn-add-inverter`, inverter panel structure
- `src/venus_os_fronius_proxy/static/style.css` — `ve-inv-*` classes, `ve-hint-card`, `ve-panel-header`

### Design System
- `CLAUDE.md` — Color tokens, typography, spacing, animation tokens, component patterns, naming conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scan_subnet(config, progress_callback)` — Already supports progress callback with (phase, current, total) signature
- `broadcast_to_clients(app, snapshot)` — WebSocket broadcast for real-time updates
- `showToast(msg, type)` — Toast notification system
- `ve-hint-card` / `ve-hint-card--success` — Hint card pattern for empty states and tips
- `ve-panel-header` — Header with inline action buttons (already has + button)
- `loadInverters()` — Fetches and renders inverter list (trigger point for auto-scan)
- `ScanConfig.ports` — Already configurable, default [502, 1502]

### Established Patterns
- Instant CRUD via fetch (PUT/DELETE) — no dirty-tracking for inverter operations
- WebSocket messages as JSON with `type` field for routing
- Scanner returns `DiscoveredDevice` with `supported` property
- Config uses dataclasses, YAML persistence, atomic save via temp file + os.replace()

### Integration Points
- `scanner_discover_handler()` needs enhancement: start scan as background task, stream progress via WS
- `ws_handler()` needs new message type for scan progress events
- `loadInverters()` in app.js: add empty-list check → trigger auto-scan
- Config YAML: add `scanner:` section with `ports:` list
- New WS message types: `scan_progress`, `scan_complete`, `scan_error`
- POST `/api/inverters` for batch-adding confirmed scan results

</code_context>

<specifics>
## Specific Ideas

- Zero-config Erlebnis: User installiert App, öffnet Config, Inverter ist schon da (single-inverter auto-add)
- Ports-Feld mit Default "502, 1502" — beide Werte vorbelegt weil SolarEdge oft auf 1502 konfiguriert wird
- Progress-Bar soll sich "schnell" anfühlen — ~15-30s für /24 Subnet ist akzeptabel
- Scan-Ergebnisse erscheinen dort wo auch die Progress-Bar war (gleicher Bereich unter Inverter-Panel)

</specifics>

<deferred>
## Deferred Ideas

- Live connection status dots (green/orange/red) in inverter list — future enhancement
- Multi-proxy parallel output to Venus OS — MPRX-01/02 future scope
- Scan abort/cancel functionality — could be added later
- Scheduled periodic re-scan — not discussed, future scope

</deferred>

---

*Phase: 20-discovery-ui-onboarding*
*Context gathered: 2026-03-20*
