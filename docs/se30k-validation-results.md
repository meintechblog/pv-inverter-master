# SolarEdge SE30K Live Validation Results

**Date:** 2026-03-18 (00:43 UTC)
**Script:** `scripts/validate_se30k.py`
**Target:** 192.168.3.18:1502, unit ID 1
**Inverter Status:** SLEEPING (nighttime -- no active power production)

---

## Raw Output

```
============================================================
SolarEdge SE30K Live Register Validation
Target: 192.168.3.18:1502 (unit ID 1)
Timestamp: 2026-03-17T23:43:56.106749+00:00
============================================================

-- 1. Connection Test --
Connected to 192.168.3.18:1502 -- PASS

-- 2. SunSpec Header Validation --
SunSpec Header: b'SunS' (SunS) -- PASS

-- 3. Common Model (Model 1) Validation --
  DID: 1 (expect 1)
  Length: 65 (expect 65)
  C_Manufacturer: "SolarEdge"
  C_Model: "SE30K-RW00IBNM4"
  C_Version: "0004.0023.0529"
  C_SerialNumber: "7E0C5F93"
  C_DeviceAddress: 1
Common Model: DID=1, Length=65 -- PASS

-- 4. Inverter Model Validation --
  Inverter Model: DID=103, Length=50
  DID check: 103 (three-phase=True) -- PASS
  AC Current: 0 * 10^-2 = 0.0 A
  AC Power: 0 * 10^0 = 0 W
  Frequency: 4998 * 10^-2 = 49.98 Hz
  Lifetime Energy: 20605854 * 10^0 = 20605854 Wh
  DC Voltage: 3 * 10^-1 = 0.3 V
  DC Power: 0 * 10^0 = 0 W
  Status: 2 (SLEEPING)
  Vendor Status: 0

-- 5. Model Chain Walk --
  Model at 40121: DID=1, Length=65
  Model at 40188: DID=203, Length=105
  Model at 40295: DID=701, Length=153
  Model at 40450: DID=702, Length=50
  Model at 40502: DID=703, Length=17
  Model at 40521: DID=704, Length=65
  Model at 40588: DID=705, Length=57
  Model at 40647: DID=706, Length=47
  Model at 40696: DID=707, Length=105
  Model at 40803: DID=708, Length=105
  Model at 40910: DID=709, Length=135
  Model at 41047: DID=710, Length=135
  Model at 41184: DID=711, Length=32
  Model at 41218: DID=712, Length=44
  Model at 41264: DID=713, Length=7
  Model at 41273: DID=65535, Length=0
  End of model chain

============================================================
SUMMARY
============================================================

Test                      Result   Detail
------------------------------------------------------------
Connection                PASS     Connected
SunSpec Header            PASS     b'SunS'
Common Model              PASS     DID=1, Length=65, Mfr=SolarEdge
Inverter Model            PASS     DID=103, Len=50, Power=0W, Status=SLEEPING
Model Chain               PASS     1 -> 203 -> 701 -> 702 -> 703 -> 704 -> 705 -> 706 -> 707 -> 708 -> 709 -> 710 -> 711 -> 712 -> 713

Model 120 (Nameplate): NOT FOUND -- Proxy must SYNTHESIZE Model 120
Model 123 (Controls): NOT FOUND -- Proxy must SYNTHESIZE Model 123 and translate writes to 0xF300/0xF322
```

---

## Key Findings

### 1. SunSpec Header -- CONFIRMED

Register 40000-40001 contains `0x53756E53` ("SunS") as expected. The SolarEdge SE30K is a compliant SunSpec device.

### 2. Common Model (Model 1) -- CONFIRMED

| Field | Expected | Actual | Match |
|-------|----------|--------|-------|
| DID | 1 | 1 | YES |
| Length | 65 | 65 | YES |
| C_Manufacturer | "SolarEdge" | "SolarEdge" | YES |
| C_Model | "SE30K" | "SE30K-RW00IBNM4" | YES (more specific) |
| C_Version | (any) | "0004.0023.0529" | N/A |
| C_SerialNumber | (any) | "7E0C5F93" | N/A |
| C_DeviceAddress | 1 | 1 | YES |

**Note:** The model string "SE30K-RW00IBNM4" is more specific than the documented "SE30K". The suffix identifies the specific hardware variant. The proxy should pass through (or map) this model string.

### 3. Inverter Model (Model 103) -- CONFIRMED

| Field | Expected | Actual | Match |
|-------|----------|--------|-------|
| DID | 103 | 103 | YES |
| Length | 50 | 50 | YES |
| Phase type | Three-phase | Three-phase | YES |

**Inverter readings (nighttime/sleeping):**

| Register | Value | Notes |
|----------|-------|-------|
| AC Current | 0.0 A | Expected (sleeping) |
| AC Power | 0 W | Expected (sleeping) |
| Frequency | 49.98 Hz | Grid frequency still readable while sleeping |
| Lifetime Energy | 20,605,854 Wh (~20.6 MWh) | Plausible for a 30kW inverter |
| DC Voltage | 0.3 V | Near-zero (panels dark) |
| DC Power | 0 W | Expected (sleeping) |
| Status | 2 (SLEEPING) | Nighttime auto-shutdown |
| Vendor Status | 0 | No vendor error |

**All values are plausible.** The inverter is in SLEEPING mode (nighttime). Frequency is still measurable from grid. Lifetime energy of ~20.6 MWh is realistic. A daytime validation would show non-zero power values.

### 4. Model Chain -- MAJOR FINDING

The SE30K has a much richer model chain than documented in the SolarEdge SunSpec Technical Note:

```
Model 103 (Three-Phase Inverter)
  |
  +-- Model 1 (Common) -- second Common block (possibly for meter/optimizer)
  +-- Model 203 (Watt-Hour Accumulator)
  +-- Model 701 (DER AC Measurement)
  +-- Model 702 (DER Capacity)
  +-- Model 703 (DER Enter Service)
  +-- Model 704 (DER Controls) -- THIS is the SunSpec controls model!
  +-- Model 705 (DER Active Power)
  +-- Model 706 (DER Reactive Power)
  +-- Model 707 (DER Watt-VAR)
  +-- Model 708 (DER Frequency Watt)
  +-- Model 709 (DER Frequency Droop)
  +-- Model 710 (DER Voltage Watt)
  +-- Model 711 (DER Voltage VAR)
  +-- Model 712 (DER Low/High Voltage Ride Through)
  +-- Model 713 (DER Low/High Frequency Ride Through)
  +-- 0xFFFF (End)
```

**Critical observations:**

1. **Model 120 (Nameplate) is NOT present.** Proxy must synthesize it. CONFIRMED.
2. **Model 123 (Immediate Controls) is NOT present.** Proxy must synthesize it. CONFIRMED.
3. **Model 704 (DER Controls) IS present** at address 40521, length 65. This is the newer SunSpec DER controls model. dbus-fronius can use Model 704 as an alternative to Model 123 (per research). This is significant -- the SE30K supports standard SunSpec DER controls via Model 704, though the proxy still needs to present Model 123 for maximum compatibility.
4. **Second Common Model (Model 1)** at address 40121 -- this likely represents a second device (meter or optimizer aggregate). The proxy should NOT pass this through; it should only serve the first Common Model with Fronius identity.
5. **Model 203 (Watt-Hour Accumulator)** provides detailed energy metering beyond what Model 103 offers.

### 5. Discrepancies from Documented Register Map

| Item | Documented | Actual | Impact |
|------|-----------|--------|--------|
| Model string | "SE30K" | "SE30K-RW00IBNM4" | Minor -- more specific variant ID |
| Model chain after 103 | "Unknown, possibly 0xFFFF" | 15 additional models (1, 203, 701-713) | Major -- much richer than expected |
| Model 120 | "May not be present" | Not present | CONFIRMED -- must synthesize |
| Model 123 | "Not present" | Not present | CONFIRMED -- must synthesize |
| Model 704 | Not mentioned | Present at 40521 | New finding -- SE30K supports DER Controls |
| Firmware version | Not specified | 0004.0023.0529 | Informational |

### 6. Implications for Proxy Design

1. **Model 120 synthesis is mandatory** -- confirmed by live data
2. **Model 123 synthesis is mandatory** -- confirmed by live data, with write translation to SE proprietary registers (0xF300/0xF322)
3. **Model 704 discovery** -- dbus-fronius looks for Model 704 as alternative to Model 123. The proxy could potentially use the SE30K's native Model 704 for power control instead of proprietary registers. This needs further investigation but does not change the v1 proxy design (which synthesizes Model 123).
4. **Second Common Model** -- the proxy must be careful not to walk the SE30K's chain beyond Model 103 and accidentally include the second device's registers
5. **Nighttime behavior** -- the SE30K responds normally while sleeping (Status=2). All measurement registers read as zero except grid frequency, which is expected and correct.

---

## Validation Status

| Check | Result |
|-------|--------|
| SunSpec Header "SunS" at 40000 | PASS |
| Common Model DID=1, Length=65 | PASS |
| Manufacturer = "SolarEdge" | PASS |
| Inverter Model DID=103 (three-phase) | PASS |
| Inverter Model Length=50 | PASS |
| Plausible measurement values | PASS (sleeping) |
| Model chain walked successfully | PASS |
| Model 120 present | NO -- must synthesize |
| Model 123 present | NO -- must synthesize |
| Model 704 present | YES (bonus finding) |

**Overall: PASS** -- All documented register addresses and layouts match the live SE30K. The proxy design assumptions are validated.
