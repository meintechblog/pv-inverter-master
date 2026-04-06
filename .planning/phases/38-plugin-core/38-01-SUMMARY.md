---
phase: 38-plugin-core
plan: 01
subsystem: plugins
tags: [sungrow, modbus-tcp, sunspec, plugin, tdd]
dependency_graph:
  requires: []
  provides: [SungrowPlugin, sungrow-poll, sungrow-sunspec-encoding]
  affects: [aggregation, device-registry, power-limit-distributor]
tech_stack:
  added: []
  patterns: [modbus-fc04-input-registers, sungrow-state-mapping, 3-phase-sunspec-encoding]
key_files:
  created:
    - src/pv_inverter_proxy/plugins/sungrow.py
    - tests/test_sungrow_plugin.py
  modified: []
decisions:
  - "FC04 input registers for Sungrow (not FC03 holding registers like SolarEdge)"
  - "MPPT1 as primary DC voltage channel for SunSpec, DC currents summed from both MPPTs"
  - "Value clamping on all parsed register data (T-38-02 threat mitigation)"
  - "write_power_limit as safe no-op returning success (Phase 41 adds real control)"
metrics:
  duration: 314s
  completed: "2026-04-06T08:59:49Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 40
---

# Phase 38 Plan 01: SungrowPlugin Core Implementation Summary

SungrowPlugin implementing InverterPlugin ABC with Modbus TCP FC04 polling of Sungrow SG-RT input registers 5002-5037, SunSpec Model 103 encoding with native 3-phase data, state code mapping, and proportional ThrottleCaps declaration.

## What Was Done

### Task 1: Write failing tests for SungrowPlugin (TDD RED)
- Created `tests/test_sungrow_plugin.py` with 40 test functions across 11 test classes
- Covers: plugin interface, connect, poll (FC04), Sungrow register parsing, SunSpec encoding, 3-phase verification, state code mapping, reconfigure, ThrottleCaps, write_power_limit no-op, common registers, Model 120
- Tests verified to fail with ModuleNotFoundError (RED phase)
- Commit: `1b6c21c`

### Task 2: Implement SungrowPlugin (TDD GREEN)
- Created `src/pv_inverter_proxy/plugins/sungrow.py` (~260 lines)
- `poll()` uses `read_input_registers` (FC04) at wire address 5002, count=36
- `_parse_sungrow_data()` converts raw registers with Sungrow scale factors (0.1V, 0.1A, 0.1Hz, 0.1degC, 0.1kWh) to physical values
- `_encode_model_103()` produces 52 SunSpec registers with all 3 AC phases populated
- `SUNGROW_STATE_TO_SUNSPEC` maps: 0x8000->MPPT, 0x0000->OFF, 0x1300->STANDBY, 0x8100->THROTTLED, 0x5500->FAULT, unknown->SLEEPING
- `throttle_capabilities` returns proportional mode with 2.0s response time
- `write_power_limit()` returns WriteResult(success=True) as safe no-op
- Value clamping on all parsed data (voltage 0-1000V, current 0-200A, power 0-50kW, temp -40 to 100C)
- All 40 tests pass, SolarEdge plugin tests also pass (no regressions)
- Commit: `a274e29`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed U32 sample data in tests**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Plan specified `raw[14]=4000, raw[15]=0` for "total DC power = 4000W" but with U32 high-word-first encoding this yields `(4000<<16)|0 = 262144000W`. Same for total active power.
- **Fix:** Swapped to `raw[14]=0, raw[15]=4000` and `raw[28]=0, raw[29]=3900` so U32 decoding produces correct values.
- **Files modified:** tests/test_sungrow_plugin.py
- **Commit:** a274e29

**2. [Rule 1 - Bug] Fixed energy calculation in test expectations**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Plan said energy = `(100<<16|0)*0.1 = 655.36 kWh` but code converts 0.1kWh to Wh by multiplying by 100, giving `6553600*100 = 655360000 Wh`.
- **Fix:** Updated test expectations and comments to match correct math.
- **Files modified:** tests/test_sungrow_plugin.py
- **Commit:** a274e29

**3. [Rule 2 - Security] Added value clamping (T-38-02 mitigation)**
- **Found during:** Task 2 implementation
- **Issue:** Threat model T-38-02 requires clamping untrusted register values to sane ranges.
- **Fix:** Added `_clamp()` helper and applied to all parsed values (voltage, current, power, temperature).
- **Files modified:** src/pv_inverter_proxy/plugins/sungrow.py
- **Commit:** a274e29

## Decisions Made

1. **FC04 for Sungrow input registers** -- Sungrow uses input registers (3x type), not holding registers (4x type) like SolarEdge. Using `read_input_registers()` not `read_holding_registers()`.
2. **MPPT1 as primary DC voltage** -- SunSpec Model 103 has one DC voltage field. Using MPPT1 voltage, summing currents from both MPPTs.
3. **Value clamping** -- Applied per threat model T-38-02 to protect against corrupted register values from the Modbus device.
4. **write_power_limit no-op** -- Phase 38 is read-only. Returns success without writing. Phase 41 will add real Sungrow power control.

## Verification Results

| Check | Result |
|-------|--------|
| `python -m pytest tests/test_sungrow_plugin.py -x -q` | 40 passed |
| `python -m pytest tests/test_solaredge_plugin.py -x -q` | 17 passed (no regression) |
| `grep -c "class SungrowPlugin" sungrow.py` | 1 |
| `grep "read_input_registers" sungrow.py` | Found (FC04) |
| `grep "read_holding_registers" sungrow.py` | Not found (anti-pattern absent) |

## Known Stubs

None -- all functionality required by this plan is fully implemented and wired.

## Self-Check: PASSED

All files exist, all commits verified.
