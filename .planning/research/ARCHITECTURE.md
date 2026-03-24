# Architecture Patterns

**Domain:** Shelly Plugin Integration into PV-Inverter-Proxy
**Researched:** 2026-03-24

## Recommended Architecture

### Design Principle: Follow the OpenDTU Pattern

The Shelly plugin integrates identically to how OpenDTU was added in v4.0. The existing architecture already anticipates heterogeneous device types through the `InverterPlugin` ABC, `plugin_factory` dispatch, device-centric UI, and aggregation layer. Shelly is the third plugin, not a special case.

### High-Level Integration

```
                          +-----------------+
                          |  plugin_factory  |  (dispatch by entry.type)
                          +--------+--------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     SolarEdgePlugin       OpenDTUPlugin         ShellyPlugin
     (Modbus TCP)          (REST API)            (REST API)
              |                    |                    |
              v                    v                    v
         PollResult           PollResult           PollResult
    (common + inverter     (common + inverter   (common + inverter
      registers)              registers)           registers)
              |                    |                    |
              +--------------------+--------------------+
                                   |
                          +--------v--------+
                          | DeviceRegistry   |
                          | (per-device poll  |
                          |  loop + state)   |
                          +--------+--------+
                                   |
                          +--------v--------+
                          | AggregationLayer |
                          | (decode -> sum   |
                          |  -> re-encode)   |
                          +--------+--------+
                                   |
                          +--------v--------+
                          |  RegisterCache   |
                          | (Venus OS reads) |
                          +-----------------+
```

### Component Boundaries

| Component | Responsibility | New/Modified | Communicates With |
|-----------|---------------|-------------|-------------------|
| `ShellyPlugin` | Poll Shelly REST API, translate to SunSpec registers, switch on/off | **NEW** | DeviceRegistry, aiohttp |
| `ShellyProfile` (ABC) | Abstract API differences between Gen1/Gen2/Gen3 | **NEW** | ShellyPlugin |
| `ShellyGen1Profile` | Gen1 HTTP endpoints (`/status`, `/relay/0?turn=on`) | **NEW** | ShellyProfile |
| `ShellyGen2Profile` | Gen2/Gen3 RPC endpoints (`/rpc/Switch.GetStatus`, `/rpc/Switch.Set`) | **NEW** | ShellyProfile |
| `detect_shelly_gen()` | Hit `/shelly` then `/rpc/Shelly.GetDeviceInfo` to identify generation | **NEW** | Webapp (add-device flow) |
| `plugin_factory` | Add `elif entry.type == "shelly"` branch | **MODIFY** (3 lines) | ShellyPlugin |
| `InverterEntry` | Add `shelly_gen` field (1/2/3, default 0 = auto-detect) | **MODIFY** (1 field) | Config, ShellyPlugin |
| `AggregationLayer` | **NO CHANGES** -- already generic over any PollResult | Unchanged | DeviceRegistry |
| `PowerLimitDistributor` | **NO CHANGES** -- calls `write_power_limit()` which Shelly implements as on/off | Unchanged | ShellyPlugin |
| `DashboardCollector` | **NO CHANGES** -- decodes SunSpec registers generically | Unchanged | DeviceRegistry |
| `webapp.py` | Add Shelly type card in add-device, Shelly config fields, on/off toggle in dashboard | **MODIFY** | ShellyPlugin, frontend |
| `app.js` | Add Shelly type in picker, on/off control instead of slider, Shelly-specific config form | **MODIFY** | webapp.py API |

### Data Flow

**Polling (every N seconds):**
```
ShellyPlugin.poll()
  -> HTTP GET to Shelly device (profile-dependent URL)
  -> Parse JSON: power, voltage, current, energy, temperature, relay state
  -> Encode into SunSpec Model 103 registers (same as OpenDTU pattern)
  -> Return PollResult(common_registers, inverter_registers, success=True)
  -> DeviceRegistry stores in DeviceState.last_poll_data
  -> AggregationLayer.recalculate() sums into virtual inverter
  -> RegisterCache updated, Venus OS reads via Modbus TCP
```

**Control (on/off):**
```
Venus OS writes WMaxLimPct via Modbus
  -> PowerLimitDistributor.distribute()
  -> ShellyPlugin.write_power_limit(enable, limit_pct)
  -> If limit_pct < threshold (e.g., 5%): switch OFF
  -> If limit_pct >= threshold or enable=False (100%): switch ON
  -> HTTP command to Shelly (profile-dependent)
```

## Profile System Design (Gen1 vs Gen2/Gen3)

The key architectural decision: **profile as a strategy object inside ShellyPlugin, not as separate plugin subclasses**.

### Why Strategy, Not Inheritance

Separate `ShellyGen1Plugin` and `ShellyGen2Plugin` classes would duplicate all the SunSpec encoding, common register building, and status mapping. The only difference between generations is the HTTP endpoints and JSON response structure. A strategy pattern isolates exactly the varying part.

### Class Hierarchy

```python
# shelly_profiles.py (new file in plugins/)

@dataclass
class ShellyPollData:
    """Normalized poll result from any Shelly generation."""
    power_w: float
    voltage_v: float
    current_a: float
    frequency_hz: float
    energy_total_wh: float
    temperature_c: float
    relay_on: bool

class ShellyProfile(ABC):
    """Strategy for generation-specific Shelly API calls."""

    @abstractmethod
    async def poll_status(self, session: aiohttp.ClientSession, host: str) -> ShellyPollData:
        """Poll device status and return normalized data."""

    @abstractmethod
    async def switch(self, session: aiohttp.ClientSession, host: str, on: bool) -> bool:
        """Switch relay on/off. Returns True on success."""

    @abstractmethod
    async def get_device_info(self, session: aiohttp.ClientSession, host: str) -> dict:
        """Get device info (model, firmware, mac)."""


class ShellyGen1Profile(ShellyProfile):
    """Gen1 devices: /status, /relay/0?turn=on|off"""

    async def poll_status(self, session, host):
        # GET http://{host}/status
        # Parse: .relays[0].ison, .meters[0].power, .voltage, .temperature, etc.
        ...

    async def switch(self, session, host, on):
        # GET http://{host}/relay/0?turn=on|off
        ...

    async def get_device_info(self, session, host):
        # GET http://{host}/shelly -> {type, mac, fw}
        ...


class ShellyGen2Profile(ShellyProfile):
    """Gen2/Gen3 devices: /rpc/Switch.GetStatus, /rpc/Switch.Set"""

    async def poll_status(self, session, host):
        # GET http://{host}/rpc/Switch.GetStatus?id=0
        # Parse: .output, .apower, .voltage, .current, .freq, .aenergy.total, .temperature.tC
        ...

    async def switch(self, session, host, on):
        # GET http://{host}/rpc/Switch.Set?id=0&on=true|false
        ...

    async def get_device_info(self, session, host):
        # GET http://{host}/rpc/Shelly.GetDeviceInfo
        # -> {id, mac, model, gen, fw_id, ver, app}
        ...


# plugins/shelly.py

class ShellyPlugin(InverterPlugin):
    """Shelly smart device plugin. Delegates API calls to a ShellyProfile."""

    def __init__(self, host: str, profile: ShellyProfile, name: str = ""):
        self._host = host
        self._profile = profile  # Gen1 or Gen2 strategy
        self._name = name
        self._session: aiohttp.ClientSession | None = None
        self._relay_on: bool = True
        self._max_power_w: int = 3500  # Default, updated from config/rated_power

    async def connect(self) -> None:
        self._session = aiohttp.ClientSession()

    async def poll(self) -> PollResult:
        data = await self._profile.poll_status(self._session, self._host)
        self._relay_on = data.relay_on
        inverter_regs = self._encode_model_103(data)
        common_regs = self._build_common_registers()
        return PollResult(common_regs, inverter_regs, success=True)

    async def write_power_limit(self, enable, limit_pct, *, force=False):
        # Shelly has no percentage control -- map to on/off
        should_be_on = (not enable) or (limit_pct > 5.0)
        if should_be_on != self._relay_on:
            ok = await self._profile.switch(self._session, self._host, should_be_on)
            if ok:
                self._relay_on = should_be_on
            return WriteResult(success=ok)
        return WriteResult(success=True)  # Already in desired state

    # _encode_model_103, _build_common_registers, get_model_120_registers,
    # get_static_common_overrides, reconfigure, close
    # ... follow exact OpenDTU pattern
```

### Auto-Detection Flow

```python
async def detect_shelly_gen(host: str) -> int:
    """Detect Shelly generation by probing endpoints.

    Returns 1, 2, or 3. Raises on failure.
    Strategy:
      1. Try GET /rpc/Shelly.GetDeviceInfo -> if gen field exists, return it (2 or 3)
      2. Try GET /shelly -> if response has 'type' but no 'gen', it's Gen1
      3. Raise ValueError if neither works
    """
```

This function is called in the add-device webapp flow (like OpenDTU's test-auth) and stores the result in `InverterEntry.shelly_gen`.

## Integration Points: Method-by-Method Analysis

### InverterPlugin ABC Implementation

| Method | SolarEdge | OpenDTU | Shelly | Notes |
|--------|-----------|---------|--------|-------|
| `connect()` | Modbus TCP client | aiohttp session | aiohttp session | Same pattern as OpenDTU |
| `poll()` | Modbus register read | REST JSON -> SunSpec | REST JSON -> SunSpec | Same pattern as OpenDTU |
| `get_static_common_overrides()` | "Fronius" manufacturer | "Hoymiles" manufacturer | "Shelly" manufacturer | Trivial |
| `get_model_120_registers()` | 30kW nameplate | Dynamic from API | From config rated_power | Use InverterEntry.rated_power |
| `write_power_limit()` | EDPC registers (%) | OpenDTU limit API (%) | **On/Off only** | Map % to binary -- see below |
| `reconfigure()` | Close + update host/port | Close session | Close session | Same as OpenDTU |
| `close()` | Close Modbus client | Close aiohttp | Close aiohttp | Same as OpenDTU |

### write_power_limit: The Key Difference

Shelly devices are switches, not variable-power inverters. They cannot accept a percentage limit. The mapping:

```
write_power_limit(enable=True, limit_pct=X):
  - X > 5%  -> relay ON  (device produces whatever its PV panel generates)
  - X <= 5% -> relay OFF (device disconnected from grid)

write_power_limit(enable=False, limit_pct=any):
  - relay ON (disable limiting = full power = on)
```

The 5% threshold prevents oscillation. A Shelly with a 400W micro-inverter behind it either produces ~400W or 0W. The PowerLimitDistributor already handles this correctly because:
1. It assigns per-device percentage based on rated_power
2. Shelly's `write_power_limit` maps that percentage to on/off
3. The waterfall algorithm naturally throttles low-priority devices to 0% before touching higher-priority ones

### Aggregation Layer: Zero Changes

The AggregationLayer is already fully generic:
1. It reads `DeviceState.last_poll_data["inverter_registers"]` -- any plugin providing valid Model 103 registers works
2. `decode_model_103_to_physical()` decodes any valid uint16 register array
3. Summation logic is field-level (power, current, energy sums; voltage, frequency averages)
4. A Shelly producing 380W just adds 380W to the total like any other device

When the Shelly relay is OFF, its `poll()` returns 0W in all power fields, and status=2 (SLEEPING). The aggregation handles this naturally -- zero values do not corrupt sums.

### Config Changes

```python
# InverterEntry additions:
@dataclass
class InverterEntry:
    ...
    type: str = "solaredge"       # Now also "shelly"
    shelly_gen: int = 0           # 0=auto-detect, 1=Gen1, 2=Gen2, 3=Gen3
```

Gen2 and Gen3 share the same API (Gen3 uses the same RPC protocol as Gen2, just newer hardware). So `ShellyGen2Profile` handles both gen=2 and gen=3.

### Webapp/Frontend Changes

**Add-Device Modal:**
- Third type card: "Shelly Device"
- Form: Host IP only (no port, no unit_id, no auth -- Shelly local API is unauthenticated by default)
- Discover button: `GET /api/shelly/detect?host=X` -> returns gen, model, mac
- Auto-fills name from model, sets shelly_gen

**Device Config Page:**
- Hide Port/Unit ID fields for Shelly (not applicable)
- Show Shelly Generation (readonly, detected)
- Show relay state indicator

**Device Dashboard:**
- Power gauge: same as other devices (SunSpec registers decoded)
- AC values: same (voltage, current, frequency from Shelly)
- Power control: **On/Off toggle instead of percentage slider**
  - Frontend checks `device_type === 'shelly'` and renders toggle
  - Toggle calls existing `/api/devices/{id}/power-limit` with limit_pct=100 (on) or limit_pct=0 (off)
- Connection card: same pattern
- No DC values (Shelly measures AC only -- DC fields stay 0)

## Patterns to Follow

### Pattern 1: Profile-Based API Abstraction
**What:** Isolate generation-specific HTTP calls behind a common interface
**When:** Device has multiple API generations with different endpoints but same data
**Example:** See ShellyProfile class hierarchy above

### Pattern 2: Reuse SunSpec Encoding
**What:** Translate any power data source into Model 103 registers
**When:** Adding any new device type to the proxy
**Why:** AggregationLayer, DashboardCollector, and RegisterCache all consume SunSpec registers. Translating at the plugin boundary means zero changes downstream.

### Pattern 3: Binary Control Mapping
**What:** Map percentage-based control to on/off with hysteresis threshold
**When:** Device only supports binary control but must participate in the waterfall distribution
**Why:** The Distributor sends percentages. The plugin is responsible for interpreting them. A threshold with deadband prevents rapid toggling.

### Pattern 4: Auto-Detection at Add Time
**What:** Probe device capabilities once during add-device flow, store result in config
**When:** Device type has sub-variants that affect runtime behavior
**Why:** Avoids probing on every connect/poll. Config persists the detection result. Manual override possible via shelly_gen field.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate InverterPlugin Subclasses per Generation
**What:** Creating ShellyGen1Plugin and ShellyGen2Plugin as separate InverterPlugin implementations
**Why bad:** 90% code duplication (SunSpec encoding, common registers, status mapping, aiohttp session management). Two entries in plugin_factory. Config needs different type values ("shelly_gen1" vs "shelly_gen2").
**Instead:** Single ShellyPlugin with internal ShellyProfile strategy. One type="shelly" in config.

### Anti-Pattern 2: Modifying AggregationLayer for Shelly
**What:** Adding Shelly-specific logic to the aggregation (e.g., special handling for binary devices)
**Why bad:** Aggregation is already generic. Shelly provides the same PollResult format. Adding conditionals creates maintenance burden for every future plugin.
**Instead:** Translate to SunSpec at the plugin boundary. Aggregation stays generic.

### Anti-Pattern 3: Custom WebSocket Message Types for Shelly
**What:** Adding new WS message types for relay state, Shelly-specific data
**Why bad:** Existing architecture uses snapshot-diff on the client side. Adding message types complicates the protocol.
**Instead:** Include `relay_on` in the existing snapshot dict (as `device_type`-specific field). Frontend reads it when `device_type === 'shelly'`.

### Anti-Pattern 4: Polling /shelly for Generation on Every Connect
**What:** Re-detecting Shelly generation on every connect/reconnect
**Why bad:** Unnecessary network traffic, slower reconnects, generation never changes
**Instead:** Detect once at add-device time, store in InverterEntry.shelly_gen, use stored value at runtime

## File Organization

```
src/pv_inverter_proxy/
  plugins/
    __init__.py           # MODIFY: add "shelly" branch to plugin_factory
    solaredge.py          # unchanged
    opendtu.py            # unchanged
    shelly.py             # NEW: ShellyPlugin class (~250 LOC)
    shelly_profiles.py    # NEW: ShellyProfile ABC + Gen1Profile + Gen2Profile (~200 LOC)
  config.py               # MODIFY: add shelly_gen to InverterEntry
  webapp.py               # MODIFY: add /api/shelly/detect endpoint, Shelly in add-device
  static/
    app.js                # MODIFY: Shelly type card, on/off toggle, config form
    style.css             # MODIFY: minimal (on/off toggle styling, reuse ve-toggle)
    index.html            # unchanged
```

Estimated new code: ~500 LOC Python, ~150 LOC JavaScript
Estimated modified code: ~50 LOC Python, ~80 LOC JavaScript

## Build Order (Dependency-Driven)

```
Phase 1: ShellyProfile + Gen1/Gen2 profiles (shelly_profiles.py)
  -> No dependencies on existing code, fully testable in isolation
  -> Unit tests with mocked HTTP responses

Phase 2: ShellyPlugin (shelly.py)
  -> Depends on Phase 1 (profiles) + existing plugin.py ABC
  -> Implements all InverterPlugin methods
  -> Unit tests with mocked profile

Phase 3: Config + plugin_factory integration
  -> Add shelly_gen to InverterEntry
  -> Add "shelly" to plugin_factory
  -> DeviceRegistry starts Shelly devices (zero changes to registry itself)

Phase 4: Auto-detection endpoint + add-device UI
  -> detect_shelly_gen() function
  -> /api/shelly/detect webapp endpoint
  -> Frontend: third type card, Shelly form, discover flow

Phase 5: Dashboard UI for Shelly
  -> On/Off toggle instead of power slider
  -> Hide DC section for Shelly devices
  -> Relay state indicator in connection card

Phase 6: End-to-end testing with real Shelly device
  -> Deploy to LXC, test with physical Shelly
  -> Verify aggregation includes Shelly power
  -> Verify Venus OS sees combined output
```

## Scalability Considerations

| Concern | 1 Shelly | 10 Shellies | 50 Shellies |
|---------|----------|-------------|-------------|
| Poll interval | 5s default (same as OpenDTU) | 5s each, staggered by DeviceRegistry | May need 10s interval |
| HTTP sessions | 1 aiohttp session per device | 10 sessions, fine | Consider session pooling |
| Aggregation | Instant | ~1ms per recalculate | Still fast (pure math) |
| Memory | ~2KB per device state | ~20KB | ~100KB, negligible |
| Waterfall distribution | Trivial | All Shellies at same TO = equal split | Group by TO, split budget |

## Shelly API Reference (for Implementation)

### Gen1 Endpoints

| Action | Method | URL | Response Key Fields |
|--------|--------|-----|---------------------|
| Device info | GET | `/shelly` | `type`, `mac`, `fw` |
| Full status | GET | `/status` | `relays[0].ison`, `meters[0].power`, `voltage`, `temperature` |
| Relay status | GET | `/relay/0` | `ison`, `power`, `overpower` |
| Switch on | GET | `/relay/0?turn=on` | `ison: true` |
| Switch off | GET | `/relay/0?turn=off` | `ison: false` |

### Gen2/Gen3 Endpoints

| Action | Method | URL | Response Key Fields |
|--------|--------|-----|---------------------|
| Device info | GET | `/rpc/Shelly.GetDeviceInfo` | `gen`, `model`, `mac`, `ver`, `app` |
| Full status | GET | `/rpc/Shelly.GetStatus` | All components |
| Switch status | GET | `/rpc/Switch.GetStatus?id=0` | `output`, `apower`, `voltage`, `current`, `freq`, `aenergy.total`, `temperature.tC` |
| Switch on | GET | `/rpc/Switch.Set?id=0&on=true` | `was_on` |
| Switch off | GET | `/rpc/Switch.Set?id=0&on=false` | `was_on` |

### Gen2 Switch.GetStatus Response (Complete)

```json
{
  "id": 0,
  "source": "WS_in",
  "output": false,
  "apower": 0,
  "voltage": 225.9,
  "current": 0,
  "freq": 50,
  "aenergy": {"total": 11.679, "by_minute": [0, 0, 0], "minute_ts": 1234567890},
  "ret_aenergy": {"total": 5.817},
  "temperature": {"tC": 53.3, "tF": 127.9}
}
```

## Sources

- [Shelly Gen2 API Documentation](https://shelly-api-docs.shelly.cloud/gen2/) -- HIGH confidence
- [Shelly Gen1 API Reference](https://shelly-api-docs.shelly.cloud/gen1/) -- HIGH confidence
- [Shelly Gen2 Switch Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/) -- HIGH confidence
- [Shelly.GetDeviceInfo RPC](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Shelly/) -- HIGH confidence
- [Shelly Gen1 Compatibility in Gen2](https://shelly-api-docs.shelly.cloud/gen2/0.14/General/gen1Compatibility/) -- MEDIUM confidence
- [Shelly Gen1/Gen2/Gen3/Gen4 Comparison](https://support.shelly.cloud/en/support/solutions/articles/103000316073-comparison-of-shelly-gen1-gen2-gen3-and-gen4-devices) -- MEDIUM confidence
- Existing codebase: `plugin.py`, `plugins/opendtu.py`, `aggregation.py`, `device_registry.py`, `config.py`, `webapp.py`, `app.js` -- HIGH confidence (direct code reading)
