# Feature Research: Shelly Plugin for PV-Inverter-Master

**Domain:** Shelly smart device integration as PV monitoring plugin
**Researched:** 2026-03-24
**Confidence:** HIGH (official Shelly API docs verified, evcc reference implementation studied)

## Shelly Device Context for PV Monitoring

Shelly smart plugs are widely used in the German balcony solar (Balkonkraftwerk) community to measure micro-inverter output. The typical setup: a Shelly Plug sits between the micro-inverter's AC output cable and the household socket. The Shelly measures power flowing through it -- effectively monitoring the inverter's production without requiring inverter-specific protocols.

**Key difference from SolarEdge/OpenDTU:** Shelly devices are AC-only measurement devices with relay control. They have no DC data, no MPPT status, no inverter-internal telemetry. They measure what comes out of the micro-inverter at the socket level.

## Shelly API Landscape by Generation

### Gen1 (Legacy: Shelly 1PM, Shelly Plug S original)

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /shelly` | `{type, mac, auth, fw, num_meters}` | No `gen` field -- absence of `gen` = Gen1 |
| `GET /status` | Full device status JSON | Meters array with power, energy |
| `GET /relay/0` | `{ison, power, energy, temperature}` | Relay state + basic metering |
| `GET /relay/0?turn=on` | Turns relay on | Control endpoint |
| `GET /relay/0?turn=off` | Turns relay off | Control endpoint |

**Gen1 meter fields:** `power` (W), `total` (Wh as Watt-minutes/60), `temperature` (device internal C)
**Gen1 limitations:** No voltage/current on basic models; Shelly 1PM Gen1 reports power but not V/A separately. The BL0937 chip in Gen1 Plug S cannot detect power direction (no negative values for feed-in).

### Gen2 (Plus series: Shelly Plus Plug S, Plus 1PM)

| Endpoint | Returns | Notes |
|----------|---------|-------|
| `GET /shelly` | `{id, mac, model, gen:2, fw_id, ver, app, auth_en}` | `gen` field present |
| `GET /rpc/Shelly.GetStatus` | All component statuses | Primary data endpoint |
| `GET /rpc/Switch.GetStatus?id=0` | Switch + metering data | Per-channel status |
| `GET /rpc/Switch.Set?id=0&on=true` | Turn on | Control via RPC |
| `GET /rpc/Switch.Set?id=0&on=false` | Turn off | Control via RPC |

**Gen2 Switch.GetStatus fields:**
- `output` (bool) -- relay on/off state
- `apower` (float) -- active power in Watts
- `voltage` (float) -- supply voltage in Volts
- `current` (float) -- current in Amps
- `pf` (float) -- power factor
- `freq` (float) -- network frequency in Hz
- `aenergy.total` (float) -- total consumed energy in Wh
- `aenergy.by_minute` (array) -- last 3 minutes in mWh
- `ret_aenergy.total` (float) -- returned energy in Wh (only on supported devices)
- `temperature.tC` (float) -- device temperature in Celsius
- `errors` (array) -- `["overtemp", "overpower", "overvoltage", "undervoltage"]`

### Gen3 (Shelly Plug S Gen3, Plug PM Gen3)

Same RPC API as Gen2 (`gen:3` in `/shelly` response). Gen3 uses the BL0942 chip which CAN detect power direction, enabling negative `apower` values for solar feed-in measurement. This is the recommended device for PV monitoring.

## Generation Auto-Detection Strategy

All Shelly generations expose `GET /shelly`. The response structure differs:

```
Gen1: {"type":"SHPLG-S","mac":"XXXX","auth":false,"fw":"...","num_meters":1}
Gen2: {"id":"shellypluss-XXXX","mac":"XXXX","model":"SNPL-00116EU","gen":2,...}
Gen3: {"id":"shellyplugsg3-XXXX","mac":"XXXX","model":"S3PL-00112EU","gen":3,...}
```

**Detection algorithm:** `GET /shelly` -> if `gen` field exists, use its value (2 or 3 -> Gen2 API). If `gen` absent, it is Gen1. This matches the approach used by evcc (reference: evcc-io/evcc meter/shelly package).

## Feature Landscape

### Table Stakes (Users Expect These)

Features that MUST exist for the Shelly plugin to feel like a first-class citizen alongside SolarEdge/OpenDTU.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Power polling (W) | Core purpose -- measure micro-inverter output | LOW | Gen1: `power` from `/status`. Gen2/3: `apower` from `Switch.GetStatus` |
| Voltage reading (V) | Existing plugins show voltage | LOW | Gen2/3 only. Gen1: synthesize 0 or skip |
| Current reading (A) | Existing plugins show current | LOW | Gen2/3 only. Gen1: synthesize 0 or skip |
| Energy total (Wh) | Dashboard shows daily yield + total | LOW | Gen1: `total` (Watt-minutes -> Wh). Gen2/3: `aenergy.total` |
| Temperature (C) | Existing plugins show device temp | LOW | Gen1: `temperature`. Gen2/3: `temperature.tC` |
| On/Off switch control | PROJECT.md specifies this explicitly | LOW | Gen1: `relay/0?turn=on/off`. Gen2/3: `Switch.Set?id=0&on=true/false` |
| Generation auto-detection | PROJECT.md: "Auto-Detection der Shelly-Generation beim Hinzufuegen" | MEDIUM | `GET /shelly` -> check `gen` field presence/value |
| Gen1/Gen2+ profile system | Different API shapes need abstraction | MEDIUM | Two profile classes behind one ShellyPlugin facade |
| Device dashboard (gauge + AC values) | Every device gets a dashboard -- existing pattern | MEDIUM | Reuse existing gauge/AC-table components, no DC section |
| Connection card with On/Off toggle | Matches OpenDTU pattern (has power on/off) | LOW | Replace power-limit slider with simple on/off toggle |
| Aggregation into virtual inverter | Shelly data must flow into Venus OS | LOW | Plugin returns SunSpec registers via existing PollResult |
| Add-Device flow: Shelly option | Third option alongside SolarEdge/OpenDTU | LOW | New "shelly" type in plugin_factory + UI selector |
| Config persistence (host, channel) | Standard config pattern | LOW | New fields on InverterEntry: `shelly_channel` (default 0) |
| Frequency reading (Hz) | Grid frequency is useful for PV monitoring | LOW | Gen2/3: `freq` field. Gen1: not available, synthesize 50.0 |

### Differentiators (Competitive Advantage)

Features that go beyond basic integration and add real value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Returned energy tracking | Shelly Gen3 can measure energy fed INTO grid (negative apower, ret_aenergy). Unique data point no other plugin has | LOW | Only on Gen3 with BL0942 chip. Show as "Feed-in Energy" on dashboard |
| Error condition display | Shelly reports overtemp/overpower/overvoltage/undervoltage errors. Surface these as toast notifications | LOW | Gen2/3: `errors` array in Switch.GetStatus |
| Power factor display | PF matters for micro-inverter efficiency assessment | LOW | Gen2/3: `pf` field. Nice addition to AC details |
| mDNS discovery of Shellys | Shelly devices announce via mDNS as `_http._tcp.local.` with "shelly" in hostname. Auto-find them on the network | MEDIUM | Existing scanner infrastructure could be extended. Shellys respond to `GET /shelly` on port 80 |
| Per-minute power history from device | Gen2/3 `aenergy.by_minute` gives 3-minute granular data directly from the device, no extra storage needed | LOW | Could supplement the existing ring buffer sparklines |

### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Shelly Cloud API integration | "Access from anywhere" | Adds cloud dependency, auth complexity, latency. PROJECT.md explicitly says "Nur lokale REST API, kein Cloud-Account noetig" | Local REST API only, as designed |
| Power limiting (%) for Shelly | "Match SolarEdge feature parity" | Shelly plugs are binary on/off relays. They cannot do percentage-based power limiting. Pretending otherwise would be misleading | On/Off only. Set `throttle_enabled: false` by default for Shelly devices (monitoring-only) |
| DC values (voltage, current, power) | "Feature parity with SolarEdge dashboard" | Shelly measures AC only at the socket. There are no DC values. Showing zeros or N/A clutters the UI | Hide DC section entirely for Shelly devices. Dashboard should adapt based on device capabilities |
| Shelly scripting/automation | "Run scripts on the Shelly device" | Out of scope -- this proxy monitors and aggregates, does not manage device firmware/scripts | Users configure Shelly scripts via Shelly app directly |
| MQTT subscription to Shelly | "Subscribe to Shelly's built-in MQTT instead of polling REST" | Adds MQTT client complexity, Shelly MQTT needs configuration on the device side, REST polling is simpler and matches OpenDTU pattern | REST polling at configurable interval (default 5s) |
| Shelly Gen4 support | "Future-proof for Gen4 devices" | Gen4 not widely available yet, API may change. YAGNI | Gen4 uses same RPC API as Gen2/3 per current docs, so it should work. Add explicit support when a user has one |
| Shelly EM / 3EM support | "Measure grid/house consumption" | These are energy meters, not PV inverter monitors. They measure consumption at the panel level. Does not fit the "inverter plugin" abstraction | Out of scope per PROJECT.md -- proxy only handles PV data |
| Automatic relay scheduling | "Turn micro-inverter on/off on schedule" | Feature creep. Proxy is for monitoring + Venus OS integration, not home automation | Users can use Shelly app or Home Assistant for scheduling |

## Feature Dependencies

```
[Generation Auto-Detection]
    |-- requires --> [/shelly endpoint probe]
    |-- feeds -----> [Gen1/Gen2+ Profile System]
                          |
                          |-- Gen1Profile --> [/status + /relay polling]
                          |-- Gen2Profile --> [/rpc/Switch.GetStatus polling]
                          |
                          v
                    [ShellyPlugin (facade)]
                          |
                          |-- implements --> [InverterPlugin ABC]
                          |                      |
                          |                      |-- poll() --> [PollResult with SunSpec registers]
                          |                      |-- write_power_limit() --> [On/Off only, no %]
                          |                      |-- connect() --> [aiohttp session + gen detect]
                          |
                          |-- feeds -----> [DashboardCollector]
                          |                      |
                          |                      v
                          |                [Device Dashboard (no DC section)]
                          |
                          |-- feeds -----> [AggregationLayer]
                                               |
                                               v
                                         [Virtual Fronius Inverter for Venus OS]

[Add-Device Flow]
    |-- requires --> [plugin_factory update]
    |-- requires --> [InverterEntry.type = "shelly"]
    |-- requires --> [UI: third device type option]
    |-- triggers --> [Generation Auto-Detection on save]

[On/Off Toggle]
    |-- requires --> [ShellyPlugin.send_switch_command()]
    |-- requires --> [Dashboard UI: toggle instead of slider]
    |-- uses -----> [Existing WebSocket command pattern]
```

### Dependency Notes

- **Profile System requires Auto-Detection:** The profile (Gen1 vs Gen2+) must be determined before the first poll. Auto-detection runs once at connect time and caches the result.
- **Dashboard adapts to capabilities:** Shelly devices have no DC data. The dashboard component must conditionally hide the DC section and show only AC values + temperature.
- **Aggregation is transparent:** Once ShellyPlugin returns a valid PollResult with SunSpec Model 103 registers, the existing AggregationLayer handles it identically to SolarEdge/OpenDTU data. No aggregation changes needed.
- **On/Off conflicts with power limiting:** Shelly must default to `throttle_enabled: false` so the PowerLimitDistributor does not try to send percentage limits to it. On/Off is a separate control path.

## MVP Definition

### Launch With (v6.0 Core)

- [ ] ShellyPlugin implementing InverterPlugin ABC with Gen1/Gen2+ profiles
- [ ] Generation auto-detection via `GET /shelly` on connect
- [ ] REST polling: power, voltage, current, energy, temperature, frequency
- [ ] On/Off relay control via webapp toggle
- [ ] SunSpec register encoding (AC values mapped to Model 103, no DC)
- [ ] Device dashboard: power gauge, AC values table, connection card with on/off
- [ ] Add-Device flow: "Shelly" as third option with host input
- [ ] Config: `type: "shelly"`, `shelly_channel: 0`, host field
- [ ] Aggregation: Shelly power flows into virtual inverter sum
- [ ] `throttle_enabled: false` default (monitoring-only in power distributor)

### Add After Validation (v6.x)

- [ ] Returned energy display -- when Gen3 device is detected, show feed-in Wh
- [ ] Error condition toasts -- surface overtemp/overpower from Shelly errors array
- [ ] mDNS discovery -- find Shellys on network automatically (extend scanner)
- [ ] Power factor display -- add PF to AC details panel

### Future Consideration (v7+)

- [ ] Shelly Gen4 explicit support -- when devices become common
- [ ] Multi-channel Shellys (2PM, 4PM) -- monitor multiple circuits per device

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Power/energy polling | HIGH | LOW | P1 |
| Gen auto-detection + profile system | HIGH | MEDIUM | P1 |
| On/Off switch control | HIGH | LOW | P1 |
| Device dashboard | HIGH | MEDIUM | P1 |
| Add-Device flow UI | HIGH | LOW | P1 |
| Aggregation integration | HIGH | LOW | P1 |
| Voltage/current/frequency | MEDIUM | LOW | P1 |
| Temperature display | MEDIUM | LOW | P1 |
| Config persistence | HIGH | LOW | P1 |
| Returned energy (Gen3) | MEDIUM | LOW | P2 |
| Error condition toasts | MEDIUM | LOW | P2 |
| Power factor display | LOW | LOW | P2 |
| mDNS discovery | MEDIUM | MEDIUM | P2 |
| Multi-channel support | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v6.0 launch
- P2: Should have, add in v6.x
- P3: Nice to have, future milestone

## Existing Architecture Integration Points

| Integration Point | What Changes | What Stays |
|-------------------|--------------|------------|
| `plugin_factory()` | Add `elif entry.type == "shelly"` branch | Factory pattern unchanged |
| `InverterEntry` | Add `shelly_channel: int = 0` field | All existing fields remain |
| `DashboardCollector` | No changes needed -- reads SunSpec registers generically | Decode map, snapshot format |
| `AggregationLayer` | No changes needed -- sums Model 103 registers | Summation logic |
| `PowerLimitDistributor` | Shelly defaults to `throttle_enabled: false`, skipped for % limits | Waterfall algorithm |
| `DeviceRegistry` | No changes needed -- starts poll task per device | Lifecycle management |
| Webapp HTML/JS | Add Shelly device type in add-device modal, on/off toggle on dashboard | Existing pages, routing |
| Config YAML | New type value `"shelly"` in inverters list | YAML schema |

## Shelly-Specific Data Mapping to SunSpec Model 103

| Shelly Field (Gen2/3) | SunSpec Register | Offset | Scale Factor | Notes |
|------------------------|-----------------|--------|--------------|-------|
| `apower` | AC Power (40083) | 14 | SF=0 | Direct watts |
| `voltage` | AC Voltage AN (40079) | 10 | SF=-1 | x10 encoding |
| `current` | AC Current (40071) | 2 | SF=-2 | x100 encoding |
| `freq` | AC Frequency (40085) | 16 | SF=-2 | x100 encoding |
| `aenergy.total` | AC Energy (40093) | 24-25 | SF=0 | acc32 in Wh |
| `temperature.tC` | Temperature Cab (40102) | 33 | SF=-1 | x10 encoding |
| N/A | DC Current (40096) | 27 | -- | Always 0 |
| N/A | DC Voltage (40098) | 29 | -- | Always 0 |
| N/A | DC Power (40100) | 31 | -- | Always 0 |
| `output` (bool) | Status (40107) | 38 | -- | true=4 (MPPT), false=2 (SLEEPING) |

## Competitor Feature Analysis

| Feature | dbus-shelly-1pm-pvinverter (Victron community) | evcc Shelly meter | Our Approach |
|---------|------------------------------------------------|-------------------|--------------|
| Gen1 + Gen2 support | Gen1 only | Both (auto-detect) | Both (auto-detect via /shelly) |
| Power monitoring | Yes (power only) | Yes (power, energy) | Full: power, voltage, current, energy, temp, freq |
| Venus OS integration | Yes (D-Bus direct) | No (EV charger focus) | Via Modbus proxy (Fronius emulation) |
| On/Off control | No | Yes | Yes, via webapp toggle |
| Multi-device aggregation | No (single device) | No (single meter) | Yes, aggregated virtual inverter |
| Dashboard | No | No | Full device-centric dashboard |
| Gen3 returned energy | No | No | Planned (v6.x differentiator) |

## Sources

- [Shelly Gen2+ Switch Component API](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/) -- Switch.GetStatus response fields, power metering data (HIGH confidence)
- [Shelly Gen1 API Reference](https://shelly-api-docs.shelly.cloud/gen1/) -- Legacy HTTP endpoints, /status, /relay structure (HIGH confidence)
- [Shelly Gen1 Compatibility (Gen2 docs)](https://shelly-api-docs.shelly.cloud/gen2/General/gen1Compatibility/) -- /shelly endpoint shared across generations (HIGH confidence)
- [Shelly Returned Energy Support](https://support.shelly.cloud/en/support/solutions/articles/103000316350) -- BL0937 vs BL0942 chip, which devices support negative power (HIGH confidence)
- [Shelly Balcony Power Plant Guide](https://www.shelly.com/pages/shelly-balcony-power-plant-how-to-measure-electricity-easily-and-accurately) -- Typical PV monitoring use case (MEDIUM confidence)
- [evcc Shelly meter integration](https://pkg.go.dev/github.com/evcc-io/evcc/meter/shelly) -- Reference implementation for Gen1/Gen2 auto-detection and unified interface (HIGH confidence)
- [Shelly Gen1/Gen2/Gen3/Gen4 Comparison](https://support.shelly.cloud/en/support/solutions/articles/103000316073) -- Device capabilities by generation (MEDIUM confidence)
- [Shelly Plug PM Gen3 Documentation](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen3/ShellyPlugPMG3/) -- Gen3 device specifics (HIGH confidence)
- [dbus-shelly-1pm-pvinverter](https://github.com/vikt0rm/dbus-shelly-1pm-pvinverter) -- Community Victron/Shelly integration (MEDIUM confidence)

---
*Feature research for: Shelly Plugin integration into PV-Inverter-Master v6.0*
*Researched: 2026-03-24*
