# Register Mapping Specification (PROTO-03)

Complete register-by-register translation table mapping SolarEdge SE30K registers to the Fronius SunSpec proxy register layout served to Venus OS.

**Source SolarEdge:** 192.168.3.18:1502, unit ID 1
**Proxy Target:** port 502, unit ID 126
**Architecture:** Cache-based -- proxy polls SolarEdge asynchronously, serves Venus OS reads from local cache.

---

## Overview

Both SolarEdge and Fronius implement standard SunSpec models. The register layout within each model is defined by the SunSpec specification, so the data format is identical. The translation task consists of:

1. **Identity substitution** -- Replace "SolarEdge" with "Fronius" in Common Model
2. **Model chain construction** -- Build the expected chain (SolarEdge may lack Model 120/123)
3. **Scale factor passthrough** -- SunSpec scale factors work identically on both sides
4. **Power control translation** -- Map SunSpec Model 123 writes to SolarEdge proprietary registers (0xF300-0xF322)
5. **Unit ID translation** -- Proxy listens on unit 126, connects to SolarEdge on unit 1

---

## Proxy Register Layout

The proxy presents a contiguous SunSpec model chain starting at register 40000:

| Address Range | Model | DID | Length | Total Regs | Translation Type |
|---------------|-------|-----|--------|------------|------------------|
| 40000-40001 | SunSpec Header "SunS" | -- | -- | 2 | STATIC |
| 40002-40068 | Model 1 (Common) | 1 | 65 | 67 | MIXED (identity replaced, rest passthrough) |
| 40069-40120 | Model 103 (Three-Phase Inverter) | 103 | 50 | 52 | PASSTHROUGH from SE 40069-40120 |
| 40121-40148 | Model 120 (Nameplate) | 120 | 26 | 28 | SYNTHESIZED (SE may not provide this) |
| 40149-40174 | Model 123 (Immediate Controls) | 123 | 24 | 26 | TRANSLATED (writes to SE proprietary regs) |
| 40175-40176 | End Marker | 0xFFFF | 0x0000 | 2 | STATIC |

**Address calculation verification:**
- Common: 40000 + 2 = 40002
- Inverter: 40002 + 2 + 65 = 40069
- Nameplate: 40069 + 2 + 50 = 40121
- Controls: 40121 + 2 + 26 = 40149
- End: 40149 + 2 + 24 = 40175

---

## Common Model Detail (Model 1)

| Proxy Address | Name | Size (regs) | Proxy Value | Source | Translation Type |
|---------------|------|-------------|-------------|--------|-----------------|
| 40000-40001 | SunSpec ID | 2 | 0x53756E53 ("SunS") | Static | HARDCODED |
| 40002 | C_SunSpec_DID | 1 | 1 | Static | HARDCODED |
| 40003 | C_SunSpec_Length | 1 | 65 | Static | HARDCODED |
| 40004-40019 | C_Manufacturer | 16 | "Fronius" + null padding (32 bytes) | Static | REPLACED |
| 40020-40035 | C_Model | 16 | From SE 40020-40035 | SE Common | PASSTHROUGH |
| 40036-40043 | C_Options | 8 | "NOT_IMPLEMENTED" padded | Static | HARDCODED |
| 40044-40051 | C_Version | 8 | From SE 40044-40051 | SE Common | PASSTHROUGH |
| 40052-40067 | C_SerialNumber | 16 | From SE 40052-40067 | SE Common | PASSTHROUGH |
| 40068 | C_DeviceAddress | 1 | 126 | Static | HARDCODED |

**C_Manufacturer encoding:**
```
"Fronius" = 0x46 0x72 0x6F 0x6E 0x69 0x75 0x73 (7 bytes)
Padded:     0x46 0x72 0x6F 0x6E 0x69 0x75 0x73 0x00 0x00 ... 0x00 (32 bytes total)
Registers:  0x4672 0x6F6E 0x6975 0x7300 0x0000 ... 0x0000 (16 registers)
```

---

## Inverter Model 103 Detail (Three-Phase)

All 50 data registers are direct passthrough from SolarEdge at the same addresses.

| Proxy Address | Name | Size | Type | Units | SE Source | Translation |
|---------------|------|------|------|-------|-----------|-------------|
| 40069 | C_SunSpec_DID | 1 | uint16 | -- | SE 40069 | PASSTHROUGH (should be 103) |
| 40070 | C_SunSpec_Length | 1 | uint16 | -- | SE 40070 | PASSTHROUGH (should be 50) |
| 40071 | I_AC_Current | 1 | uint16 | A | SE 40071 | PASSTHROUGH |
| 40072 | I_AC_CurrentA | 1 | uint16 | A | SE 40072 | PASSTHROUGH |
| 40073 | I_AC_CurrentB | 1 | uint16 | A | SE 40073 | PASSTHROUGH |
| 40074 | I_AC_CurrentC | 1 | uint16 | A | SE 40074 | PASSTHROUGH |
| 40075 | I_AC_Current_SF | 1 | int16 | -- | SE 40075 | PASSTHROUGH |
| 40076 | I_AC_VoltageAB | 1 | uint16 | V | SE 40076 | PASSTHROUGH |
| 40077 | I_AC_VoltageBC | 1 | uint16 | V | SE 40077 | PASSTHROUGH |
| 40078 | I_AC_VoltageCA | 1 | uint16 | V | SE 40078 | PASSTHROUGH |
| 40079 | I_AC_VoltageAN | 1 | uint16 | V | SE 40079 | PASSTHROUGH |
| 40080 | I_AC_VoltageBN | 1 | uint16 | V | SE 40080 | PASSTHROUGH |
| 40081 | I_AC_VoltageCN | 1 | uint16 | V | SE 40081 | PASSTHROUGH |
| 40082 | I_AC_Voltage_SF | 1 | int16 | -- | SE 40082 | PASSTHROUGH |
| 40083 | I_AC_Power | 1 | int16 | W | SE 40083 | PASSTHROUGH |
| 40084 | I_AC_Power_SF | 1 | int16 | -- | SE 40084 | PASSTHROUGH |
| 40085 | I_AC_Frequency | 1 | uint16 | Hz | SE 40085 | PASSTHROUGH |
| 40086 | I_AC_Frequency_SF | 1 | int16 | -- | SE 40086 | PASSTHROUGH |
| 40087 | I_AC_VA | 1 | int16 | VA | SE 40087 | PASSTHROUGH |
| 40088 | I_AC_VA_SF | 1 | int16 | -- | SE 40088 | PASSTHROUGH |
| 40089 | I_AC_VAR | 1 | int16 | var | SE 40089 | PASSTHROUGH |
| 40090 | I_AC_VAR_SF | 1 | int16 | -- | SE 40090 | PASSTHROUGH |
| 40091 | I_AC_PF | 1 | int16 | % | SE 40091 | PASSTHROUGH |
| 40092 | I_AC_PF_SF | 1 | int16 | -- | SE 40092 | PASSTHROUGH |
| 40093-40094 | I_AC_Energy_WH | 2 | acc32 | Wh | SE 40093-40094 | PASSTHROUGH |
| 40095 | I_AC_Energy_WH_SF | 1 | uint16 | -- | SE 40095 | PASSTHROUGH |
| 40096 | I_DC_Current | 1 | uint16 | A | SE 40096 | PASSTHROUGH |
| 40097 | I_DC_Current_SF | 1 | int16 | -- | SE 40097 | PASSTHROUGH |
| 40098 | I_DC_Voltage | 1 | uint16 | V | SE 40098 | PASSTHROUGH |
| 40099 | I_DC_Voltage_SF | 1 | int16 | -- | SE 40099 | PASSTHROUGH |
| 40100 | I_DC_Power | 1 | int16 | W | SE 40100 | PASSTHROUGH |
| 40101 | I_DC_Power_SF | 1 | int16 | -- | SE 40101 | PASSTHROUGH |
| 40102 | I_Temp_Cab | 1 | int16 | C | SE 40102 | PASSTHROUGH |
| 40103 | I_Temp_Sink | 1 | int16 | C | SE 40103 | PASSTHROUGH |
| 40104 | I_Temp_Trans | 1 | int16 | C | SE 40104 | PASSTHROUGH |
| 40105 | I_Temp_Other | 1 | int16 | C | SE 40105 | PASSTHROUGH |
| 40106 | I_Temp_SF | 1 | int16 | -- | SE 40106 | PASSTHROUGH |
| 40107 | I_Status | 1 | uint16 | -- | SE 40107 | PASSTHROUGH |
| 40108 | I_Status_Vendor | 1 | uint16 | -- | SE 40108 | PASSTHROUGH |
| 40109-40120 | Reserved / Vendor | 12 | -- | -- | SE 40109-40120 | PASSTHROUGH |

---

## Model 120 Synthesis (Nameplate)

Model 120 is synthesized by the proxy because SolarEdge may not provide it in its model chain. All values are derived from the SE30K's specifications.

| Proxy Address | Name | Size | Type | Value | Notes |
|---------------|------|------|------|-------|-------|
| 40121 | DID | 1 | uint16 | 120 | Nameplate model identifier |
| 40122 | Length | 1 | uint16 | 26 | Model data length |
| 40123 | DERTyp | 1 | enum16 | 4 | PV (photovoltaic) |
| 40124 | WRtg | 1 | uint16 | 30000 | Rated power: 30,000 W (SE30K) |
| 40125 | WRtg_SF | 1 | int16 | 0 | Scale factor: 30000 * 10^0 = 30000 W |
| 40126 | VARtg | 1 | uint16 | 30000 | VA rating: 30,000 VA |
| 40127 | VARtg_SF | 1 | int16 | 0 | Scale factor |
| 40128 | VArRtgQ1 | 1 | int16 | 18000 | Reactive power Q1 (0.6 PF) |
| 40129 | VArRtgQ2 | 1 | int16 | 18000 | Reactive power Q2 |
| 40130 | VArRtgQ3 | 1 | int16 | -18000 | Reactive power Q3 (negative) |
| 40131 | VArRtgQ4 | 1 | int16 | -18000 | Reactive power Q4 (negative) |
| 40132 | VArRtg_SF | 1 | int16 | 0 | Scale factor |
| 40133 | ARtg | 1 | uint16 | 44 | Max current ~44A at 400V 3-phase |
| 40134 | ARtg_SF | 1 | int16 | 0 | Scale factor |
| 40135 | PFRtgQ1 | 1 | int16 | 100 | Power factor Q1 (1.00 with SF -2) |
| 40136 | PFRtgQ2 | 1 | int16 | 100 | Power factor Q2 |
| 40137 | PFRtgQ3 | 1 | int16 | -100 | Power factor Q3 |
| 40138 | PFRtgQ4 | 1 | int16 | -100 | Power factor Q4 |
| 40139 | PFRtg_SF | 1 | int16 | -2 | Scale factor: 100 * 10^-2 = 1.00 |
| 40140 | WHRtg | 1 | uint16 | 0 | Not applicable (no storage) |
| 40141 | WHRtg_SF | 1 | int16 | 0 | Scale factor |
| 40142 | AhrRtg | 1 | uint16 | 0 | Not applicable |
| 40143 | AhrRtg_SF | 1 | int16 | 0 | Scale factor |
| 40144 | MaxChaRte | 1 | uint16 | 0 | Not applicable |
| 40145 | MaxChaRte_SF | 1 | int16 | 0 | Scale factor |
| 40146 | MaxDisChaRte | 1 | uint16 | 0 | Not applicable |
| 40147 | MaxDisChaRte_SF | 1 | int16 | 0 | Scale factor |
| 40148 | Pad | 1 | uint16 | 0 | Padding |

---

## Model 123 Write Translation (Immediate Controls)

Model 123 is the write-path interface between Venus OS and the SolarEdge proprietary power control registers. Venus OS writes standard SunSpec Model 123 registers; the proxy translates these to SolarEdge proprietary commands.

### Model 123 Register Layout

| Proxy Address | Name | Size | Type | Access | Notes |
|---------------|------|------|------|--------|-------|
| 40149 | DID | 1 | uint16 | R | 123 (Immediate Controls) |
| 40150 | Length | 1 | uint16 | R | 24 |
| 40151 | Conn_WinTms | 1 | uint16 | R/W | Connection window time (not used) |
| 40152 | Conn_RvrtTms | 1 | uint16 | R/W | Connection revert time (not used) |
| 40153 | Conn | 1 | enum16 | R/W | Connection control (always CONNECT) |
| 40154 | WMaxLimPct | 1 | uint16 | R/W | Active power limit (% of WRtg) |
| 40155 | WMaxLimPct_WinTms | 1 | uint16 | R/W | Ramp window time (stored locally) |
| 40156 | WMaxLimPct_RvrtTms | 1 | uint16 | R/W | Revert timeout |
| 40157 | WMaxLimPct_RmpTms | 1 | uint16 | R/W | Ramp time |
| 40158 | WMaxLim_Ena | 1 | enum16 | R/W | Enable/disable power limiting |
| 40159 | OutPFSet | 1 | int16 | R/W | Output power factor setpoint (v2) |
| 40160-40174 | Remaining fields | 15 | -- | R/W | PF/VAR controls (not implemented in v1) |

### Write Translation Table

| Proxy Register | SunSpec Field | SE Target Register | Translation Logic |
|----------------|---------------|-------------------|-------------------|
| 40154 | WMaxLimPct | 0xF322 (62242) | SunSpec integer+SF to Float32. Example: SunSpec value 5000 with SF -2 = 50.00% -> write Float32 50.0 to 0xF322 |
| 40156 | WMaxLimPct_RvrtTms | 0xF310 (62224) | Uint32 seconds -> SE Command Timeout |
| 40157 | WMaxLimPct_RmpTms | 0xF318/0xF31A (62232/62234) | -> SE ramp-up/ramp-down rate (%/min) |
| 40158 | WMaxLim_Ena | 0xF300 (62208) | 1=ENABLED -> write 1; 0=DISABLED -> write 0 |

### Write Sequence (Proxy to SolarEdge)

Power control writes must follow this exact sequence:

1. **Enable first:** Venus OS writes `WMaxLim_Ena = 1` at proxy register 40158 -> Proxy writes `1` to SE register 0xF300 (enable dynamic power control)
2. **Set limit:** Venus OS writes `WMaxLimPct = 5000` (50.00%) at proxy register 40154 -> Proxy converts: `5000 * 10^(-2) = 50.0` -> Proxy writes Float32 `50.0` to SE register 0xF322
3. **Refresh:** Proxy must refresh 0xF322 at least every `Command Timeout / 2` seconds to prevent fallback
4. **Disable:** Venus OS writes `WMaxLim_Ena = 0` at proxy register 40158 -> Proxy writes `0` to SE register 0xF300

### Float32 Encoding for SolarEdge

SolarEdge power control registers use IEEE 754 Float32 (big-endian), occupying 2 Modbus registers:

```python
import struct
# Encode 50.0% as Float32 for writing to 0xF322
value = 50.0
registers = struct.unpack(">HH", struct.pack(">f", value))
# Result: (0x4248, 0x0000) -> write to 0xF322 and 0xF323
```

---

## Scale Factor Reference

### Formula

```
actual_value = raw_value * 10^scale_factor
```

- `raw_value`: The integer stored in the measurement register (uint16 or int16)
- `scale_factor`: Signed int16 stored in the corresponding `_SF` register
- Result: The real-world value with appropriate decimal precision

### Examples

| Register | Raw Value | SF Register | SF Value | Actual Value | Unit |
|----------|-----------|-------------|----------|--------------|------|
| I_AC_Power | 2071 | I_AC_Power_SF | -1 | 207.1 | W |
| WMaxLimPct | 5000 | WMaxLimPct_SF | -2 | 50.00 | % |
| WRtg | 30000 | WRtg_SF | 0 | 30000 | W |
| I_AC_Frequency | 5002 | I_AC_Frequency_SF | -2 | 50.02 | Hz |
| I_AC_VoltageAN | 2345 | I_AC_Voltage_SF | -1 | 234.5 | V |

### Implementation Notes

- Scale factors are **signed int16** -- use `struct.unpack('>h', data)` in Python
- A scale factor of 0 means the raw value is the actual value (multiply by 10^0 = 1)
- Negative scale factors (most common) shift the decimal point left
- The proxy passes through SolarEdge scale factors unchanged for Model 103

---

## SolarEdge Status Code Mapping

SolarEdge uses standard SunSpec status codes for I_Status (register 40107). These pass through unchanged.

| Value | SunSpec Name | SolarEdge Name | Description |
|-------|-------------|----------------|-------------|
| 1 | OFF | I_STATUS_OFF | Inverter off |
| 2 | SLEEPING | I_STATUS_SLEEPING | Night mode / auto-shutdown |
| 3 | STARTING | I_STATUS_STARTING | Grid monitoring / wake-up |
| 4 | MPPT | I_STATUS_MPPT | Producing power (normal operation) |
| 5 | THROTTLED | I_STATUS_THROTTLED | Producing power (curtailed) |
| 6 | SHUTTING_DOWN | I_STATUS_SHUTTING_DOWN | Shutting down |
| 7 | FAULT | I_STATUS_FAULT | Fault condition |
| 8 | STANDBY | I_STATUS_STANDBY | Maintenance / setup |

**Note:** dbus-fronius discards frames where Status = 7 and all measurement values are zero (Fronius null-frame filter). The proxy should avoid serving all-zero frames with fault status.

---

## SolarEdge Proprietary Register Reference

These are the SolarEdge-specific registers used for power control translation. They are NOT part of the SunSpec standard.

| Address (hex) | Address (dec) | Size | R/W | Name | Type | Range | Units |
|---------------|---------------|------|-----|------|------|-------|-------|
| 0xF300 | 62208 | 1 | R/W | Enable Dynamic Power Control | uint16 | 0-1 | -- |
| 0xF310 | 62224 | 2 | R/W | Command Timeout | uint32 | 0-MAX | sec |
| 0xF312 | 62226 | 2 | R/W | Fallback Active Power Limit | Float32 | 0-100 | % |
| 0xF318 | 62232 | 2 | R/W | Active Power Ramp-up Rate | Float32 | 0-100 | %/min |
| 0xF31A | 62234 | 2 | R/W | Active Power Ramp-down Rate | Float32 | 0-100 | %/min |
| 0xF322 | 62242 | 2 | R/W | Dynamic Active Power Limit | Float32 | 0-100 | % |

**Important constraints:**
- 0xF300 must be enabled (=1) BEFORE writing to any other power control register
- 0xF322 must be refreshed at least every `Command Timeout / 2` seconds
- All registers except 0xF322 are stored in non-volatile memory -- write only when changed
- "Advanced Power Control" must be enabled on the SolarEdge via SetApp or LCD
