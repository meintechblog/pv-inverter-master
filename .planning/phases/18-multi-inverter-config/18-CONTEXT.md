# Phase 18: Multi-Inverter Config - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Config system stores and serves multiple inverter entries, with seamless migration from the existing single-inverter format. YAML structure, dataclass model, migration logic, and REST API endpoints for CRUD operations. No UI changes in this phase — that's Phase 19.

</domain>

<decisions>
## Implementation Decisions

### YAML Migration Format
- Auto-convert old `inverter:` dict to `inverters:` list on first load
- Write back migrated format immediately (no lazy migration)
- Old `inverter:` key is removed after migration — no fallback preservation
- Update `config.example.yaml` to show the new multi-inverter format
- Migration is silent and lossless — existing host/port/unit_id preserved as first entry

### Inverter Identity Fields
- Each inverter entry contains: `host`, `port`, `unit_id`, `enabled`, `manufacturer`, `model`, `serial`, `firmware_version`
- Auto-generated UUID (`id` field) per entry for API addressing — stable across config edits
- `manufacturer`, `model`, `serial`, `firmware_version` are populated by scanner (Phase 17) or left empty for manual entries
- Default `enabled: true` for migrated entries and auto-discovered entries
- Migrated entry gets `manufacturer`/`model`/`serial`/`firmware_version` set to empty string (populated later when scanner runs or connection succeeds)

### API Design
- New CRUD endpoints: `GET /api/inverters` (list all), `POST /api/inverters` (add), `PUT /api/inverters/{id}` (update), `DELETE /api/inverters/{id}` (remove)
- `/api/config` GET response changes: return `inverters: [...]` list instead of `inverter: {...}` — frontend must adapt
- `/api/config` POST (save) continues to work but routes to new multi-inverter storage internally
- Validation per entry: reuse existing `validate_inverter_config()` for host/port/unit_id
- UUID collision prevention: generate new UUID if somehow duplicate

### Active Inverter Selection
- Proxy uses the first enabled inverter in list order — simple, backward compatible
- When active inverter is disabled or deleted: fall through to next enabled entry
- If no enabled inverters remain: proxy stops polling, logs clear warning message
- Hot-reload on inverter change: reconfigure plugin with new active inverter's host/port/unit_id
- Active inverter is marked in API response (e.g., `"active": true` flag)

### Claude's Discretion
- UUID generation strategy (uuid4 vs shorter ID)
- Exact migration detection logic (presence of `inverter:` key vs `inverters:` key)
- Error handling for corrupted or partial YAML during migration
- Config file backup before migration (optional safety net)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Config System
- `src/venus_os_fronius_proxy/config.py` — Current InverterConfig dataclass, load_config/save_config, validate_inverter_config(), atomic save pattern
- `config/config.example.yaml` — Current single-inverter YAML format (must be updated to multi-inverter)

### REST API
- `src/venus_os_fronius_proxy/webapp.py` lines 240-341 — config_get_handler, config_save_handler, config_test_handler (must be adapted for multi-inverter)
- `src/venus_os_fronius_proxy/webapp.py` lines 344-370 — config_test_handler pattern (reusable for per-inverter test)

### Scanner Integration
- `src/venus_os_fronius_proxy/scanner.py` — DiscoveredDevice dataclass with manufacturer/model/serial/firmware fields (Phase 17 output that feeds into new inverter entries)

### Frontend (read-only context)
- `src/venus_os_fronius_proxy/static/app.js` lines 728-869 — Current config load/save JS that must adapt to new API format (Phase 19 scope, but API must be designed with this in mind)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `validate_inverter_config(host, port, unit_id)` — Reuse for per-entry validation in multi-inverter CRUD
- `save_config()` / `load_config()` — Atomic save pattern stays, load needs migration logic
- `DiscoveredDevice` dataclass from scanner.py — Field names align with new InverterConfig fields
- `config_test_handler()` — Test-connect pattern reusable for per-inverter connectivity check

### Established Patterns
- Dataclasses for all config structures — continue with new `InverterEntry` dataclass
- `dataclasses.asdict()` for YAML serialization — works with lists of dataclasses
- Atomic save via temp file + `os.replace()` — keep for multi-inverter writes
- Structlog for all logging — migration and CRUD operations use structured logging
- `shared_ctx` dict for runtime state — store active inverter reference here

### Integration Points
- `Config.inverter` (singular) → `Config.inverters` (list of InverterEntry) — breaking change in dataclass
- `plugin.reconfigure(host, port, unit_id)` — Called when active inverter changes
- `request.app["config"]` — All webapp handlers access config through this
- WebSocket broadcasts — notify frontend when inverter list changes (existing broadcast infrastructure)

</code_context>

<specifics>
## Specific Ideas

- Migration must be invisible to existing users — app starts, old config works, done
- Scanner results (Phase 17) feed directly into new inverter entries via POST /api/inverters
- UUID per entry allows stable references even if host/port changes (e.g., DHCP reassignment)
- Manufacturer + Model display after connect is Phase 19 scope, but data fields must exist now

</specifics>

<deferred>
## Deferred Ideas

- Manufacturer + Model inline display in Config page — Phase 19
- Toggle slider for enable/disable per inverter — Phase 19
- Delete with confirmation — Phase 19
- Auto-discover button and scan UI — Phase 20
- Multi-proxy (multiple simultaneous Fronius outputs to Venus OS) — Future scope (MPRX-01/02)

</deferred>

---

*Phase: 18-multi-inverter-config*
*Context gathered: 2026-03-20*
