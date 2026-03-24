# Technology Stack: Shelly Plugin Integration (v6.0)

**Project:** PV Inverter Proxy
**Researched:** 2026-03-24
**Scope:** Stack additions for Shelly Gen1/Gen2/Gen3 local REST API plugin
**Overall confidence:** HIGH

## Critical Finding: No New Dependencies Needed

The existing `aiohttp` client (already used by OpenDTU plugin) handles all Shelly HTTP/JSON communication. Shelly devices expose a simple local REST API -- same pattern as OpenDTU polling.

## Existing Stack (DO NOT CHANGE)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Runtime |
| pymodbus | >=3.6,<4.0 | Modbus TCP server + SolarEdge client |
| aiohttp | >=3.10,<4.0 | HTTP server, WebSocket, REST API, OpenDTU client, **Shelly client** |
| structlog | >=24.0 | Structured JSON logging |
| PyYAML | >=6.0,<7.0 | Configuration files |
| aiomqtt | >=2.3,<3.0 | MQTT publishing |
| zeroconf | >=0.140,<1.0 | mDNS broker discovery |
| Vanilla JS | -- | Frontend (zero dependencies, no build) |

## Recommended Stack Additions

**None.** Zero new Python packages. `aiohttp.ClientSession` with `session.get()` and `session.json()` is all that is needed.

### Why NOT aioshelly

The Home Assistant project maintains [aioshelly](https://github.com/home-assistant-libs/aioshelly) -- a full-featured Python Shelly library. Do NOT use it because:

| Concern | Detail |
|---------|--------|
| Heavy dependencies | Pulls in `orjson`, `bluetooth-data-tools`, CoAP stack |
| Wrong abstraction | Block/CoAP device model, WebSocket RPC channels -- we only need 2 HTTP GETs per poll |
| Designed for HA | Tightly coupled to Home Assistant's device model and event system |
| Project philosophy | "Zero new dependencies" -- extend existing aiohttp usage, same as OpenDTU |
| Complexity | We need ~150 LOC for the Shelly plugin. aioshelly adds thousands of LOC of unused functionality |

**Confidence: HIGH** -- Verified aioshelly's scope on PyPI and GitHub. Overkill for simple HTTP polling.

---

## Shelly API Reference by Generation

### Universal Detection: `GET /shelly`

All Shelly devices (Gen1, Gen2, Gen3) expose `GET http://<ip>/shelly`. This is the single endpoint for generation detection.

**Gen1 response:**
```json
{
  "type": "SHSW-PM",
  "mac": "AABBCCDDEEFF",
  "auth": false,
  "fw": "20230913-114244/v1.14.0-gcb84623",
  "discoverable": true
}
```
- **No `gen` field.** Presence of `type` without `gen` indicates Gen1.

**Gen2/Gen3 response:**
```json
{
  "name": "My Shelly",
  "id": "shellyplus1pm-aabbccddeeff",
  "mac": "AABBCCDDEEFF",
  "model": "SNSW-001P16EU",
  "gen": 2,
  "fw_id": "20231107-164738/1.0.8-g",
  "ver": "1.0.8",
  "app": "Plus1PM",
  "auth_en": false
}
```
- `gen` field present: `2` for Gen2, `3` for Gen3.
- Gen3 uses the **identical** RPC API as Gen2 (confirmed by official docs, shellyctl, and forum discussions).

**Detection algorithm:**
```python
async def detect_generation(session: aiohttp.ClientSession, host: str) -> tuple[str, dict]:
    """Detect Shelly generation. Returns ("gen1"|"gen2", device_info_dict)."""
    async with session.get(f"http://{host}/shelly", timeout=aiohttp.ClientTimeout(total=5)) as resp:
        data = await resp.json()
    gen = data.get("gen", 0)
    if gen >= 2:
        return "gen2", data  # Gen2 and Gen3 share the same API
    return "gen1", data
```

**Confidence: HIGH** -- Verified via official Shelly Gen1 and Gen2 API docs plus evcc's open-source Go implementation.

---

### Gen1 API Endpoints

**Polling: `GET /status`**

Returns full device status including relay state, metering, temperature.

```json
{
  "relays": [
    {
      "ison": true,
      "has_timer": false,
      "source": "http"
    }
  ],
  "meters": [
    {
      "power": 342.5,
      "is_valid": true,
      "total": 117920,
      "counters": [342.5, 340.1, 338.7],
      "voltage": 230.4,
      "current": 1.49
    }
  ],
  "temperature": 45.2,
  "overtemperature": false,
  "uptime": 86400
}
```

| Field Path | Type | Unit | Notes |
|------------|------|------|-------|
| `meters[0].power` | float | W | Instantaneous active power |
| `meters[0].voltage` | float | V | Supply voltage (1PM, Plug S, 2.5) |
| `meters[0].current` | float | A | Current draw |
| `meters[0].total` | float | Wh | Accumulated energy |
| `relays[0].ison` | bool | -- | Relay on/off state |
| `temperature` | float | C | Internal temp (not all Gen1 have this -- may be absent) |
| `overtemperature` | bool | -- | Overtemp protection triggered |

Note: Some Gen1 devices (Shelly EM, 3EM) use `emeters[]` instead of `meters[]`. For PV metering plugs (Plug S, 1PM), `meters[]` is the relevant array.

**Switching: `GET /relay/0?turn=on` or `GET /relay/0?turn=off`**

```
GET http://<ip>/relay/0?turn=on   -> {"ison": true, "has_timer": false, ...}
GET http://<ip>/relay/0?turn=off  -> {"ison": false, "has_timer": false, ...}
```

Gen1 uses GET for actions (the HTTP method is intentionally ignored per docs). Relay index `0` = first/only relay.

**Confidence: HIGH** -- Official Gen1 API docs.

---

### Gen2/Gen3 API Endpoints (Identical Protocol)

Gen2 and Gen3 use the same JSON-RPC 2.0 over HTTP. The official docs cover both under "Gen2+". The CLI tool `shellyctl` explicitly targets "Gen2/3 API". There are no Gen3-specific endpoints.

**Polling: `GET /rpc/Switch.GetStatus?id=0`**

Returns switch status with integrated power metering.

```json
{
  "id": 0,
  "source": "init",
  "output": true,
  "apower": 342.5,
  "voltage": 230.4,
  "current": 1.49,
  "aenergy": {
    "total": 14567.89,
    "by_minute": [5.23, 5.11, 5.08],
    "minute_ts": 1699012345
  },
  "temperature": {
    "tC": 45.2,
    "tF": 113.4
  }
}
```

| Field Path | Type | Unit | Notes |
|------------|------|------|-------|
| `apower` | float | W | Instantaneous active power |
| `voltage` | float | V | Supply voltage |
| `current` | float | A | Current draw |
| `aenergy.total` | float | Wh | Accumulated energy |
| `output` | bool | -- | Switch on/off state |
| `temperature.tC` | float/null | C | Device temp (may be null on some models) |

For meter-only devices (no relay, PM1 component): `GET /rpc/PM1.GetStatus?id=0` returns same power fields without `output`.

**Switching: `GET /rpc/Switch.Set?id=0&on=true`**

```
GET http://<ip>/rpc/Switch.Set?id=0&on=true   -> {"was_on": false}
GET http://<ip>/rpc/Switch.Set?id=0&on=false  -> {"was_on": true}
```

**Confidence: HIGH** -- Official Gen2 Switch component docs.

---

## API Comparison Matrix

| Aspect | Gen1 | Gen2/Gen3 |
|--------|------|-----------|
| **Identification** | `/shelly` -> `type` field, no `gen` | `/shelly` -> `gen: 2` or `gen: 3` |
| **Poll endpoint** | `GET /status` | `GET /rpc/Switch.GetStatus?id=0` |
| **Power field** | `meters[0].power` | `apower` |
| **Voltage field** | `meters[0].voltage` | `voltage` |
| **Current field** | `meters[0].current` | `current` |
| **Energy field** | `meters[0].total` (Wh) | `aenergy.total` (Wh) |
| **Relay state** | `relays[0].ison` | `output` |
| **Temperature** | `temperature` (top-level, may be absent) | `temperature.tC` (may be null) |
| **Switch ON** | `GET /relay/0?turn=on` | `GET /rpc/Switch.Set?id=0&on=true` |
| **Switch OFF** | `GET /relay/0?turn=off` | `GET /rpc/Switch.Set?id=0&on=false` |
| **Auth** | HTTP Basic Auth (if enabled) | Digest Auth (if enabled) |
| **Power limiting** | Not supported (on/off only) | Not supported (on/off only) |

---

## Integration Pattern: Profile-Based Abstraction

Use a dict-based profile to abstract Gen1 vs Gen2 API differences. The ShellyPlugin selects the profile at connect time based on auto-detected generation.

```python
SHELLY_PROFILES = {
    "gen1": {
        "poll_url": "/status",
        "switch_on_url": "/relay/0?turn=on",
        "switch_off_url": "/relay/0?turn=off",
    },
    "gen2": {  # Also used for Gen3
        "poll_url": "/rpc/Switch.GetStatus?id=0",
        "switch_on_url": "/rpc/Switch.Set?id=0&on=true",
        "switch_off_url": "/rpc/Switch.Set?id=0&on=false",
    },
}
```

Each profile has a corresponding `_extract_gen1(data)` / `_extract_gen2(data)` method to normalize the JSON response into a common dict:

```python
{
    "power_w": float,
    "voltage_v": float,
    "current_a": float,
    "energy_wh": float,
    "is_on": bool,
    "temperature_c": float | None,
}
```

---

## Integration Points with Existing Architecture

### InverterEntry Config Extension

Add to existing `InverterEntry` dataclass:

| New Field | Type | Default | Purpose |
|-----------|------|---------|---------|
| (existing) `type` | str | -- | New value: `"shelly"` (alongside `"solaredge"`, `"opendtu"`) |
| `shelly_gen` | str | `""` | `"gen1"` or `"gen2"` -- auto-detected on first connect, persisted to config |

No `gateway_host` needed -- Shelly devices are standalone (direct IP, no gateway like OpenDTU).

### Plugin Factory Extension

```python
# In plugins/__init__.py plugin_factory()
elif entry.type == "shelly":
    from pv_inverter_proxy.plugins.shelly import ShellyPlugin
    return ShellyPlugin(host=entry.host, generation=entry.shelly_gen, name=entry.name)
```

### InverterPlugin ABC Method Mapping

| ABC Method | Shelly Implementation |
|------------|----------------------|
| `connect()` | Create `aiohttp.ClientSession`, `GET /shelly` for generation detection + device info |
| `poll()` | GET profile poll URL, extract fields, encode to SunSpec Model 103 registers |
| `get_static_common_overrides()` | Manufacturer = `"Shelly"`, model from `/shelly` response (`type` or `app`) |
| `get_model_120_registers()` | Synthesize nameplate with `rated_power` from config (Shelly has no self-reported rating) |
| `write_power_limit()` | **No-op** -- return `WriteResult(success=True)`. Shelly has no %-based power limiting. |
| `close()` | Close aiohttp session |
| `reconfigure()` | Close session, update host. New session created on next `connect()` |

### Shelly-Specific Extension

Add `send_switch_command(on: bool) -> WriteResult` method outside the ABC -- exposed via webapp API route. Same pattern as OpenDTU's `send_power_command()`.

### Polling Interval

Use 5s (same as OpenDTU default). Shelly devices respond in <100ms on LAN with no rate limiting.

---

## What NOT to Add

| Library/Feature | Why Not |
|-----------------|---------|
| `aioshelly` | Pulls CoAP, Bluetooth deps. We need 2 HTTP GETs per poll. Overkill. |
| `orjson` | Responses are tiny JSON (<1KB). stdlib `json` is fine. |
| WebSocket RPC channel | Gen2 supports WS-based RPC but HTTP GET is simpler, stateless, proven by OpenDTU pattern. |
| Shelly Cloud API | Explicitly out of scope per PROJECT.md. Local API only. |
| mDNS discovery for Shellys | Could use existing zeroconf to find `_http._tcp.local.` Shelly devices, but add-device flow should use manual IP entry first. Discovery can be a follow-up. |
| Auth support | PROJECT.md: "kein Sicherheits-Overhead, alles im selben LAN". Skip for v6.0. |

## Installation

No changes to `pyproject.toml`. No new `pip install` commands.

## New Files

| File | Purpose |
|------|---------|
| `src/pv_inverter_proxy/plugins/shelly.py` | ShellyPlugin: poll, switch, SunSpec encoding, gen1/gen2 profiles |

Modified files: `plugins/__init__.py` (add shelly case), `config.py` (add `shelly_gen` field to `InverterEntry`), `webapp.py` (add switch command route, add-device flow), frontend files (Shelly device option, on/off toggle).

## Sources

- [Shelly Gen1 API Reference](https://shelly-api-docs.shelly.cloud/gen1/) -- HIGH confidence
- [Shelly Gen2 API Reference](https://shelly-api-docs.shelly.cloud/gen2/) -- HIGH confidence
- [Shelly Gen2 Switch Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/) -- HIGH confidence
- [Shelly Gen2 Shelly.GetDeviceInfo](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Shelly/) -- HIGH confidence
- [Shelly Gen2 PM1 Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/PM1/) -- HIGH confidence
- [Shelly Gen1 Compatibility Layer (Gen2)](https://shelly-api-docs.shelly.cloud/gen2/0.14/General/gen1Compatibility/) -- MEDIUM confidence
- [Shelly Gen1/Gen2/Gen3/Gen4 Comparison](https://support.shelly.cloud/en/support/solutions/articles/103000316073) -- MEDIUM confidence
- [evcc Shelly meter (Go, real-world reference)](https://pkg.go.dev/github.com/evcc-io/evcc/meter/shelly) -- HIGH confidence
- [shellyctl Gen2/3 CLI](https://github.com/jcodybaker/shellyctl) -- confirms Gen3 = Gen2 API
- [aioshelly on PyPI](https://pypi.org/project/aioshelly/) -- evaluated and rejected
