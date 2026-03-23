# Phase 28: Plugin Core & Profiles - Research

**Researched:** 2026-03-24
**Domain:** Shelly smart device REST API integration as InverterPlugin
**Confidence:** HIGH

## Summary

Phase 28 implements the ShellyPlugin -- the third InverterPlugin alongside SolarEdge (Modbus TCP) and OpenDTU (REST API). The plugin polls Shelly devices over their local HTTP/JSON API, auto-detects Gen1 vs Gen2+ generations, extracts power/voltage/current/frequency/energy/temperature data, and encodes it into SunSpec Model 103 registers identical to the OpenDTU pattern. The existing aiohttp library handles all HTTP communication -- zero new dependencies.

The key architectural pattern is a profile-based abstraction: Gen1 and Gen2+ use different HTTP endpoints and JSON response structures, but a ShellyProfile strategy isolates these differences behind a common interface. The ShellyPlugin delegates API calls to the selected profile and handles all SunSpec encoding, common register building, and lifecycle management. Gen3 devices use the identical Gen2 RPC API and require no separate profile.

The energy counter offset tracking (PLUG-06) is the most nuanced requirement: Shelly devices reset their cumulative energy counter on reboot, so the plugin must detect counter resets and maintain an in-memory offset to prevent the aggregated energy total from jumping backward.

**Primary recommendation:** Follow the OpenDTU plugin pattern exactly -- profile-based API abstraction, aiohttp session per device, SunSpec Model 103 encoding at the plugin boundary, PollResult as the sole output contract.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLUG-01 | ShellyPlugin implements InverterPlugin ABC (poll, connect, close, write_power_limit, get_model_120_registers, reconfigure) | All 7 ABC methods mapped -- see "InverterPlugin ABC Implementation" section. OpenDTU plugin is the template. |
| PLUG-02 | Profile system with Gen1 (REST /status, /relay) and Gen2+ (RPC /rpc/Switch.GetStatus, /rpc/Switch.Set) API adapters | ShellyProfile ABC with Gen1Profile and Gen2Profile -- see "Profile System Design" section. Dict-based URL+extractor pattern. |
| PLUG-03 | Auto-detection of Shelly generation via GET /shelly (gen field present = Gen2+, absent = Gen1) | Single-endpoint detection algorithm verified against official docs and evcc implementation -- see "Auto-Detection" section. |
| PLUG-04 | Polling delivers power (W), voltage (V), current (A), frequency (Hz), energy (Wh), temperature (C) | Field mapping documented for both Gen1 and Gen2 JSON responses -- see "Data Field Mapping" section. Gen1 may lack some fields. |
| PLUG-05 | SunSpec Model 103 register encoding from Shelly JSON (identical to OpenDTU) | Register offset map with scale factors documented -- see "SunSpec Model 103 Encoding" section. Same _encode_model_103 pattern as OpenDTU. |
| PLUG-06 | Energy counter offset tracking (Shelly resets on reboot, daily yield must not jump) | Offset tracking algorithm documented -- see "Energy Counter Offset Tracking" section. In-memory only, same limitation as OpenDTU. |
| PLUG-07 | Missing fields handled gracefully (Gen1 has less data, some models lack temperature) | Defensive .get() with defaults, 0.0 for missing values, no crashes -- see "Missing Fields Handling" section. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | >=3.10,<4.0 | HTTP client for Shelly REST API polling and switch control | Already used by OpenDTU plugin -- zero new deps, proven pattern |
| structlog | >=24.0 | Structured logging for poll events, errors, detection | Already used project-wide |

### Supporting

No new libraries needed. All Shelly communication uses existing aiohttp.ClientSession.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw aiohttp | aioshelly (HA library) | Pulls CoAP, Bluetooth, orjson deps -- massive overkill for 2 HTTP GETs per poll. Rejected. |
| HTTP GET polling | WebSocket RPC (Gen2 supports it) | Stateless GET is simpler, proven by OpenDTU pattern. WS adds reconnection complexity for no benefit at 5s poll interval. |
| Profile ABC classes | Simple dict with URL strings | Dict is simpler for URL mapping but cannot encapsulate JSON extraction logic. Profile classes are cleaner for the Gen1 vs Gen2 JSON parsing differences. |

**Installation:**
```bash
# No new packages needed
pip install -e .  # existing command unchanged
```

## Architecture Patterns

### Recommended File Structure
```
src/pv_inverter_proxy/
  plugins/
    __init__.py             # MODIFY: add "shelly" branch to plugin_factory
    shelly.py               # NEW: ShellyPlugin class (~200 LOC)
    shelly_profiles.py      # NEW: ShellyProfile ABC + Gen1Profile + Gen2Profile (~180 LOC)
    opendtu.py              # unchanged
    solaredge.py            # unchanged
  config.py                 # MODIFY: add shelly_gen field to InverterEntry
```

### Pattern 1: Profile-Based API Abstraction (Strategy Pattern)

**What:** Isolate Gen1/Gen2 HTTP endpoint differences behind a common interface. The ShellyPlugin holds a profile reference and delegates all API calls to it.

**When to use:** Device has multiple API generations with different endpoints but identical logical data.

**Example:**
```python
# Source: Codebase analysis + Shelly API docs
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
```

### Pattern 2: SunSpec Register Encoding at Plugin Boundary

**What:** Translate Shelly JSON to SunSpec Model 103 uint16 registers inside the plugin. Downstream components (AggregationLayer, DashboardCollector, RegisterCache) consume only SunSpec registers.

**When to use:** Adding any new device type to the proxy.

**Why:** Zero changes needed in aggregation, dashboard, or Modbus server. The PollResult contract is the integration boundary.

**Example:**
```python
# Source: OpenDTU plugin pattern (plugins/opendtu.py lines 201-263)
def _encode_model_103(self, data: ShellyPollData) -> list[int]:
    """Encode Shelly poll data into 52 uint16 SunSpec Model 103 registers."""
    regs = [0] * 52
    regs[0] = 103   # DID
    regs[1] = 50    # Length

    # AC Current (offset 2-6, SF=-2)
    regs[2] = int(round(data.current_a * 100))
    regs[3] = int(round(data.current_a * 100))  # Phase A (single-phase)
    regs[6] = _int16_as_uint16(-2)

    # AC Voltage AN (offset 10, SF=-1)
    regs[10] = int(round(data.voltage_v * 10))
    regs[13] = _int16_as_uint16(-1)

    # AC Power (offset 14, SF=0)
    regs[14] = int(round(data.power_w)) & 0xFFFF
    regs[15] = 0

    # AC Frequency (offset 16, SF=-2)
    regs[16] = int(round(data.frequency_hz * 100))
    regs[17] = _int16_as_uint16(-2)

    # Energy acc32 (offset 24-25, SF=0)
    energy_wh = int(round(data.energy_total_wh))
    regs[24] = (energy_wh >> 16) & 0xFFFF
    regs[25] = energy_wh & 0xFFFF
    regs[26] = 0

    # DC fields: all zero (Shelly has no DC data)
    # Temperature (offset 33, SF=-1)
    regs[33] = int(round(data.temperature_c * 10))
    regs[37] = _int16_as_uint16(-1)

    # Status: relay ON = 4 (MPPT), OFF = 2 (SLEEPING)
    regs[38] = 4 if data.relay_on else 2

    return regs
```

### Pattern 3: Energy Counter Offset Tracking

**What:** Detect Shelly energy counter resets (device reboot) and maintain a cumulative offset so the reported total never decreases.

**When to use:** Any device with a volatile energy counter.

**Example:**
```python
# Source: Requirement PLUG-06
class ShellyPlugin:
    def __init__(self, ...):
        self._energy_offset_wh: float = 0.0
        self._last_energy_raw_wh: float = 0.0

    def _track_energy(self, raw_energy_wh: float) -> float:
        """Track energy with offset to handle reboot resets."""
        if raw_energy_wh < self._last_energy_raw_wh:
            # Counter reset detected -- accumulate offset
            self._energy_offset_wh += self._last_energy_raw_wh
        self._last_energy_raw_wh = raw_energy_wh
        return raw_energy_wh + self._energy_offset_wh
```

### Pattern 4: Auto-Detection at Connect Time

**What:** Probe the `/shelly` endpoint once during `connect()`, detect Gen1 vs Gen2+, select the correct profile, and cache the result.

**When to use:** Device type has sub-variants affecting runtime API behavior.

**Example:**
```python
# Source: Shelly API docs + evcc reference implementation
async def _detect_generation(self, session: aiohttp.ClientSession) -> str:
    """Detect Shelly generation. Returns "gen1" or "gen2"."""
    async with session.get(
        f"http://{self._host}/shelly",
        timeout=aiohttp.ClientTimeout(total=5)
    ) as resp:
        data = await resp.json()

    gen = data.get("gen", 0)
    if gen >= 2:
        return "gen2"  # Gen2 and Gen3 share identical API
    return "gen1"
```

### Anti-Patterns to Avoid

- **Separate InverterPlugin subclasses per generation:** ShellyGen1Plugin and ShellyGen2Plugin would duplicate 90% of code (SunSpec encoding, common registers, session management). Use strategy pattern instead.
- **Modifying AggregationLayer for Shelly:** Aggregation is already generic over PollResult. Adding Shelly-specific conditionals breaks the abstraction.
- **Re-detecting generation on every connect/reconnect:** Generation never changes. Detect once, store in config.
- **Sending percentage power limits to Shelly:** Shelly has no variable power control. `write_power_limit()` must be a no-op returning success.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client | Custom urllib/requests wrapper | aiohttp.ClientSession | Already in project, async, session reuse, timeout support |
| JSON parsing | Custom field extractors | Profile classes with `.get()` defaults | Clean separation of Gen1 vs Gen2 JSON shapes |
| SunSpec encoding | New encoding format | Copy OpenDTU's `_encode_model_103` pattern | Proven register layout, AggregationLayer expects exact format |
| Connection backoff | Custom retry logic | Existing ConnectionManager | Already handles backoff, night mode, state transitions |
| Device lifecycle | Custom poll loop | Existing DeviceRegistry | Creates asyncio task, manages start/stop/enable/disable |

**Key insight:** The entire device integration infrastructure (DeviceRegistry, ConnectionManager, DashboardCollector, AggregationLayer) is already generic. The ShellyPlugin only needs to implement InverterPlugin ABC and return valid PollResult -- everything downstream works automatically.

## Common Pitfalls

### Pitfall 1: Gen1 Energy Unit Confusion
**What goes wrong:** Gen1 `meters[0].total` may report Watt-minutes on some firmware versions, not Wh. Using the raw value as Wh inflates energy by 60x.
**Why it happens:** Shelly Gen1 firmware evolved over time -- older versions used Watt-minutes, newer use Wh.
**How to avoid:** The total field is in Watt-minutes for Gen1 `/status`. Convert at parse time: `energy_wh = total / 60.0`. For Gen2, `aenergy.total` is already in Wh -- use directly.
**Warning signs:** Energy values 60x too high compared to expected daily yield.

### Pitfall 2: Missing Fields on Gen1 Devices
**What goes wrong:** Gen1 Plug S and 1PM have different field availability. Plug S may lack voltage/current. Some Gen1 models have no temperature sensor. Accessing missing fields crashes the poll.
**Why it happens:** Gen1 JSON structure varies by hardware model.
**How to avoid:** Always use `.get()` with default values: `data.get("temperature", 0.0)`, `data.get("meters", [{}])[0].get("voltage", 0.0)`. Never crash on missing fields -- return 0.0 defaults.
**Warning signs:** KeyError exceptions in poll logs.

### Pitfall 3: Energy Counter Reset on Reboot
**What goes wrong:** Shelly energy counter resets to 0 when the device reboots (power cycle, OTA update). Without offset tracking, aggregated energy total jumps backward, which Venus OS may interpret as negative production.
**Why it happens:** Shelly stores cumulative energy in volatile memory.
**How to avoid:** Implement PLUG-06 offset tracking: detect when `current_energy < last_energy`, accumulate offset, always report `current + offset`.
**Warning signs:** Energy total drops suddenly in dashboard after Shelly reboot.

### Pitfall 4: write_power_limit Must Be No-Op, Not Error
**What goes wrong:** If `write_power_limit()` returns `WriteResult(success=False)`, the PowerLimitDistributor logs errors and retries. But Shelly genuinely cannot accept percentage limits -- returning failure is incorrect.
**Why it happens:** ABC method exists for inverters that support throttling.
**How to avoid:** Return `WriteResult(success=True)` always. Set `throttle_enabled: false` as default for Shelly InverterEntry so the distributor skips it. The no-op prevents error spam.
**Warning signs:** Repeated "power_limit_failed" log messages for Shelly devices.

### Pitfall 5: DC Register Values Must Be Zero, Not "Not Implemented"
**What goes wrong:** Setting DC registers to SunSpec "not implemented" values (0x8000/0xFFFF) would work for the spec but the existing `decode_model_103_to_physical()` treats 0x8000 and 0xFFFF as 0.0 already. The AggregationLayer then includes these 0.0 values in DC averaging, diluting the average.
**Why it happens:** Aggregation divides DC voltage sum by total device count, not just devices with DC data.
**How to avoid:** Set DC register values to 0. This is Phase 32 scope (AGG-02) -- for Phase 28, just use zeros. The aggregation fix is tracked separately.
**Warning signs:** Lower-than-expected DC voltage in aggregated virtual inverter after adding Shelly.

## Data Field Mapping

### Gen1 /status Response Fields
| Shelly Field | Type | Unit | Maps To |
|-------------|------|------|---------|
| `meters[0].power` | float | W | power_w |
| `meters[0].voltage` | float | V | voltage_v (may be absent on basic models) |
| `meters[0].current` | float | A | current_a (may be absent) |
| `meters[0].total` | float | Wm | energy_total_wh (divide by 60) |
| `relays[0].ison` | bool | -- | relay_on |
| `temperature` | float | C | temperature_c (top-level, may be absent) |
| N/A | -- | -- | frequency_hz: default 50.0 (Gen1 does not report frequency) |

### Gen2/Gen3 /rpc/Switch.GetStatus?id=0 Response Fields
| Shelly Field | Type | Unit | Maps To |
|-------------|------|------|---------|
| `apower` | float | W | power_w |
| `voltage` | float | V | voltage_v |
| `current` | float | A | current_a |
| `freq` | float | Hz | frequency_hz |
| `aenergy.total` | float | Wh | energy_total_wh |
| `output` | bool | -- | relay_on |
| `temperature.tC` | float/null | C | temperature_c (may be null) |

## SunSpec Model 103 Register Encoding

Identical register layout to OpenDTU plugin (plugins/opendtu.py lines 201-263):

| Data | Register Offset | Scale Factor | Encoding |
|------|----------------|--------------|----------|
| AC Current | 2 (total), 3 (L1) | SF=-2 at offset 6 | `round(current_a * 100)` |
| AC Voltage AN | 10 | SF=-1 at offset 13 | `round(voltage_v * 10)` |
| AC Power | 14 | SF=0 at offset 15 | `round(power_w) & 0xFFFF` |
| AC Frequency | 16 | SF=-2 at offset 17 | `round(frequency_hz * 100)` |
| AC Energy | 24-25 (acc32) | SF=0 at offset 26 | High/low word split of Wh integer |
| DC Current | 27 | SF=-2 at offset 28 | 0 (no DC data) |
| DC Voltage | 29 | SF=-1 at offset 30 | 0 (no DC data) |
| DC Power | 31 | SF=0 at offset 32 | 0 (no DC data) |
| Temperature | 33 | SF=-1 at offset 37 | `round(temperature_c * 10)` |
| Status | 38 | -- | relay_on ? 4 (MPPT) : 2 (SLEEPING) |

## InverterPlugin ABC Implementation Map

| ABC Method | Shelly Implementation | Notes |
|------------|----------------------|-------|
| `connect()` | Create aiohttp.ClientSession, auto-detect generation via `/shelly`, select profile | Store device info (model, mac) for common registers |
| `poll()` | Delegate to `self._profile.poll_status()`, track energy offset, encode to Model 103 | Return PollResult with common + inverter registers |
| `get_static_common_overrides()` | Manufacturer="Shelly", Model from device info | Same pattern as OpenDTU "Hoymiles" |
| `get_model_120_registers()` | DID=120, Len=26, DERTyp=4 (PV), WRtg from `rated_power` config | Shelly has no self-reported rating |
| `write_power_limit()` | No-op returning `WriteResult(success=True)` | Shelly cannot do percentage limiting |
| `reconfigure()` | Close session, update host | New session on next connect |
| `close()` | Close aiohttp session | Same as OpenDTU |

## Config Changes

Add to InverterEntry dataclass in config.py:

```python
@dataclass
class InverterEntry:
    ...
    type: str = "solaredge"       # New value: "shelly"
    shelly_gen: str = ""          # "gen1" or "gen2" -- auto-detected, persisted
```

Add to plugin_factory in plugins/__init__.py:

```python
elif entry.type == "shelly":
    from pv_inverter_proxy.plugins.shelly import ShellyPlugin
    return ShellyPlugin(
        host=entry.host,
        generation=entry.shelly_gen,
        name=entry.name,
        rated_power=entry.rated_power,
    )
```

Default `throttle_enabled` to `False` for Shelly entries (enforce in config save handler).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_shelly_plugin.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUG-01 | ShellyPlugin isinstance InverterPlugin, all 7 methods exist | unit | `pytest tests/test_shelly_plugin.py::TestABCCompliance -x` | Wave 0 |
| PLUG-02 | Gen1Profile polls /status, Gen2Profile polls /rpc/Switch.GetStatus | unit | `pytest tests/test_shelly_plugin.py::TestProfiles -x` | Wave 0 |
| PLUG-03 | Auto-detection returns "gen1" when no gen field, "gen2" when gen>=2 | unit | `pytest tests/test_shelly_plugin.py::TestAutoDetection -x` | Wave 0 |
| PLUG-04 | Poll returns PollResult with correct power/voltage/current/freq/energy/temp | unit | `pytest tests/test_shelly_plugin.py::TestPollSuccess -x` | Wave 0 |
| PLUG-05 | Register encoding matches OpenDTU pattern (same offsets, SFs) | unit | `pytest tests/test_shelly_plugin.py::TestRegisterEncoding -x` | Wave 0 |
| PLUG-06 | Energy offset tracking survives counter reset | unit | `pytest tests/test_shelly_plugin.py::TestEnergyTracking -x` | Wave 0 |
| PLUG-07 | Missing temp/voltage/current fields produce 0.0 defaults, no crash | unit | `pytest tests/test_shelly_plugin.py::TestMissingFields -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_shelly_plugin.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_shelly_plugin.py` -- covers PLUG-01 through PLUG-07 (new file, ~300 LOC)
- Mock fixtures: reuse `_mock_session` pattern from `test_opendtu_plugin.py`
- Sample JSON responses for Gen1 `/status` and Gen2 `/rpc/Switch.GetStatus?id=0`

## Code Examples

### Gen1 /status Sample Response (for test fixtures)
```json
{
  "relays": [{"ison": true, "has_timer": false, "source": "http"}],
  "meters": [{
    "power": 342.5,
    "is_valid": true,
    "total": 117920,
    "counters": [342.5, 340.1, 338.7],
    "voltage": 230.4,
    "current": 1.49
  }],
  "temperature": 45.2,
  "overtemperature": false,
  "uptime": 86400
}
```

### Gen2 /rpc/Switch.GetStatus?id=0 Sample Response (for test fixtures)
```json
{
  "id": 0,
  "source": "init",
  "output": true,
  "apower": 342.5,
  "voltage": 230.4,
  "current": 1.49,
  "freq": 50.01,
  "aenergy": {"total": 14567.89, "by_minute": [5.23, 5.11, 5.08], "minute_ts": 1699012345},
  "ret_aenergy": {"total": 5.817},
  "temperature": {"tC": 45.2, "tF": 113.4}
}
```

### Gen1 /shelly Sample Response (for detection tests)
```json
{"type": "SHSW-PM", "mac": "AABBCCDDEEFF", "auth": false, "fw": "20230913-114244/v1.14.0-gcb84623"}
```

### Gen2 /shelly Sample Response (for detection tests)
```json
{"id": "shellyplus1pm-aabbccddeeff", "mac": "AABBCCDDEEFF", "model": "SNSW-001P16EU", "gen": 2, "fw_id": "20231107-164738/1.0.8-g", "ver": "1.0.8", "app": "Plus1PM", "auth_en": false}
```

## Open Questions

1. **Gen1 energy unit: Watt-minutes or Wh?**
   - What we know: Official Gen1 docs say `meters[0].total` is "total energy consumed in Watt-minute". Community reports and some firmware versions report Wh.
   - What's unclear: Whether the user's specific Gen1 firmware reports Wm or Wh.
   - Recommendation: Assume Watt-minutes for Gen1 (divide by 60). If values look wrong, add a config flag `gen1_energy_unit: "wm"|"wh"` as escape hatch. Start with Wm assumption since official docs say so.

2. **Should Shelly rated_power include in WRtg aggregation?**
   - What we know: If Shelly monitors a micro-inverter, its power IS real PV generation and should be in WRtg.
   - What's unclear: Edge case where Shelly monitors a non-PV load.
   - Recommendation: Include by default. The user sets `rated_power` on the InverterEntry -- if they set it, they want it counted.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `plugin.py` (ABC), `plugins/opendtu.py` (reference implementation), `sunspec_models.py` (register encoding), `config.py` (InverterEntry), `plugins/__init__.py` (plugin_factory), `device_registry.py` (lifecycle), `aggregation.py` (downstream consumer)
- `.planning/research/STACK.md` -- Shelly API endpoints and field mapping verified against official docs
- `.planning/research/ARCHITECTURE.md` -- Profile pattern and integration points
- `.planning/research/PITFALLS.md` -- Common failure modes and prevention strategies

### Secondary (MEDIUM confidence)
- [Shelly Gen1 API Reference](https://shelly-api-docs.shelly.cloud/gen1/) -- endpoint structure, /status fields
- [Shelly Gen2 Switch Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/) -- Switch.GetStatus response
- [evcc Shelly meter (Go)](https://pkg.go.dev/github.com/evcc-io/evcc/meter/shelly) -- auto-detection pattern validation

### Tertiary (LOW confidence)
- Gen1 energy unit ambiguity (Wm vs Wh) -- conflicting community reports, official docs say Wm

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new deps, proven aiohttp pattern
- Architecture: HIGH -- profile pattern matches OpenDTU, all integration points mapped to code
- Pitfalls: HIGH -- verified against official docs + existing codebase analysis
- SunSpec encoding: HIGH -- identical to OpenDTU, offsets verified against sunspec_models.py

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (Shelly API is stable, Gen1/Gen2 APIs frozen)
