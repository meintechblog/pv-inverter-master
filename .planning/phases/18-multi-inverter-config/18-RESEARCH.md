# Phase 18: Multi-Inverter Config - Research

**Researched:** 2026-03-20
**Domain:** Python config system (dataclasses + YAML), aiohttp REST API, migration logic
**Confidence:** HIGH

## Summary

Phase 18 transforms the single-inverter config into a multi-inverter list. The existing codebase uses Python dataclasses serialized to YAML via `dataclasses.asdict()` and `pyyaml`. The migration path is straightforward: detect old `inverter:` key in raw YAML data, convert to `inverters:` list, write back immediately. New CRUD endpoints follow existing aiohttp patterns already established in `webapp.py`.

The primary complexity is in the `Config` dataclass change (`inverter` singular to `inverters` list) and ensuring all references to `config.inverter` across the codebase are updated to use the active inverter from the list. Python's `uuid` stdlib module provides UUID4 generation with no additional dependencies.

**Primary recommendation:** Use `uuid.uuid4().hex[:12]` for short stable IDs (12 hex chars = 2.8 trillion combinations, sufficient for a list that will rarely exceed 10 entries). Detect migration via presence of `inverter:` key (singular) in raw YAML dict. Back up config file before migration as `.yaml.bak`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auto-convert old `inverter:` dict to `inverters:` list on first load
- Write back migrated format immediately (no lazy migration)
- Old `inverter:` key is removed after migration -- no fallback preservation
- Update `config.example.yaml` to show the new multi-inverter format
- Migration is silent and lossless -- existing host/port/unit_id preserved as first entry
- Each inverter entry contains: `host`, `port`, `unit_id`, `enabled`, `manufacturer`, `model`, `serial`, `firmware_version`
- Auto-generated UUID (`id` field) per entry for API addressing -- stable across config edits
- `manufacturer`, `model`, `serial`, `firmware_version` are populated by scanner (Phase 17) or left empty for manual entries
- Default `enabled: true` for migrated entries and auto-discovered entries
- Migrated entry gets `manufacturer`/`model`/`serial`/`firmware_version` set to empty string
- New CRUD endpoints: `GET /api/inverters`, `POST /api/inverters`, `PUT /api/inverters/{id}`, `DELETE /api/inverters/{id}`
- `/api/config` GET response changes: return `inverters: [...]` list instead of `inverter: {...}`
- `/api/config` POST (save) continues to work but routes to new multi-inverter storage internally
- Proxy uses the first enabled inverter in list order -- simple, backward compatible
- When active inverter is disabled or deleted: fall through to next enabled entry
- If no enabled inverters remain: proxy stops polling, logs clear warning message
- Hot-reload on inverter change: reconfigure plugin with new active inverter's host/port/unit_id
- Active inverter is marked in API response (e.g., `"active": true` flag)

### Claude's Discretion
- UUID generation strategy (uuid4 vs shorter ID)
- Exact migration detection logic (presence of `inverter:` key vs `inverters:` key)
- Error handling for corrupted or partial YAML during migration
- Config file backup before migration (optional safety net)

### Deferred Ideas (OUT OF SCOPE)
- Manufacturer + Model inline display in Config page -- Phase 19
- Toggle slider for enable/disable per inverter -- Phase 19
- Delete with confirmation -- Phase 19
- Auto-discover button and scan UI -- Phase 20
- Multi-proxy (multiple simultaneous Fronius outputs to Venus OS) -- Future scope (MPRX-01/02)

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | Config unterstuetzt mehrere Inverter-Eintraege (Liste statt einzelner Eintrag) | New `InverterEntry` dataclass with UUID, `Config.inverters: list[InverterEntry]`, CRUD API endpoints, active inverter selection logic |
| CONF-05 | Bestehende Single-Inverter Config wird automatisch ins Multi-Inverter Format migriert | Migration logic in `load_config()` detecting `inverter:` key, converting to `inverters:` list, writing back immediately with backup |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | 6.0.x (installed: 6.0.3) | YAML config serialization | Already in use, `yaml.safe_load` / `yaml.dump` |
| dataclasses | stdlib | Config schema definition | Already in use for all config types |
| uuid | stdlib | Stable inverter entry IDs | No extra dependency, `uuid4()` for random UUIDs |
| aiohttp | 3.10.x | REST API endpoints | Already in use for all webapp routes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog | 24.x | Structured logging for migration/CRUD | Already used everywhere |
| ipaddress | stdlib | IP validation in `validate_inverter_config` | Already used |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uuid4().hex[:12] | Full uuid4 string (36 chars) | Full UUID is overkill for <20 entries; short hex is human-friendly in URLs |
| uuid4().hex[:12] | nanoid | Would add dependency for no real benefit |

**No new installations required.** All dependencies are already in `pyproject.toml`.

## Architecture Patterns

### Recommended Changes to Config Module

```
src/venus_os_fronius_proxy/
├── config.py              # Modified: InverterEntry dataclass, migration logic in load_config
├── webapp.py              # Modified: new CRUD routes, updated config_get/save handlers
├── __main__.py            # Modified: use config.inverters[0] (or first enabled) for plugin init
└── config/
    └── config.example.yaml  # Updated: show inverters: list format
```

### Pattern 1: InverterEntry Dataclass

**What:** New dataclass replacing `InverterConfig` with additional identity fields and UUID.
**When to use:** Every reference to an inverter in config.

```python
import uuid
from dataclasses import dataclass, field

def _generate_id() -> str:
    return uuid.uuid4().hex[:12]

@dataclass
class InverterEntry:
    host: str = "192.168.3.18"
    port: int = 1502
    unit_id: int = 1
    enabled: bool = True
    id: str = field(default_factory=_generate_id)
    manufacturer: str = ""
    model: str = ""
    serial: str = ""
    firmware_version: str = ""
```

### Pattern 2: Migration in load_config

**What:** Detect old format, convert, write back, return new format.
**When to use:** Every call to `load_config()`.

```python
def load_config(path: str | None = None) -> Config:
    config_path = path or DEFAULT_CONFIG_PATH
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}

    # Migration: inverter (singular) -> inverters (list)
    migrated = False
    if "inverter" in data and "inverters" not in data:
        old = data.pop("inverter")
        entry = {
            "id": _generate_id(),
            "host": old.get("host", "192.168.3.18"),
            "port": old.get("port", 1502),
            "unit_id": old.get("unit_id", 1),
            "enabled": True,
            "manufacturer": "",
            "model": "",
            "serial": "",
            "firmware_version": "",
        }
        data["inverters"] = [entry]
        migrated = True

    # ... build Config from data ...

    if migrated and config_path != DEFAULT_CONFIG_PATH or migrated:
        # Backup original
        import shutil
        backup_path = config_path + ".bak"
        if os.path.exists(config_path) and not os.path.exists(backup_path):
            shutil.copy2(config_path, backup_path)
        # Write migrated format
        save_config(config_path, config)
        log.info("config.migrated", backup=backup_path)

    return config
```

### Pattern 3: Active Inverter Helper

**What:** Property or function to get the first enabled inverter from the list.
**When to use:** Anywhere the proxy needs the current active inverter.

```python
def get_active_inverter(config: Config) -> InverterEntry | None:
    """Return the first enabled inverter, or None if all disabled."""
    for inv in config.inverters:
        if inv.enabled:
            return inv
    return None
```

### Pattern 4: CRUD API Handlers

**What:** Standard REST endpoints following existing aiohttp handler patterns.
**When to use:** New `/api/inverters` routes.

```python
async def inverters_list_handler(request: web.Request) -> web.Response:
    config: Config = request.app["config"]
    active = get_active_inverter(config)
    items = []
    for inv in config.inverters:
        d = dataclasses.asdict(inv)
        d["active"] = (active is not None and inv.id == active.id)
        items.append(d)
    return web.json_response({"inverters": items})

async def inverters_add_handler(request: web.Request) -> web.Response:
    body = await request.json()
    # validate, create InverterEntry, append to config.inverters
    # save_config, return new entry with 201

async def inverters_update_handler(request: web.Request) -> web.Response:
    inv_id = request.match_info["id"]
    # find entry by id, update fields, validate, save

async def inverters_delete_handler(request: web.Request) -> web.Response:
    inv_id = request.match_info["id"]
    # find and remove, handle active inverter fallthrough
```

### Anti-Patterns to Avoid
- **Mutating config.inverters without saving:** Every CRUD operation must call `save_config()` to persist changes. The in-memory Config and YAML file must stay in sync.
- **Using list index as identifier:** Indices change when items are deleted. The UUID `id` field is the stable reference.
- **Breaking backward compat in /api/config:** The GET response changes from `inverter: {}` to `inverters: []`, but the POST handler must still accept the old format during transition (Phase 19 frontend will adapt).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unique IDs | Custom counter or timestamp | `uuid.uuid4().hex[:12]` | Collision-free, no state needed |
| Atomic file write | Manual rename logic | Existing `save_config()` pattern (temp + `os.replace`) | Already battle-tested in codebase |
| YAML serialization | Custom dict building | `dataclasses.asdict()` + `yaml.dump()` | Already works, handles nested structures |
| Input validation | Per-endpoint duplicate checks | Existing `validate_inverter_config()` | Reuse for each inverter entry |

**Key insight:** The codebase already has all the building blocks (atomic save, validation, dataclass serialization). This phase is primarily about restructuring, not building new infrastructure.

## Common Pitfalls

### Pitfall 1: dataclasses.asdict with custom default_factory
**What goes wrong:** `dataclasses.asdict()` serializes everything including the `id` field. When loading back, `_generate_id()` default_factory would create a NEW id instead of using the saved one.
**Why it happens:** The `field(default_factory=_generate_id)` only fires when no value is provided.
**How to avoid:** When constructing `InverterEntry` from YAML data, always pass the saved `id` value. Only use the factory default for truly new entries.
**Warning signs:** IDs changing between save/load cycles.

### Pitfall 2: Stale config.inverter References
**What goes wrong:** Code throughout the app references `config.inverter` (singular). After migration, this attribute no longer exists.
**Why it happens:** The dataclass field name changes from `inverter` to `inverters`.
**How to avoid:** Search all references to `config.inverter` and update them. Key locations: `__main__.py` (plugin creation), `webapp.py` (config_get/save handlers), startup log message.
**Warning signs:** `AttributeError: 'Config' object has no attribute 'inverter'` at runtime.

### Pitfall 3: Hot-reload Race Condition
**What goes wrong:** Deleting or disabling the active inverter while it's being polled could cause the plugin to error.
**Why it happens:** The proxy poll loop reads from the current plugin's host/port, which is being reconfigured.
**How to avoid:** Use the existing `request.app["reconfiguring"]` flag pattern from `config_save_handler`. Set it before reconfigure, clear after.
**Warning signs:** Modbus connection errors during config changes.

### Pitfall 4: Migration Runs on Every Load
**What goes wrong:** If migration detection is based on absence of `inverters` key, and the file isn't written back, migration runs repeatedly.
**Why it happens:** Decision says write-back is immediate, but if save fails silently, the old format persists.
**How to avoid:** Migration write-back must raise on failure (existing `save_config` does raise). Log migration success explicitly.
**Warning signs:** Repeated "config.migrated" log entries.

### Pitfall 5: Empty inverters List
**What goes wrong:** Fresh install with no config file gets `inverters: []` (empty list), but `get_active_inverter()` returns `None`.
**Why it happens:** Default `InverterConfig` had hardcoded defaults; an empty list has no entries.
**How to avoid:** Fresh install should create a default entry (preserving current default host/port/unit_id behavior). Only `inverters: []` if user explicitly removes all entries.
**Warning signs:** Proxy immediately enters "no active inverter" state on fresh install.

## Code Examples

### Config YAML New Format
```yaml
# Multi-inverter format (migrated or new)
inverters:
  - id: "a1b2c3d4e5f6"
    host: "192.168.3.18"
    port: 1502
    unit_id: 1
    enabled: true
    manufacturer: "SolarEdge"
    model: "SE30K"
    serial: ""
    firmware_version: ""
  - id: "f6e5d4c3b2a1"
    host: "192.168.3.19"
    port: 1502
    unit_id: 1
    enabled: false
    manufacturer: ""
    model: ""
    serial: ""
    firmware_version: ""
```

### Updated Config Dataclass
```python
@dataclass
class Config:
    inverters: list[InverterEntry] = field(default_factory=lambda: [InverterEntry()])
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    night_mode: NightModeConfig = field(default_factory=NightModeConfig)
    webapp: WebappConfig = field(default_factory=WebappConfig)
    venus: VenusConfig = field(default_factory=VenusConfig)
    log_level: str = "INFO"
```

### Loading inverters from YAML Data
```python
inverters_data = data.get("inverters", [])
if inverters_data:
    inverters = [
        InverterEntry(**{
            k: v for k, v in entry.items()
            if k in InverterEntry.__dataclass_fields__
        })
        for entry in inverters_data
    ]
else:
    inverters = [InverterEntry()]  # Default entry for fresh install
```

### API Response Format
```json
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
      "serial": "",
      "firmware_version": "",
      "active": true
    }
  ]
}
```

### Updated /api/config GET Response
```json
{
  "inverters": [
    {"id": "a1b2c3d4e5f6", "host": "192.168.3.18", "port": 1502, "unit_id": 1, "enabled": true, "active": true, "manufacturer": "", "model": "", "serial": "", "firmware_version": ""}
  ],
  "venus": {
    "host": "",
    "port": 1883,
    "portal_id": ""
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `inverter:` single dict | `inverters:` list of dicts | Phase 18 | Breaking change to Config dataclass and API response |
| `config.inverter.host` | `get_active_inverter(config).host` | Phase 18 | All proxy startup and reconfigure code must update |
| No UUID per config entry | UUID `id` field on each entry | Phase 18 | Stable API addressing for CRUD |

**Deprecated/outdated:**
- `InverterConfig` dataclass: replaced by `InverterEntry` with additional fields
- `config.inverter` attribute: replaced by `config.inverters` list

## Open Questions

1. **Should /api/config POST accept the old single-inverter format for backward compatibility?**
   - What we know: Decision says "continues to work but routes to new multi-inverter storage internally"
   - What's unclear: Whether this means accepting `{inverter: {...}}` or just `{inverters: [...]}`
   - Recommendation: Accept both formats during transition. If body contains `inverter:` (singular), update the active inverter. If `inverters:`, replace entire list. This keeps frontend working until Phase 19 updates it.

2. **Default entry on fresh install**
   - What we know: Current `InverterConfig` has defaults (192.168.3.18:1502 unit 1)
   - What's unclear: Whether a fresh install should create a default entry or start with empty list
   - Recommendation: Create one default entry to match current behavior. Users who install fresh still get a working default.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `python3 -m pytest tests/test_config.py tests/test_config_save.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | InverterEntry dataclass has all required fields | unit | `python3 -m pytest tests/test_config.py -x -k inverter_entry` | No -- Wave 0 |
| CONF-01 | Config.inverters is a list of InverterEntry | unit | `python3 -m pytest tests/test_config.py -x -k config_inverters` | No -- Wave 0 |
| CONF-01 | CRUD GET /api/inverters returns list with active flag | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_list` | No -- Wave 0 |
| CONF-01 | CRUD POST /api/inverters adds entry with validation | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_add` | No -- Wave 0 |
| CONF-01 | CRUD PUT /api/inverters/{id} updates entry | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_update` | No -- Wave 0 |
| CONF-01 | CRUD DELETE /api/inverters/{id} removes entry, active fallthrough | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_delete` | No -- Wave 0 |
| CONF-01 | get_active_inverter returns first enabled | unit | `python3 -m pytest tests/test_config.py -x -k active_inverter` | No -- Wave 0 |
| CONF-05 | Old inverter: format migrated to inverters: list | unit | `python3 -m pytest tests/test_config.py -x -k migration` | No -- Wave 0 |
| CONF-05 | Migration preserves host/port/unit_id values | unit | `python3 -m pytest tests/test_config.py -x -k migration_preserves` | No -- Wave 0 |
| CONF-05 | Migration writes back immediately | unit | `python3 -m pytest tests/test_config.py -x -k migration_writeback` | No -- Wave 0 |
| CONF-05 | Fresh install with no file returns default entry | unit | `python3 -m pytest tests/test_config.py -x -k fresh_default` | No -- Wave 0 |
| CONF-05 | Config roundtrip save/load preserves all InverterEntry fields | unit | `python3 -m pytest tests/test_config_save.py -x -k roundtrip_inverters` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_config.py tests/test_config_save.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_config.py` -- new tests for InverterEntry, migration, active inverter
- [ ] `tests/test_config_save.py` -- new tests for multi-inverter roundtrip
- [ ] `tests/test_webapp.py` -- new tests for CRUD inverter endpoints

*(Existing test infrastructure covers framework setup. No new framework installs needed.)*

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `config.py`, `webapp.py`, `scanner.py`, `__main__.py`
- `pyproject.toml` -- confirmed dependency versions and test config
- Python stdlib docs -- `uuid`, `dataclasses`, `shutil` modules

### Secondary (MEDIUM confidence)
- PyYAML behavior with lists of dicts via `yaml.dump(dataclasses.asdict(...))` -- verified by existing `save_config` pattern that already serializes nested dataclasses

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- patterns directly extend existing codebase patterns
- Pitfalls: HIGH -- identified from direct code analysis of current references

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable domain, no external dependency changes expected)
