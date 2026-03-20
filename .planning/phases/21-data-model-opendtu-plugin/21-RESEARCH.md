# Phase 21: Data Model & OpenDTU Plugin - Research

**Researched:** 2026-03-20
**Domain:** Config data model refactor, typed AppContext, OpenDTU REST plugin
**Confidence:** HIGH

## Summary

Phase 21 bundles two foundational changes: (1) refactoring the config data model and shared_ctx to support typed multi-device configurations, and (2) implementing the OpenDTU plugin for Hoymiles inverter polling and power limiting. Both are prerequisites for all subsequent v4.0 phases (DeviceRegistry, Aggregation, Power Distribution, UI).

The config refactor is a clean break (no v3.1 migration) per user decision. The existing `InverterEntry` dataclass gains a `type` field, a `name` field, and OpenDTU-specific fields (`gateway_host`, `serial`). Gateway credentials are stored in a separate `gateways:` section to avoid duplication across inverters sharing the same OpenDTU. The flat `shared_ctx` dict is replaced with a typed `AppContext` dataclass, with all existing consumers (`proxy.py`, `webapp.py`, `dashboard.py`, `venus_reader.py`, `__main__.py`) migrated in place.

The OpenDTU plugin implements `InverterPlugin` ABC using `aiohttp.ClientSession` (already a dependency at v3.13.3). It polls `GET /api/livedata/status`, translates JSON to SunSpec uint16 register arrays (so `DashboardCollector` works unchanged), and writes power limits via `POST /api/limit/config` with Basic Auth. The critical design constraint is the 25-30s dead-time guard for Hoymiles power limiting -- the plugin must track pending limit state and suppress re-sends.

**Primary recommendation:** Implement in two waves: Wave 1 handles config model + AppContext refactor (pure structural change, no functional change to SolarEdge path). Wave 2 adds the OpenDTU plugin as a new module that can be tested in isolation against the real OpenDTU at 192.168.3.98.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 1 Config-Eintrag pro Hoymiles Inverter (nicht pro Gateway)
- Jeder Eintrag hat: type:"opendtu", gateway_host, serial, name, enabled
- Name wird automatisch aus OpenDTU API uebernommen (User kann aendern)
- Optionales name-Feld fuer ALLE Device-Typen (SolarEdge + OpenDTU)
- Wenn name leer: Fallback auf Manufacturer+Model (SolarEdge) oder Serial (OpenDTU)
- OpenDTU-Inverter sollen per manuellem Discover gefunden werden koennen (Gateway-Host scannen, alle Serials auflisten)
- KEINE Migration von v3.1 Config -- frische Config, alles neu anlernen
- App ist noch nirgendwo produktiv im Einsatz, sauberer Schnitt
- Config-Struktur mit type-Feld pro Device (see CONTEXT.md for full YAML example)
- Gateway-Credentials (user/password) werden pro Gateway-Host gespeichert, nicht pro Inverter (separate gateways: section)
- Default credentials: admin/openDTU42 (OpenDTU Standard)
- Poll-Intervall: 5s Default, konfigurierbar pro Gateway
- Bei Gateway offline: Retry mit exponential Backoff (5s -> 10s -> 30s -> 60s) + Status-Dot
- Shared aiohttp.ClientSession pro Gateway (Connection Pooling)
- OpenDTU Plugin implementiert InverterPlugin ABC
- Dead-Time Guard fuer Power Limit: 25-30s Wartezeit nach Limit-Befehl an Hoymiles
- shared_ctx (flacher dict) wird zu @dataclass AppContext mit typisierten Feldern
- Jedes Device bekommt ein DeviceState-Objekt (collector, poll_counter, connection_state)
- Bestehender Code (__main__.py, webapp.py, proxy.py, dashboard.py) wird auf AppContext umgestellt
- Kein Functional Change fuer bestehende SolarEdge-Funktionalitaet -- nur Strukturaenderung

### Claude's Discretion
- Exakte Felder des AppContext Dataclass
- DeviceState Dataclass Struktur
- OpenDTU Plugin interne Implementierung (aiohttp Session Management, JSON Parsing)
- Error-Handling Details bei OpenDTU API-Fehlern
- Ob Gateway-Config in eigener Dataclass oder als Dict in Config

### Deferred Ideas (OUT OF SCOPE)
- DeviceRegistry with per-device poll lifecycle -- Phase 22
- Virtual inverter aggregation -- Phase 22
- Power limit distribution with priorities -- Phase 23
- Device-centric UI -- Phase 24
- OpenDTU MQTT als Alternative zu REST -- Future Scope (EXT-02)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Config unterstuetzt typisierte Device-Eintraege (type: solaredge \| opendtu) mit typspezifischen Feldern | Config dataclass extension with `type` field, `name` field, OpenDTU-specific fields; separate `gateways:` section for credentials; `load_config` parser updated |
| DATA-02 | Typisierter AppContext ersetzt flachen shared_ctx dict -- jedes Device hat eigenen State | AppContext dataclass with DeviceState per device; migration of all 5 shared_ctx consumers |
| DATA-03 | Bestehende v3.1 Configs werden automatisch migriert (type: solaredge als Default) | CONTEXT.md locks: NO migration, fresh config. This requirement contradicts the user decision. Recommend marking as N/A or updating REQUIREMENTS.md |
| DTU-01 | System pollt OpenDTU REST API (/api/livedata/status) und liest AC Power, Voltage, Current, YieldDay, DC Channel Daten pro Hoymiles Inverter | OpenDTU plugin polls GET /api/livedata/status?inv={serial}, JSON-to-SunSpec register translation |
| DTU-02 | Jeder Hoymiles Inverter hinter einem OpenDTU Gateway wird als eigenes Device behandelt (1 OpenDTU -> N Devices via Serial) | Per-serial config entries, gateway_host links to gateways section; discover endpoint lists serials from one OpenDTU |
| DTU-03 | System kann Power Limit pro Hoymiles Inverter setzen via POST /api/limit/config mit OpenDTU Basic Auth | Plugin write_power_limit() POSTs with serial, limit_type=1, limit_value=pct; auth from gateways config |
| DTU-04 | OpenDTU Plugin implementiert InverterPlugin ABC (poll, write_power_limit, reconfigure, close) | Full ABC implementation; all 7 methods mapped to OpenDTU REST equivalents |
| DTU-05 | System handelt die 18-25s Latenz bei Hoymiles Power Limit korrekt (Dead-Time Guard, kein Oszillieren) | Dead-time tracking in plugin; suppress re-sends for 25-30s after limit command; check /api/limit/status for confirmation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | 3.13.3 (installed) | HTTP client for OpenDTU REST polling + Basic Auth | Already a dependency; ClientSession is async-native; BasicAuth built-in |
| Python dataclasses | stdlib | AppContext, DeviceState, GatewayConfig, extended InverterEntry | Established project pattern; no pydantic needed |
| PyYAML | >=6.0 (installed) | Config persistence with new sections | Existing config system uses yaml.safe_load/yaml.dump |
| structlog | >=24.0 (installed) | Structured logging for OpenDTU plugin | Project standard logger |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Async poll loop, gather, sleep | OpenDTU polling at 5s interval |
| enum | stdlib | ConnectionState extension | Gateway connection states |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiohttp.ClientSession | httpx | Would add new dependency for zero benefit; aiohttp already installed |
| dataclasses | pydantic | 5MB+ overhead; dataclasses sufficient for config validation |

**Installation:**
```bash
# No new packages needed
pip install -e .
```

## Architecture Patterns

### Recommended Project Structure
```
src/venus_os_fronius_proxy/
  config.py           # MODIFIED: add type, name, GatewayConfig, load gateways section
  context.py          # NEW: AppContext + DeviceState dataclasses
  plugins/
    __init__.py        # MODIFIED: add plugin_factory function
    solaredge.py       # UNCHANGED
    opendtu.py         # NEW: OpenDTU plugin implementing InverterPlugin ABC
  __main__.py          # MODIFIED: use AppContext instead of shared_ctx dict
  proxy.py             # MODIFIED: accept AppContext instead of shared_ctx dict
  webapp.py            # MODIFIED: accept AppContext instead of shared_ctx dict
  dashboard.py         # MODIFIED: accept AppContext (minimal, collect() signature)
  venus_reader.py      # MODIFIED: accept AppContext instead of shared_ctx dict
```

### Pattern 1: Config Model with Type Discrimination
**What:** Single `inverters:` list with `type` field discriminating SolarEdge vs OpenDTU entries. Gateway credentials in separate `gateways:` section keyed by host.
**When to use:** Loading and validating config at startup; saving config after UI changes.
**Example:**
```python
# Source: CONTEXT.md locked decision
@dataclass
class InverterEntry:
    type: str = "solaredge"         # "solaredge" | "opendtu"
    host: str = "192.168.3.18"     # Modbus host (solaredge) or ignored (opendtu)
    port: int = 1502               # Modbus port (solaredge) or ignored (opendtu)
    unit_id: int = 1               # Modbus unit (solaredge) or ignored (opendtu)
    gateway_host: str = ""         # OpenDTU gateway IP (opendtu only)
    serial: str = ""               # Hoymiles inverter serial (opendtu only)
    name: str = ""                 # User-friendly name (all types)
    enabled: bool = True
    id: str = field(default_factory=_generate_id)
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""

@dataclass
class GatewayConfig:
    host: str = ""
    user: str = "admin"
    password: str = "openDTU42"
    poll_interval: float = 5.0

@dataclass
class Config:
    inverters: list[InverterEntry] = field(default_factory=list)
    gateways: dict[str, list[GatewayConfig]] = field(default_factory=dict)
    # ... existing fields unchanged ...
```

### Pattern 2: Typed AppContext Replacing shared_ctx
**What:** A dataclass that replaces the flat `shared_ctx: dict` with typed fields. All existing consumers migrate from `shared_ctx["key"]` to `app_ctx.key`.
**When to use:** Everywhere shared_ctx is currently used.
**Example:**
```python
# Source: Claude's discretion, based on existing shared_ctx keys analysis
@dataclass
class DeviceState:
    """Per-device runtime state."""
    collector: DashboardCollector
    poll_counter: dict = field(default_factory=lambda: {"success": 0, "total": 0})
    conn_mgr: ConnectionManager | None = None
    last_poll_data: dict | None = None  # raw poll registers for register viewer

@dataclass
class AppContext:
    """Typed application context replacing flat shared_ctx dict."""
    # Core infrastructure
    cache: RegisterCache | None = None
    control_state: ControlState | None = None
    config: Config | None = None
    config_path: str = ""

    # Device states (keyed by InverterEntry.id)
    devices: dict[str, DeviceState] = field(default_factory=dict)

    # Venus OS
    venus_mqtt_connected: bool = False
    venus_os_detected: bool = False
    venus_os_detected_ts: float = 0.0
    venus_os_client_ip: str = ""
    venus_task: asyncio.Task | None = None

    # Webapp
    webapp: web.Application | None = None

    # Internal
    polling_paused: bool = False
    _last_modbus_client_ip: str = ""
    override_log: OverrideLog | None = None
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
```

### Pattern 3: OpenDTU Plugin with SunSpec Register Synthesis
**What:** The OpenDTU plugin reads JSON from the REST API and synthesizes SunSpec uint16 register arrays so the existing `DashboardCollector._decode_all()` works unchanged. This is the translation layer.
**When to use:** Every poll cycle.
**Example:**
```python
# Source: OpenDTU API docs + existing SunSpec register layout
def _json_to_poll_result(self, data: dict) -> PollResult:
    """Convert OpenDTU JSON response to SunSpec register format."""
    inv = self._find_inverter(data)
    if inv is None:
        return PollResult([], [], success=False, error=f"Serial {self.serial} not found")

    # Extract physical values from JSON
    ac_power_w = inv.get("AC", {}).get("0", {}).get("Power", {}).get("v", 0)
    ac_voltage_v = inv.get("AC", {}).get("0", {}).get("Voltage", {}).get("v", 0)
    ac_current_a = inv.get("AC", {}).get("0", {}).get("Current", {}).get("v", 0)
    ac_freq_hz = inv.get("AC", {}).get("0", {}).get("Frequency", {}).get("v", 0)
    # ... DC channels, temperature, yields ...

    # Encode into SunSpec Model 103 register format with known scale factors
    inverter_regs = self._encode_model_103(
        ac_power_w, ac_voltage_v, ac_current_a, ac_freq_hz, ...
    )
    common_regs = self._build_common_registers()

    return PollResult(common_regs, inverter_regs, success=True)
```

### Pattern 4: Dead-Time Guard for Power Limiting
**What:** After sending a power limit to an OpenDTU/Hoymiles inverter, suppress re-sends for a configurable dead-time (25-30s). Check `/api/limit/status` to confirm the limit was applied.
**When to use:** Every `write_power_limit()` call in the OpenDTU plugin.
**Example:**
```python
class OpenDTUPlugin(InverterPlugin):
    DEAD_TIME_S = 30.0  # Conservative: 25s typical + 5s margin

    def __init__(self, ...):
        self._last_limit_ts: float = 0.0
        self._limit_pending: bool = False

    async def write_power_limit(self, enable: bool, limit_pct: float) -> WriteResult:
        now = time.monotonic()
        if self._limit_pending and (now - self._last_limit_ts) < self.DEAD_TIME_S:
            return WriteResult(success=True, error=None)  # Suppress, previous still pending

        # POST /api/limit/config
        result = await self._post_limit(enable, limit_pct)
        if result.success:
            self._last_limit_ts = now
            self._limit_pending = True
        return result
```

### Anti-Patterns to Avoid
- **Storing OpenDTU credentials per inverter entry:** Duplicates passwords when multiple Hoymiles share one OpenDTU gateway. Use the `gateways:` section instead.
- **Polling OpenDTU at 1s:** ESP32 overload. Use 5s minimum (Hoymiles radio updates every ~15s anyway).
- **Creating new aiohttp.ClientSession per poll:** Connection overhead. Create one session per gateway at connect(), reuse across polls.
- **Mixing shared_ctx dict access with AppContext:** During migration, do NOT leave some code using dict access and other using typed access. Migrate all consumers atomically.
- **Running `load_config()` migration for old format:** User decision is NO migration. Remove or disable the `inverter:` -> `inverters:` migration path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP Basic Auth | Custom Authorization header | `aiohttp.BasicAuth("admin", "openDTU42")` | Built into aiohttp, handles encoding correctly |
| HTTP connection pooling | Manual session management | `aiohttp.ClientSession()` with keepalive | aiohttp handles TCP keepalive, connection reuse, timeouts |
| JSON response parsing | Manual string parsing | `response.json()` from aiohttp | Handles encoding, content-type validation |
| Config YAML persistence | Custom file writing | Existing `save_config()` with atomic write | Already handles temp file + os.replace() pattern |
| Exponential backoff | Custom retry logic | Existing `ConnectionManager` pattern | Already proven in SolarEdge path; adapt for OpenDTU |

**Key insight:** The existing codebase already has proven patterns for connection management, config persistence, and plugin lifecycle. The OpenDTU plugin should follow the SolarEdge plugin as a reference implementation, adapting HTTP REST for Modbus TCP.

## Common Pitfalls

### Pitfall 1: OpenDTU JSON Field Paths Differ by Firmware Version
**What goes wrong:** OpenDTU API response structure has changed across firmware versions (e.g., 2024-01-30 restructured livedata/status). The field path `inverters[].AC.0.Power.v` may not exist on older firmware.
**Why it happens:** No versioned API contract.
**How to avoid:** Use defensive `.get()` chains with fallback values. Check firmware version via `/api/system/status` on first connect and log a warning if outside tested range.
**Warning signs:** KeyError or None values when parsing inverter data.

### Pitfall 2: SunSpec Register Synthesis Scale Factor Mismatch
**What goes wrong:** The OpenDTU plugin synthesizes SunSpec uint16 registers from JSON float values. If the scale factors used for encoding do not match what `DashboardCollector._decode_all()` expects, decoded values are wrong by orders of magnitude.
**Why it happens:** The collector reads scale factor registers (e.g., 40084 for AC Power SF) and uses them to decode adjacent value registers. The plugin must write consistent SF + value pairs.
**How to avoid:** Use fixed, known scale factors (e.g., SF=0 for power in watts, SF=-1 for current in 0.1A). Write both the value register AND the scale factor register in every PollResult. Validate: `decoded_value == original_json_value +/- 1W`.
**Warning signs:** Dashboard shows power values 10x or 100x off from what OpenDTU web UI shows.

### Pitfall 3: shared_ctx Migration Breaks WebSocket Broadcast
**What goes wrong:** The `_poll_loop` in `proxy.py` broadcasts snapshots via `shared_ctx["webapp"]`. Changing to AppContext without updating the broadcast path silently breaks live updates.
**Why it happens:** The broadcast import is lazy (`from venus_os_fronius_proxy.webapp import broadcast_to_clients`) and uses `shared_ctx["webapp"]` for the aiohttp app reference.
**How to avoid:** Grep all `shared_ctx` references before starting migration. There are currently 15+ keys accessed across 5 files. Create a checklist and verify each.
**Warning signs:** WebSocket clients stop receiving updates after the refactor.

### Pitfall 4: Gateway Session Not Closed on Shutdown
**What goes wrong:** `aiohttp.ClientSession` must be explicitly closed. If the OpenDTU plugin's session is not closed during shutdown, Python emits "Unclosed client session" warnings and TCP connections leak.
**Why it happens:** `close()` is async and easy to miss in error paths.
**How to avoid:** Always close the session in `close()` method. The SolarEdge plugin's `close()` pattern is the reference.
**Warning signs:** "Unclosed client session" warning in logs on shutdown.

### Pitfall 5: DATA-03 Contradicts CONTEXT.md
**What goes wrong:** Requirement DATA-03 says "Bestehende v3.1 Configs werden automatisch migriert (type: solaredge als Default)". But CONTEXT.md explicitly locks "KEINE Migration von v3.1 Config -- frische Config, alles neu anlernen".
**Why it happens:** Requirements were written before the context discussion locked the no-migration decision.
**How to avoid:** Follow CONTEXT.md (it overrides requirements per GSD protocol). Mark DATA-03 as N/A or update REQUIREMENTS.md. The fresh config approach means the existing `inverter:` -> `inverters:` migration code in `load_config()` can be removed.
**Warning signs:** Implementing migration when none is wanted wastes effort and adds code paths to test.

## Code Examples

### OpenDTU API Response Parsing (verified from official docs)
```python
# Source: https://www.opendtu.solar/firmware/web_api/
# GET /api/livedata/status response structure:
# {
#   "inverters": [
#     {
#       "serial": "112183818450",
#       "name": "Spielturm",
#       "data_age": 4,
#       "reachable": true,
#       "producing": true,
#       "limit_relative": 100.0,
#       "limit_absolute": 400.0,
#       "AC": {
#         "0": {
#           "Power": {"v": 285.3, "u": "W", "d": 1},
#           "Voltage": {"v": 230.1, "u": "V", "d": 1},
#           "Current": {"v": 1.24, "u": "A", "d": 2},
#           "Frequency": {"v": 50.01, "u": "Hz", "d": 2}
#         }
#       },
#       "DC": {
#         "0": {
#           "Power": {"v": 145.2, "u": "W", "d": 1},
#           "Voltage": {"v": 32.1, "u": "V", "d": 1},
#           "YieldTotal": {"v": 1234.5, "u": "kWh", "d": 3},
#           "YieldDay": {"v": 1.23, "u": "kWh", "d": 3}
#         },
#         "1": { ... }  # second DC string (HM-600 has 2)
#       },
#       "INV": {
#         "0": {
#           "Temperature": {"v": 35.2, "u": "\u00b0C", "d": 1}
#         }
#       }
#     }
#   ],
#   "total": { ... },
#   "hints": { "time_sync": false, "radio_problem": false, "default_password": true }
# }
```

### SunSpec Model 103 Register Encoding from Physical Values
```python
# Source: sunspec_models.py register layout + dashboard.py DECODE_MAP
def _encode_model_103(
    self,
    ac_power_w: float,
    ac_voltage_v: float,
    ac_current_a: float,
    ac_freq_hz: float,
    dc_power_w: float,
    dc_voltage_v: float,
    dc_current_a: float,
    temperature_c: float,
    energy_total_wh: int,
    yield_day_wh: int,
    status_code: int,
) -> list[int]:
    """Encode physical values into 52 uint16 SunSpec Model 103 registers."""
    regs = [0] * 52
    regs[0] = 103   # DID
    regs[1] = 50    # Length

    # Use SF=-2 for current (0.01A resolution)
    # Use SF=0 for power (1W resolution)
    # Use SF=-1 for voltage (0.1V resolution)
    # Use SF=-2 for frequency (0.01Hz resolution)

    # AC Current (offset 2-6)
    regs[2] = int(round(ac_current_a * 100))  # Total AC current, SF=-2
    regs[3] = int(round(ac_current_a * 100))  # Phase A (single-phase micro-inverter)
    regs[4] = 0  # Phase B (not applicable)
    regs[5] = 0  # Phase C (not applicable)
    regs[6] = _int16_as_uint16(-2)  # AC Current SF

    # AC Voltage (offset 7-13)
    regs[10] = int(round(ac_voltage_v * 10))  # AC Voltage AN, SF=-1
    regs[13] = _int16_as_uint16(-1)  # AC Voltage SF

    # AC Power (offset 14-15)
    regs[14] = int(round(ac_power_w)) & 0xFFFF  # AC Power, SF=0
    regs[15] = 0  # AC Power SF

    # AC Frequency (offset 16-17)
    regs[16] = int(round(ac_freq_hz * 100))  # Frequency, SF=-2
    regs[17] = _int16_as_uint16(-2)  # Frequency SF

    # Energy (offset 24-26): acc32 + SF
    regs[24] = (energy_total_wh >> 16) & 0xFFFF  # High word
    regs[25] = energy_total_wh & 0xFFFF           # Low word
    regs[26] = 0  # Energy SF (already in Wh)

    # DC (offset 27-32)
    regs[27] = int(round(dc_current_a * 100))     # DC Current, SF=-2
    regs[28] = _int16_as_uint16(-2)                # DC Current SF
    regs[29] = int(round(dc_voltage_v * 10))       # DC Voltage, SF=-1
    regs[30] = _int16_as_uint16(-1)                # DC Voltage SF
    regs[31] = int(round(dc_power_w))              # DC Power, SF=0
    regs[32] = 0                                    # DC Power SF

    # Temperature (offset 33-37)
    regs[33] = int(round(temperature_c * 10))  # Cab temp, SF=-1
    regs[37] = _int16_as_uint16(-1)            # Temp SF

    # Status (offset 38)
    regs[38] = status_code  # 4=MPPT, 2=SLEEPING, etc.

    return regs
```

**IMPORTANT NOTE on register offsets:** The offsets above are relative to the Model 103 DID register at index 0 of the returned list. The DECODE_MAP in `dashboard.py` uses absolute addresses (40071 = offset 2 of Model 103). The encoding must be verified against the exact DECODE_MAP offsets. The key mapping is:

| DECODE_MAP field | Absolute addr | Model 103 offset (addr - 40069) |
|------------------|---------------|--------------------------------|
| ac_current | 40071 | 2 |
| ac_current_l1 | 40072 | 3 |
| ac_current_sf | 40075 | 6 |
| ac_voltage_an | 40079 | 10 |
| ac_voltage_sf | 40082 | 13 |
| ac_power | 40083 | 14 |
| ac_power_sf | 40084 | 15 |
| ac_frequency | 40085 | 16 |
| ac_frequency_sf | 40086 | 17 |
| ac_energy (uint32) | 40093-40094 | 24-25 |
| ac_energy_sf | 40095 | 26 |
| dc_current | 40096 | 27 |
| dc_current_sf | 40097 | 28 |
| dc_voltage | 40098 | 29 |
| dc_voltage_sf | 40099 | 30 |
| dc_power | 40100 | 31 |
| dc_power_sf | 40101 | 32 |
| temperature_cab | 40102 | 33 |
| temperature_sf | 40106 | 37 |
| status | 40107 | 38 |
| status_vendor | 40108 | 39 |

### OpenDTU Power Limit POST (verified from official docs)
```python
# Source: https://www.opendtu.solar/firmware/web_api/
# POST /api/limit/config
# Content-Type: application/json
# Authorization: Basic admin:openDTU42
# Body: {"serial": "112183818450", "limit_type": 1, "limit_value": 50}
# limit_type: 0 = absolute watts, 1 = relative percentage
```

### OpenDTU Limit Status Check
```python
# Source: https://www.opendtu.solar/firmware/web_api/
# GET /api/limit/status
# Response: {"112183818450": {"limit_relative": 50.0, "max_power": 400.0, "limit_set_status": "Ok"}}
# limit_set_status: "Ok" (applied) or "Pending" (waiting for inverter)
```

### AppContext Migration Pattern
```python
# Source: existing __main__.py shared_ctx usage analysis
# Current pattern (5 files):
#   shared_ctx["cache"] = cache
#   shared_ctx["conn_mgr"] = conn_mgr
#   shared_ctx["control_state"] = control_state
#   shared_ctx["poll_counter"] = poll_counter
#   shared_ctx["last_se_poll"] = None
#   shared_ctx["dashboard_collector"] = DashboardCollector()
#   shared_ctx["webapp"] = runner.app
#   shared_ctx["venus_task"] = venus_task
#   shared_ctx["venus_mqtt_connected"] = False
#   shared_ctx["venus_os_detected"] = False
#   shared_ctx["venus_os_detected_ts"] = time.time()
#   shared_ctx["venus_os_client_ip"] = ""
#   shared_ctx["_last_modbus_client_ip"] = ""
#   shared_ctx["polling_paused"] = bool
#   shared_ctx["override_log"] = OverrideLog()

# Migration: each key becomes a typed field on AppContext
# All dict access patterns must be found and replaced
```

### Existing shared_ctx Consumers (exhaustive list)

| File | Keys Accessed | Access Pattern |
|------|--------------|----------------|
| `__main__.py` | cache, conn_mgr, control_state, poll_counter, dashboard_collector, webapp, venus_task, venus_mqtt_connected | Write (setup) |
| `proxy.py` _poll_loop | polling_paused, last_se_poll, dashboard_collector, webapp, control_state | Read/Write |
| `proxy.py` StalenessAwareSlaveContext | venus_os_detected, venus_os_detected_ts, venus_os_client_ip, _last_modbus_client_ip, override_log | Read/Write |
| `proxy.py` run_proxy | cache, conn_mgr, control_state, poll_counter, last_se_poll | Write (populate) |
| `webapp.py` | dashboard_collector, cache, conn_mgr, control_state, config, config_path, plugin, poll_counter, last_se_poll, override_log, venus_mqtt_connected, venus_os_detected, venus_os_client_ip | Read |
| `dashboard.py` | last_se_poll, control_state, venus_mqtt_connected, venus_os_detected, venus_os_client_ip, override_log | Read |
| `venus_reader.py` | venus_mqtt_connected, control_state, dashboard_collector, webapp, override_log | Read/Write |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single inverter: dict | Multi-device: type: field | Phase 21 | Config supports N devices of different types |
| shared_ctx: dict | AppContext: dataclass | Phase 21 | Type safety, IDE autocomplete, no KeyError |
| SolarEdge only | SolarEdge + OpenDTU plugins | Phase 21 | Two inverter brands supported |
| Global poll counter | Per-device DeviceState | Phase 21 | Each device tracks its own poll stats |

**Deprecated/outdated:**
- `inverter:` (singular) config key: already migrated to `inverters:` in v3.1, will be fully removed (no backward compat)
- `get_active_inverter()`: returns single entry; will need replacement with type-aware device lookup
- `InverterConfig` alias: backward compat alias for `InverterEntry`, can be removed

## Open Questions

1. **OpenDTU YieldTotal units: kWh or Wh?**
   - What we know: OpenDTU API returns `YieldTotal` with `"u": "kWh"` and `"d": 3` (3 decimal places). SunSpec Model 103 `AC_Energy` is in Wh as acc32.
   - What's unclear: Whether the decimal value is precise enough (e.g., 1234.567 kWh = 1234567 Wh) or if there is rounding.
   - Recommendation: Convert kWh to Wh (* 1000) and round to integer. Validate against OpenDTU web UI display.

2. **OpenDTU DC channel count varies by Hoymiles model**
   - What we know: HM-400 has 1 DC input, HM-600 has 2, HM-800 has 2, HMS-2000 has 4. The JSON response has `DC.0`, `DC.1`, etc.
   - What's unclear: How to map N DC channels to SunSpec Model 103 which has only 1 DC current/voltage/power set.
   - Recommendation: Sum DC power across all channels. For DC voltage, use weighted average by power. For DC current, sum.

3. **Model 120 WRtg for Hoymiles: dynamic or hardcoded?**
   - What we know: `limit_absolute` from `/api/limit/status` gives `max_power` per serial. This is the rated power.
   - What's unclear: Whether max_power changes if the user reconfigures the inverter limit in OpenDTU.
   - Recommendation: Read `max_power` from `/api/limit/status` on connect and use for Model 120 WRtg. Refresh periodically (every 60s).

4. **DATA-03 conflict with CONTEXT.md**
   - What we know: Requirement says "migrate v3.1 configs". CONTEXT.md says "no migration, fresh config".
   - Recommendation: Follow CONTEXT.md. Update REQUIREMENTS.md to mark DATA-03 as N/A or changed to "fresh config, no migration".

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23+ |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python3 -m pytest tests/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | InverterEntry with type field, name field, GatewayConfig parsing | unit | `python3 -m pytest tests/test_config.py -x` | Exists (needs extension) |
| DATA-01 | load_config parses gateways section | unit | `python3 -m pytest tests/test_config.py::test_load_config_gateways -x` | Wave 0 |
| DATA-01 | save_config roundtrips new fields | unit | `python3 -m pytest tests/test_config_save.py -x` | Exists (needs extension) |
| DATA-02 | AppContext dataclass fields and defaults | unit | `python3 -m pytest tests/test_context.py::test_app_context_defaults -x` | Wave 0 |
| DATA-02 | DeviceState creation and access | unit | `python3 -m pytest tests/test_context.py::test_device_state -x` | Wave 0 |
| DATA-03 | N/A (no migration per CONTEXT.md) | N/A | N/A | N/A |
| DTU-01 | OpenDTU plugin poll returns valid PollResult from JSON | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_poll_success -x` | Wave 0 |
| DTU-01 | JSON-to-SunSpec register encoding matches DECODE_MAP | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_register_encoding -x` | Wave 0 |
| DTU-02 | Plugin filters by serial in multi-inverter response | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_serial_filter -x` | Wave 0 |
| DTU-03 | write_power_limit POSTs correct payload | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_write_limit -x` | Wave 0 |
| DTU-04 | Plugin implements all InverterPlugin ABC methods | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_abc_compliance -x` | Wave 0 |
| DTU-05 | Dead-time guard suppresses rapid re-sends | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_dead_time_guard -x` | Wave 0 |
| DTU-05 | Limit status polling confirms applied vs pending | unit | `python3 -m pytest tests/test_opendtu_plugin.py::test_limit_status_check -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/ -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_context.py` -- covers DATA-02 (AppContext, DeviceState)
- [ ] `tests/test_opendtu_plugin.py` -- covers DTU-01 through DTU-05
- [ ] Extension of `tests/test_config.py` -- new type field, name field, gateways section
- [ ] Extension of `tests/test_config_save.py` -- roundtrip with new fields

## Sources

### Primary (HIGH confidence)
- Direct code analysis: `plugin.py`, `plugins/solaredge.py`, `config.py`, `__main__.py`, `proxy.py`, `dashboard.py`, `webapp.py`, `connection.py`, `sunspec_models.py`, `venus_reader.py`
- [OpenDTU Web API documentation](https://www.opendtu.solar/firmware/web_api/) -- REST endpoints, JSON response structure, limit_type values, Basic Auth
- Existing test suite: 20 test files in `tests/` with pytest + pytest-asyncio

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` -- target architecture, component design, data flow
- `.planning/research/STACK.md` -- zero new deps confirmed, aiohttp client patterns
- `.planning/research/PITFALLS.md` -- 16 pitfalls catalogued with prevention strategies
- [OpenDTU GitHub Issue #571](https://github.com/tbnobody/OpenDTU/issues/571) -- 25-90 second power limit latency

### Tertiary (LOW confidence)
- OpenDTU firmware version compatibility ranges -- exact version at 192.168.3.98 needs validation during implementation
- Dead-time value (30s) -- estimated from GitHub issues, should be validated on real hardware

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all APIs verified in installed packages
- Architecture: HIGH -- based on direct analysis of all source files and locked CONTEXT.md decisions
- Config model: HIGH -- user decisions are explicit and detailed in CONTEXT.md
- OpenDTU plugin: HIGH -- API docs verified against official site, SolarEdge plugin provides clear reference pattern
- Pitfalls: HIGH -- grounded in specific code paths and official documentation

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable domain, well-documented APIs)
