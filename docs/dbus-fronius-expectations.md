# dbus-fronius Expectations for Fronius Inverter Emulation (PROTO-01)

This document formally specifies what Venus OS (via dbus-fronius) expects from a Fronius inverter over Modbus TCP SunSpec. The proxy must satisfy every requirement listed here to be recognized and operated as a Fronius device.

**Source:** Direct analysis of [victronenergy/dbus-fronius](https://github.com/victronenergy/dbus-fronius) source code (sunspec_detector.cpp, sunspec_updater.cpp).

---

## Discovery Flow

dbus-fronius uses `SunspecDetector` to find inverters on the local network. The detection sequence is:

1. **Network Scan** -- dbus-fronius sends Modbus TCP requests to IP addresses on the LAN. Previously-detected addresses get priority.

2. **SunSpec Magic Value Check** -- Reads 2 registers (uint32) at addresses 40000, 50000, and 0 (tried in that order). The value must decode to ASCII `"SunS"` (hex `0x53756E53`). This is the SunSpec interoperability header defined by the SunSpec Alliance.

3. **Common Model Read (Model 1)** -- After finding `"SunS"`, reads the Common Model starting at the next register (offset +2 from the SunSpec header). Key fields extracted:
   - **C_Manufacturer** at offset +2: 16 registers (32 bytes). The manufacturer string, null-padded. This determines product ID assignment.
   - **C_Model** at offset +18: 16 registers (32 bytes). Device model string.
   - **C_Version** at offset +42: 8 registers (16 bytes). Firmware version.
   - **C_SerialNumber** at offset +50: 16 registers (32 bytes). Unique device identifier.

4. **Manufacturer Matching** -- The extracted manufacturer string determines how Venus OS classifies the device:
   - `"Fronius"` maps to `VE_PROD_ID_PV_INVERTER_FRONIUS` (deviceType != 0)
   - `"SolarEdge"` maps to `VE_PROD_ID_PV_INVERTER_SOLAREDGE`
   - `"SMA"` maps to `VE_PROD_ID_PV_INVERTER_SMA`
   - `"ABB"` or `"FIMER"` maps to `VE_PROD_ID_PV_INVERTER_ABB`
   - All others map to `VE_PROD_ID_PV_INVERTER_SUNSPEC`

5. **Model Chain Walk** -- Starting from the Common Model header, dbus-fronius reads each model's header (Model ID + Length) and advances by the length to the next model. This continues until it encounters the end marker `0xFFFF`. It looks for:
   - **Models 101, 102, or 103**: Inverter measurement data (determines single/split/three-phase)
   - **Model 120**: Nameplate ratings -- **MANDATORY for operation**
   - **Model 123 or 704**: Power limiting controls (optional but needed for power management)
   - **Model 160**: MPPT tracker data (optional)
   - **End Marker**: `0xFFFF` followed by `0x0000`

6. **Unit ID** -- dbus-fronius defaults to unit ID **126** for SunSpec device communication.

---

## Required Models

| Model | ID | Role | Required? | Length (registers) | Key Fields |
|-------|------|------|-----------|-------------------|------------|
| Common | 1 | Device identification | MANDATORY | 65 | C_Manufacturer must be `"Fronius"` (null-padded to 32 bytes). C_Model, C_Version, C_SerialNumber passed through. |
| Three-Phase Inverter | 103 | AC/DC measurements, power, energy, status | MANDATORY | 50 | I_AC_Current, I_AC_Power, I_AC_Energy_WH, I_DC_Power, I_Status. All use integer + scale factor encoding. |
| Nameplate | 120 | Rated power and capabilities | MANDATORY | 26 | WRtg (rated power in watts), DERTyp (=4 for PV). Required for dbus-fronius to operate correctly. |
| Immediate Controls | 123 | Power limiting (WMaxLimPct) | OPTIONAL (needed for power control) | 24 | WMaxLimPct (active power limit as percentage), WMaxLim_Ena (enable/disable). Venus OS writes here to throttle output. |
| End Marker | 0xFFFF | Terminates model chain | MANDATORY | 0 | Followed by `0x0000`. Signals end of SunSpec model chain. |

---

## Unit ID

dbus-fronius defaults to unit ID **126** for SunSpec devices. This is a Venus OS convention, not a SunSpec requirement.

- The SolarEdge SE30K defaults to unit ID **1** for Modbus TCP.
- The proxy must respond on unit ID **126** to be discovered by Venus OS.
- The proxy connects to SolarEdge on unit ID **1** -- these are independent.

A unit ID mismatch is the most common cause of "device not found" errors.

---

## Fronius-Specific Behaviors

When dbus-fronius identifies a device as Fronius (manufacturer string match), it applies these special behaviors:

1. **Power Limiting Auto-Enabled** -- For Fronius devices, power limiting is automatically enabled without requiring user configuration. The proxy benefits from this because Venus OS will immediately attempt to use Model 123 for power control.

2. **Solar API Fallback** -- dbus-fronius can also discover Fronius devices via HTTP Solar API v1 (JSON). This is NOT needed for the SunSpec Modbus TCP path. The proxy does not need to implement any HTTP endpoints.

3. **Null-Frame Filter** -- dbus-fronius discards measurement frames where all values are zero and Status = 7 (fault). This occurs during Fronius "solar net" communication timeouts. The proxy controls what it serves, so it should avoid sending all-zero frames.

4. **Split-Phase Handling** -- Single-phase Fronius devices can distribute power reporting across two phases. Not relevant for the three-phase SE30K proxy (Model 103).

---

## Protocol Details

### Integer Encoding with Scale Factors

SunSpec uses integer values with accompanying scale factor registers. This is NOT floating-point encoding.

**Formula:**
```
actual_value = raw_value * 10^scale_factor
```

- **raw_value**: Unsigned or signed 16-bit integer (uint16 or int16)
- **scale_factor**: Signed 16-bit integer (int16), typically negative
- **Byte order**: Big-endian (network byte order)

**Examples:**
| Raw Value | Scale Factor | Actual Value | Meaning |
|-----------|-------------|--------------|---------|
| 2071 | -1 | 207.1 | 207.1 W |
| 5000 | -2 | 50.00 | 50.00% |
| 30000 | 0 | 30000 | 30000 W |
| 2345 | -1 | 234.5 | 234.5 V |

### 32-bit Accumulator Values

Energy counters (e.g., I_AC_Energy_WH) use acc32 -- two consecutive 16-bit registers forming a 32-bit unsigned integer in big-endian order.

### Byte Order

All multi-byte values use big-endian (most significant byte first), consistent with Modbus specification.

---

## What the Proxy Must Emulate

To be recognized and operated as a Fronius inverter by Venus OS, the proxy must satisfy all six requirements:

- [ ] **1. SunSpec Header** -- Respond to register read at address 40000 with the value `0x53756E53` (ASCII `"SunS"`) across 2 registers.

- [ ] **2. Fronius Manufacturer String** -- Present `C_Manufacturer = "Fronius"` in the Common Model (registers 40004-40019). The string must be null-padded to exactly 32 bytes (16 registers).

- [ ] **3. Valid Model Chain** -- Present models in this exact order:
  - Common (Model 1) at 40002
  - Three-Phase Inverter (Model 103)
  - Nameplate (Model 120)
  - Immediate Controls (Model 123)
  - End Marker (0xFFFF + 0x0000)

- [ ] **4. Unit ID 126** -- Respond to Modbus TCP requests addressed to unit ID 126.

- [ ] **5. Integer + Scale Factor Encoding** -- All measurement values must use SunSpec integer encoding with scale factors. No floating-point values in the SunSpec model registers.

- [ ] **6. No HTTP Dependency** -- The proxy must function entirely over Modbus TCP. No Solar API HTTP endpoints are required when using the SunSpec path.
