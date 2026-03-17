# Feature Research

**Domain:** Modbus TCP proxy for solar inverter integration (SolarEdge to Fronius emulation for Venus OS)
**Researched:** 2026-03-17
**Confidence:** HIGH (based on direct source code analysis of `victronenergy/dbus-fronius`)

## Critical Discovery: Venus OS Already Supports SolarEdge Natively

**Important finding:** Venus OS's `dbus-fronius` already supports SolarEdge inverters natively via Sunspec Modbus TCP. It reads Sunspec models 1, 101/103, 120, 123/704, and 160 directly from SolarEdge inverters. It also has a dedicated `SolarEdgeLimiter` class using SolarEdge's proprietary EDPC registers (0xF300+) for power limiting.

**This changes the project's value proposition.** The proxy is NOT needed to make Venus OS "see" a SolarEdge inverter -- `dbus-fronius` already does this by scanning all IPs in the LAN and probing for Sunspec at unit ID 126.

**Revised value proposition options:**
1. The proxy is needed if the SolarEdge is on a different network/port that Venus OS cannot reach directly
2. The proxy is needed to present the SolarEdge as a *Fronius-branded* inverter (to unlock Fronius-specific features like forced limiter enabling)
3. The proxy is needed to work around SolarEdge's single-TCP-connection limitation (port 502 allows only one client)
4. The proxy adds register caching, connection multiplexing, or protocol translation not available natively

**Recommendation:** Validate with the user which of these use cases is the actual driver. The features below are written assuming use case 3 (connection multiplexing) and/or use case 2 (Fronius identity emulation) are the primary drivers.

## How Venus OS Discovery Actually Works (Source Code Analysis)

**Confidence: HIGH** -- derived directly from `dbus-fronius` source code.

### Discovery Mechanism

1. **UDP broadcast** on port 50049 with `{"GetFroniusLoggerInfo":"all"}` -- Fronius-specific, responses on port 50050. SolarEdge inverters do NOT respond to this.
2. **IP sweep** -- scans ALL IPs in the LAN (or configured/known IPs first), attempting Modbus TCP connection on port 502 (default) with unit ID 126 (default).
3. **Sunspec header check** -- reads 2 registers at offsets 40000, 50000, then 0, looking for the "SunS" magic bytes.
4. **Model enumeration** -- walks the Sunspec model chain: Model 1 (Common) -> 101/102/103/111/112/113 or 701 (Inverter) -> 120 or 702 (Nameplate) -> 123 or 704 (Controls) -> 160 (MPPT Trackers) -> 0xFFFF (End).

### What dbus-fronius Reads from Model 1 (Common)

From registers at offset +2 through +65 of Model 1:
- Manufacturer string (offset 2, 16 registers) -- used to determine product ID
- Model string (offset 18, 16 registers) -- combined with manufacturer for product name
- Options string (offset 34, 8 registers) -- Fronius uses for data manager version
- Firmware version (offset 42, 8 registers)
- Serial number (offset 50, 16 registers) -- used as unique ID

**Manufacturer matching:**
- "Fronius" -> `VE_PROD_ID_PV_INVERTER_FRONIUS` (0xA142)
- "SMA" -> 0xA143
- "ABB" or "FIMER" -> 0xA145
- starts with "SolarEdge" -> `VE_PROD_ID_PV_INVERTER_SOLAREDGE` (0xA146)
- anything else -> `VE_PROD_ID_PV_INVERTER_SUNSPEC` (0xA144)

### What dbus-fronius Reads for Power Data

**Models 101/102/103 (integer+scale factor format):** 52 registers
- AC Current (offset 2, scale at 6)
- AC Voltage phase 1 (offset 10, scale at 13)
- AC Power (offset 14, scale at 15) -- signed
- Total Energy (offset 24, 2 registers, scale at 26)
- Operating State (offset 38)
- Per-phase currents at offsets 3,4,5; per-phase voltages at 10,11,12

**Models 111/112/113 (float format):** 62 registers
- AC Current (offset 2, float)
- AC Voltage (offset 16, float)
- AC Power (offset 22, float)
- Total Energy (offset 32, float)
- Operating State (offset 48)

### D-Bus Paths Published

The inverter service registers as `com.victronenergy.pvinverter.[id]` with these paths:
- `/Ac/Power` (W)
- `/Ac/Energy/Forward` (kWh)
- `/Ac/L1/Power`, `/Ac/L1/Current`, `/Ac/L1/Voltage`, `/Ac/L1/Energy/Forward`
- `/Ac/L2/...`, `/Ac/L3/...` (same structure)
- `/Ac/MaxPower` (W)
- `/Ac/PowerLimit` (W) -- writable, triggers power limiting
- `/Ac/NumberOfPhases`
- `/StatusCode` (0-12, Fronius-style codes)
- `/ErrorCode`
- `/ProductName`, `/ProductId`, `/Serial`, `/FirmwareVersion`
- `/Position` (0=Input1, 1=Output, 2=Input2)
- `/CustomName` -- writable
- `/Pv/0/V`, `/Pv/0/P`, `/Pv/1/V`, `/Pv/1/P` ... (tracker data)

## Feature Landscape

### Table Stakes (Must Have or It Does Not Work)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Sunspec Model 1 (Common) response | dbus-fronius reads manufacturer, model, serial, firmware from this model first. Without it, detection fails completely. | MEDIUM | Must respond with "Fronius" as manufacturer if goal is Fronius identity emulation. 66+ registers. |
| Sunspec Model 103 (3-phase inverter) response | Venus OS needs an inverter measurement model (101/102/103). SE30K is 3-phase, so 103. Without this, `checkDone()` fails (`phaseCount` stays 0). | MEDIUM | 52 registers including AC current, voltage, power, energy, and operating state with scale factors. |
| Sunspec header at register 40000 | dbus-fronius checks offsets 40000, 50000, 0 for "SunS" magic. Must respond at one of these. | LOW | Just 2 registers returning 0x5375 0x6E53 ("SunS"). |
| Sunspec model chain with 0xFFFF terminator | dbus-fronius walks model headers (ID + length pairs) sequentially. Chain must be: Header -> Model 1 -> Model 103 -> ... -> 0xFFFF. | MEDIUM | Each model header is 2 registers: model ID + body length. |
| Modbus TCP server on port 502 | Default port that Venus OS scans. Must accept connections on this port with unit ID 126 (default). | LOW | Standard Modbus TCP listener. |
| Unit ID 126 | dbus-fronius uses unit ID 126 by default for Sunspec detection. Hardcoded unless user configures alternative. | LOW | Just respond to the correct unit ID. |
| SolarEdge register reading (upstream client) | Must connect to actual SE30K at 192.168.3.18:1502 and read real Sunspec registers to get live data. | MEDIUM | SolarEdge allows only one TCP connection on port 502. The SE30K uses port 1502 which may be different. |
| Register value translation (SE -> proxy format) | SolarEdge and the proxy response format must align. Manufacturer string, product IDs, and potentially register offsets differ. Must translate. | HIGH | Core complexity of the proxy. Scale factors, data types, and model layouts may differ between what SE returns and what proxy serves. |
| Operating state mapping | Sunspec operating states must be mapped to the integer codes dbus-fronius expects. | LOW | dbus-fronius maps: Off=0, Sleeping/Shutdown/Standby=8, Starting=3, MPPT=11, Throttled=12, Fault=10. |
| Sunspec Model 120 (Nameplate) response | dbus-fronius reads max power from model 120 offset 3 (WRtg + scale at offset 4). Required for power limiting to work (denominator for percentage). | MEDIUM | Without maxPower, limiter detection fails. At minimum registers for WRtg and its scale factor. |
| Connection stability / reconnection | Venus OS rescans every 60 seconds. The proxy must stay responsive and handle disconnects gracefully. | MEDIUM | Must handle multiple sequential connections from dbus-fronius. |
| TOML/YAML config file | IP addresses, ports, polling interval, identity settings. | LOW | Foundation everything else needs. |
| systemd service | Runs on boot in LXC container, restarts on crash. | LOW | Standard unit file. |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Connection multiplexing | SolarEdge port 502 allows only one TCP connection. Proxy can hold one persistent upstream connection and serve multiple downstream clients (Venus OS, monitoring tools). | HIGH | This is likely the primary technical reason for the proxy's existence. |
| Sunspec Model 123 (Immediate Controls) for power limiting | Enables Venus OS power limiting through standard Sunspec WMaxLimPct. Translates to SolarEdge EDPC registers (0xF300+) upstream. | HIGH | dbus-fronius writes WMaxLimPct at model 123 offset +5 (5 registers: pct, unused, timeout, unused, enable). Proxy must translate to SE EDPC DynamicActivePowerLimit at 0xF322. |
| Fronius identity emulation (manufacturer = "Fronius") | When identified as Fronius, dbus-fronius force-enables the limiter (`LimiterForcedEnabled`). SolarEdge identity requires user to manually enable limiting in Venus OS settings. | LOW | Just change the manufacturer string in Model 1 from "SolarEdge" to "Fronius". Risk: may cause issues if Venus OS expects Fronius-specific behaviors (null-frame filtering). |
| Configuration webapp | Simple web UI to configure upstream SolarEdge IP/port, view connection status, see register mapping, adjust settings. | MEDIUM | Useful for debugging and initial setup. Not needed for core proxy function. |
| Sunspec Model 160 (MPPT tracker data) | Exposes per-tracker (per-string) voltage and power data in Venus OS. SE30K likely has multiple MPPT inputs. | MEDIUM | 20 registers per tracker. dbus-fronius reads voltage at offset +10 and power at +11 per tracker block. |
| Register caching with configurable poll interval | Reduces load on SolarEdge inverter by caching upstream reads. Serves cached values to Venus OS with configurable staleness. | MEDIUM | SolarEdge inverters can be slow to respond. Caching improves responsiveness. |
| Graceful degradation on upstream disconnect | If SolarEdge is unreachable, serve last-known values with appropriate status codes rather than disappearing from Venus OS entirely. | MEDIUM | Prevents Venus OS from losing the inverter and re-scanning unnecessarily. |
| Diagnostic logging / register dump | Log all register reads/writes for debugging Sunspec compatibility issues. Exportable from webapp. | LOW | Very useful during development and for troubleshooting. |
| Live register viewer in webapp | Table showing SolarEdge raw values vs translated proxy values side by side. | MEDIUM | Debugging aid for register translation validation. |
| Hot config reload | Change config without restarting service. | LOW | Watch config file or API endpoint to trigger reload. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Historical data storage / database | Users want to see production history | Venus OS already stores and graphs historical data via VRM portal. Duplicating creates data inconsistency and storage burden in LXC container. | Let Venus OS handle all data storage and visualization. |
| Solar API emulation (Fronius HTTP/JSON) | Fronius uses Solar API for older models; some think it is needed | dbus-fronius prefers Sunspec over Solar API. Solar API is legacy and adds massive complexity (HTTP server, JSON parsing, device type mapping). | Only implement Sunspec Modbus TCP. |
| Multi-inverter support in v1 | Users with multiple SolarEdge inverters | Dramatically increases complexity (multiple upstream connections, unit ID routing, model chain per device). | Support one inverter in v1. Architecture should allow adding more later via plugin pattern. |
| TLS/authentication on Modbus TCP | Security-minded users | Modbus TCP has no native security. All devices are on same LAN. Adding TLS breaks compatibility with Venus OS which expects plain Modbus TCP. | Rely on network-level security (LAN isolation). Bind to LAN interface only. |
| Direct D-Bus integration (bypass Modbus) | Seems more efficient than proxying Modbus | Requires modifying Venus OS or running custom code on the Venus OS device. Breaks the "no Venus OS modifications" constraint. Tight coupling to Venus OS internals. | Keep Modbus TCP as the integration layer -- it is the supported interface. |
| Fronius UDP broadcast emulation | Fronius uses UDP broadcast on port 50049 for fast discovery | Only works for Fronius-branded devices. dbus-fronius also does IP sweep fallback which works for any Sunspec device. Shaving 5 seconds off discovery is not worth the complexity. | Let Venus OS discover via IP sweep or configure the proxy IP manually in Venus OS settings. |
| Reactive power control | Some grid codes require reactive power management | SE30K reactive power control uses different SolarEdge registers. Venus OS pvinverter service does not expose reactive power paths. Zero benefit. | Out of scope entirely. |
| Firmware update passthrough | Forward firmware commands to SolarEdge | Extremely dangerous. SolarEdge firmware updates use proprietary protocol. Bricking risk. | Never proxy firmware operations. |
| MQTT/API integration | Alternative monitoring protocols | Venus OS communicates via Modbus TCP. No need for another protocol. Adds complexity with no benefit for the core use case. | Modbus TCP only. |
| Auto-discovery of inverters | Find SolarEdge automatically | Adds mDNS/broadcast complexity, error-prone. User knows their inverter IP. | Manual IP config in config file/webapp. |

## Feature Dependencies

```
[Config File (TOML/YAML)]
    +--foundation--> [Everything else]

[Sunspec Header (40000)]
    +--requires--> [Model 1 (Common)]
                       +--requires--> [Model 103 (Inverter)]
                       |                   +--enables--> [Operating State Mapping]
                       +--requires--> [Model 120 (Nameplate)]
                       |                   +--enables--> [Model 123 (Controls)]
                       |                                     +--enables--> [Power Limiting]
                       +--enables----> [Model 160 (MPPT Trackers)]
                       +--terminates-> [0xFFFF End Model]

[SolarEdge Upstream Client]
    +--enables--> [Register Value Translation]
                       +--enables--> [All downstream Sunspec models]

[Connection Multiplexing]
    +--enhances--> [SolarEdge Upstream Client]

[Register Caching]
    +--enhances--> [Connection Multiplexing]
    +--enhances--> [Graceful Degradation]

[Configuration Webapp]
    +--enhances--> [SolarEdge Upstream Client] (IP/port config)
    +--enhances--> [Diagnostic Logging]
    +--enhances--> [Live Register Viewer]

[Power Limiting]
    +--requires--> [Model 120 (maxPower known)]
    +--requires--> [Model 123 or 704 (control interface)]
    +--requires--> [SolarEdge EDPC registers (0xF300+) upstream write]
```

### Dependency Notes

- **Model 103 requires Model 1:** dbus-fronius reads Model 1 first; if `productName` is empty AND another Model 1 appears, detection is aborted. Model 1 must come first in the chain.
- **Power Limiting requires Model 120:** Without `maxPower` from Model 120, the limiter percentage calculation has no denominator. Limiter detection returns `false`.
- **Power Limiting requires upstream EDPC writes:** The proxy must translate Sunspec Model 123 writes (WMaxLimPct as percentage with scale factor) to SolarEdge proprietary registers (DynamicActivePowerLimit at 0xF322 as float32 percentage 0-100).
- **Fronius identity enhances Power Limiting:** When manufacturer is "Fronius", dbus-fronius force-enables limiter (`LimiterForcedEnabled`). When manufacturer is "SolarEdge", user must manually enable it in Venus OS settings.

## MVP Definition

### Launch With (v1)

- [ ] Config file (TOML) with SolarEdge IP/port/unit ID and proxy listen settings
- [ ] Modbus TCP server on port 502, unit ID 126 -- the listening endpoint for Venus OS
- [ ] Sunspec model chain: Header + Model 1 + Model 103 + Model 120 + 0xFFFF -- minimum for detection
- [ ] SolarEdge upstream Modbus TCP client -- connects to SE30K at configured IP:port
- [ ] Register translation: read SE30K Sunspec registers, translate to proxy responses
- [ ] Operating state mapping (Sunspec state enum to codes 0-12)
- [ ] systemd service for LXC container deployment
- [ ] Basic structured logging

### Add After Validation (v1.x)

- [ ] Model 123 (Immediate Controls) + SolarEdge EDPC translation -- power limiting
- [ ] Model 160 (MPPT tracker data) -- per-string monitoring
- [ ] Configuration webapp (FastAPI + htmx)
- [ ] Connection multiplexing -- handle multiple downstream clients
- [ ] Register caching -- improve performance and reduce SE30K load
- [ ] Graceful degradation on upstream disconnect
- [ ] Diagnostic logging with register dump
- [ ] Live register viewer in webapp

### Future Consideration (v2+)

- [ ] Plugin architecture for other inverter brands -- architecture prepared but not implemented in v1
- [ ] Model 704 (DERCtlAC) support -- Sunspec 2018 compatibility
- [ ] Multi-inverter support -- multiple upstream connections with unit ID routing
- [ ] Fronius identity emulation -- evaluate if the Fronius brand benefits outweigh the risks

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Config file (TOML) | HIGH | LOW | P1 |
| Modbus TCP server (port 502) | HIGH | LOW | P1 |
| Sunspec model chain (1, 103, 120) | HIGH | MEDIUM | P1 |
| SolarEdge upstream client | HIGH | MEDIUM | P1 |
| Register translation | HIGH | HIGH | P1 |
| Operating state mapping | HIGH | LOW | P1 |
| systemd service | HIGH | LOW | P1 |
| Power limiting (Model 123 + EDPC) | HIGH | HIGH | P2 |
| MPPT tracker data (Model 160) | MEDIUM | MEDIUM | P2 |
| Connection multiplexing | MEDIUM | HIGH | P2 |
| Configuration webapp | MEDIUM | MEDIUM | P2 |
| Register caching | MEDIUM | MEDIUM | P2 |
| Graceful degradation | MEDIUM | MEDIUM | P2 |
| Diagnostic logging | LOW | LOW | P2 |
| Plugin architecture | LOW | HIGH | P3 |
| Model 704 support | LOW | MEDIUM | P3 |
| Multi-inverter | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- Venus OS detection and basic monitoring
- P2: Should have, add when possible -- power control and operational quality
- P3: Nice to have, future consideration

## Key Technical Details for Implementation

### SolarEdge SE30K Specifics
- Modbus TCP port: 1502 (project context says 192.168.3.18:1502)
- Unit ID: 126 (standard for SolarEdge)
- Supports Sunspec models at register 40000+
- EDPC registers for power control: 0xF300-0xF322
- **Single TCP connection limitation on port 502** -- key constraint motivating the proxy

### Sunspec Register Map (What Proxy Must Serve)

```
Register 40000-40001: "SunS" header (0x5375, 0x6E53)
Register 40002-40003: Model 1 header (ID=1, Length=65 or 66)
Register 40004-40069: Model 1 body (manufacturer, model, serial, firmware, etc.)
Register 40070-40071: Model 103 header (ID=103, Length=50)
Register 40072-40121: Model 103 body (AC measurements + operating state)
Register 40122-40123: Model 120 header (ID=120, Length=26)
Register 40124-40149: Model 120 body (nameplate ratings incl. WRtg)
Register 40150-40151: End model (0xFFFF, 0)
```

With power limiting (v1.x):
```
Register 40150-40151: Model 123 header (ID=123, Length=24)
Register 40152-40175: Model 123 body (immediate controls, WMaxLimPct at offset +5)
Register 40176-40177: End model (0xFFFF, 0)
```

### Model 103 Register Layout (offsets from model start +2)

| Offset | Field | Type | Scale Offset | Notes |
|--------|-------|------|-------------|-------|
| 0 | Model ID | uint16 | - | Must be 103 |
| 1 | Model Length | uint16 | - | 50 |
| 2 | A (total AC current) | uint16 | 6 | Amps |
| 3 | AphA (L1 current) | uint16 | 6 | Amps |
| 4 | AphB (L2 current) | uint16 | 6 | Amps |
| 5 | AphC (L3 current) | uint16 | 6 | Amps |
| 6 | A_SF | int16 | - | Current scale factor |
| 10 | PhVphA (L1 voltage) | uint16 | 13 | Volts |
| 11 | PhVphB (L2 voltage) | uint16 | 13 | Volts |
| 12 | PhVphC (L3 voltage) | uint16 | 13 | Volts |
| 13 | V_SF | int16 | - | Voltage scale factor |
| 14 | W (AC power) | int16 | 15 | Watts (signed!) |
| 15 | W_SF | int16 | - | Power scale factor |
| 24 | WH (total energy) | uint32 | 26 | Watt-hours |
| 26 | WH_SF | int16 | - | Energy scale factor |
| 38 | St (operating state) | uint16 | - | Sunspec enum |

### Power Limit Translation

- **Downstream (Venus OS writes to proxy):** Model 123 offset +5: [WMaxLimPct, unused, WMaxLimPct_RvrtTms, unused, WMaxLim_Ena]
- **Upstream (proxy writes to SolarEdge):** EDPC register 0xF322 (DynamicActivePowerLimit) as float32 percentage (0-100)
- Scale factor: dbus-fronius reads scale at Model 123 body offset 23, computes `powerLimitScale = 100.0 / getScale(values, 0)`

### Sunspec Operating State Enum

| Sunspec Value | Name | Fronius Code | Venus OS Display |
|---------------|------|-------------|------------------|
| 1 | Off | 0 | - |
| 2 | Sleeping | 8 | Standby |
| 3 | Starting | 3 | Startup 3/6 |
| 4 | MPPT | 11 | Running (MPPT) |
| 5 | Throttled | 12 | Running (Throttled) |
| 6 | Shutting down | 8 | Standby |
| 7 | Fault | 10 | Error |
| 8 | Standby | 8 | Standby |

## Competitor / Existing Solution Analysis

| Feature | dbus-fronius (native) | This Proxy | Advantage |
|---------|----------------------|------------|-----------|
| SolarEdge monitoring | Yes (native Sunspec) | Yes (translated) | Proxy: connection multiplexing, caching |
| SolarEdge limiting | Yes (EDPC registers) | Yes (Model 123 -> EDPC) | Proxy: presents standard Sunspec interface; native: already works |
| Fronius identity | N/A (reads real manufacturer) | Configurable | Proxy: can force-enable limiter without user intervention |
| Connection sharing | No (one connection per device) | Yes | Proxy: allows Venus OS + other tools to share one connection |
| Configuration | Venus OS GUI | Webapp + config file | Proxy: independent config, no Venus OS modification needed |
| Network flexibility | Must be same subnet | Can bridge networks | Proxy: SE on different network/VLAN still works |

## Sources

- `victronenergy/dbus-fronius` GitHub repository (direct source code analysis, HIGH confidence):
  - `sunspec_detector.cpp` -- discovery mechanism, model enumeration, manufacturer matching
  - `sunspec_updater.cpp` -- register reading, power/voltage parsing, limiter logic
  - `solaredge_limiter.cpp` -- SolarEdge EDPC proprietary registers (0xF300+)
  - `inverter.cpp` -- D-Bus service registration, paths published
  - `inverter_gateway.cpp` -- IP scanning, UDP broadcast discovery
  - `dbus_fronius.cpp` -- detector initialization (SolarAPI + Sunspec at unit 126)
  - `data_processor.cpp` -- power/energy calculation and phase distribution
  - `fronius_udp_detector.cpp` -- UDP broadcast on port 50049
  - `defines.h` -- DeviceInfo struct, protocol types, enums
  - `products.h` -- product ID constants (0xA142-0xA146)
  - `power_info.cpp` -- D-Bus path structure (Power, Current, Voltage, Energy/Forward)
- Sunspec Information Model specification (models 1, 101-103, 111-113, 120, 123, 160, 701, 702, 704)

---
*Feature research for: Venus OS Fronius Proxy (SolarEdge to Fronius Modbus TCP translation)*
*Researched: 2026-03-17*
