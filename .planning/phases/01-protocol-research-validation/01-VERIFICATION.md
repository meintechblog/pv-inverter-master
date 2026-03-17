---
phase: 01-protocol-research-validation
verified: 2026-03-18T12:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 1: Protocol Research & Validation Verification Report

**Phase Goal:** All protocol unknowns are resolved and a validated register mapping specification exists
**Verified:** 2026-03-18
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | dbus-fronius discovery requirements are formally documented with exact register addresses, manufacturer string, model chain, and unit ID | VERIFIED | `docs/dbus-fronius-expectations.md` — 6-section document covering Discovery Flow, Required Models (1/103/120/123/0xFFFF), Unit ID 126, Fronius-specific behaviors, Protocol Details, and a 6-item proxy emulation checklist. Contains all required strings: `C_Manufacturer`, `unit ID 126`, `Model 120`, `Model 123`, `0xFFFF`, `## What the Proxy Must Emulate`. |
| 2 | SolarEdge SE30K registers have been read live via Modbus TCP and the actual register layout matches or has been reconciled with documentation | VERIFIED | `docs/se30k-validation-results.md` — Live run at 2026-03-17T23:43:56Z. All 5 test sections PASS: SunSpec Header "SunS", Common Model DID=1/Length=65/Mfr="SolarEdge", Inverter Model DID=103/Length=50, Model chain walked (15 models found), Model 120/123 confirmed absent. Discrepancies documented and reconciled. |
| 3 | A complete register mapping table exists that translates every needed SolarEdge register to its Fronius SunSpec equivalent including scale factors | VERIFIED | `docs/register-mapping-spec.md` — Covers all 176 proxy registers (40000-40176) with register-by-register tables for Common Model, Inverter Model 103 (50 data registers), Model 120 synthesis (26 registers), Model 123 write translation to 0xF300/0xF322 (Float32 encoding), and Scale Factor Reference. Contains `40000`, `SunS`, `C_Manufacturer`, `WRtg = 30000`, `0xF322`, `Float32`, `0xF300`, `actual_value = raw_value`. |
| 4 | Unit tests verify the translation table's correctness (scale factor handling, identity substitution, model chain structure) | VERIFIED | `tests/test_register_mapping.py` — 27 tests, 27 passed, 0 failed. Covers: `test_sunspec_header`, `test_common_model_manufacturer_substitution`, `test_model_chain_structure`, `test_model_120_synthesis`, `test_model_123_write_mapping`, `test_scale_factor`, `test_end_marker`. Pytest exit code 0. |
| 5 | Project scaffolding provides pymodbus and pytest dependencies | VERIFIED | `pyproject.toml` contains `name = "venus-os-fronius-proxy"`, `pymodbus>=3.6,<4.0`, `pytest>=8.0`, `[tool.pytest.ini_options]`, `testpaths = ["tests"]`. `requirements.txt` contains `pymodbus>=3.6,<4.0`, `pytest>=8.0`, `pytest-asyncio>=0.23`. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Project config with pymodbus and pytest deps | VERIFIED | Contains `pymodbus>=3.6,<4.0`, `pytest>=8.0`, `[tool.pytest.ini_options]` |
| `requirements.txt` | Pip-installable dependency list | VERIFIED | Contains all three required packages |
| `docs/dbus-fronius-expectations.md` | Formal dbus-fronius expectations document | VERIFIED | 132 lines, all required sections and strings present |
| `docs/register-mapping-spec.md` | Complete register mapping specification | VERIFIED | 275 lines, register-by-register tables for all 5 model sections |
| `tests/test_register_mapping.py` | Unit tests for register mapping | VERIFIED | 318 lines, 27 test functions, all pass |
| `scripts/validate_se30k.py` | Live Modbus TCP validation script | VERIFIED | 303 lines, contains `ModbusTcpClient`, `192.168.3.18`, all 5 check sections, valid Python syntax |
| `docs/se30k-validation-results.md` | Captured live validation output | VERIFIED | Contains "SunSpec Header", full model chain output, analysis and reconciliation table |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_register_mapping.py` | `docs/register-mapping-spec.md` | Tests verify same register addresses (40004, 40069, 40121, 40149, 40175) and values documented in spec | WIRED | All spec constants (CONTROLS_WMAXLIMPCT=40154, CONTROLS_WMAXLIM_ENA=40158, NAMEPLATE_WRTG_ADDR=40124, END_ADDR=40175) match spec tables exactly. Test assertions on WRtg=30000, DERTyp=4, WMaxLimPct 5000*10^-2=50.0%, 0xF322=62242, 0xF300=62208 all confirmed by passing tests. |
| `scripts/validate_se30k.py` | SolarEdge SE30K at 192.168.3.18:1502 | `ModbusTcpClient.read_holding_registers` at 40000, 40002, 40069 | WIRED | Script reads `read_holding_registers(40000, count=2)`, `read_holding_registers(40002, count=67)`, `read_holding_registers(40069, count=2)`, `read_holding_registers(40071, count=inv_length)`. Live output captured in `docs/se30k-validation-results.md` confirms successful execution. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROTO-01 | 01-01-PLAN.md | dbus-fronius Source Code analysiert -- exakte Fronius-Erwartungen (Discovery, Manufacturer-String, SunSpec Models) dokumentiert | SATISFIED | `docs/dbus-fronius-expectations.md` formally documents discovery flow, required models (1/103/120/123), unit ID 126, Fronius-specific behaviors, and proxy emulation checklist. REQUIREMENTS.md traceability table shows "Complete". |
| PROTO-02 | 01-02-PLAN.md | SolarEdge SE30K Register-Map per Modbus TCP live ausgelesen und validiert | SATISFIED | `docs/se30k-validation-results.md` contains complete live run output. All critical checks PASS. Model chain fully walked. Discrepancies (model chain richer than expected, Model 704 discovered) documented and reconciled. NOTE: REQUIREMENTS.md checklist item still shows `[ ]` and traceability table shows "Pending" -- the metadata was not updated after completion, but the deliverable work is done. |
| PROTO-03 | 01-01-PLAN.md | Register-Mapping-Spezifikation erstellt (SolarEdge -> Fronius SunSpec Translation Table) | SATISFIED | `docs/register-mapping-spec.md` provides complete register-by-register translation. 27 unit tests in `tests/test_register_mapping.py` all pass. REQUIREMENTS.md traceability table shows "Complete". |

**Note on PROTO-02 metadata:** REQUIREMENTS.md has PROTO-02 marked `[ ]` (unchecked) and "Pending" in the traceability table. The 01-02-SUMMARY.md marks it completed and commit `6e33e26` exists with the deliverable files. The underlying requirement is satisfied by the evidence; the REQUIREMENTS.md metadata was not updated after the plan executed.

---

### Anti-Patterns Found

No anti-patterns detected. Scanned `docs/`, `tests/`, and `scripts/` for TODO, FIXME, XXX, HACK, PLACEHOLDER, stub return values, and empty implementations. Zero matches.

---

### Human Verification Required

#### 1. PROTO-02 Daytime Power Readings

**Test:** Run `python3 scripts/validate_se30k.py` during daylight hours when the SE30K is producing power (Status=MPPT or THROTTLED).
**Expected:** Non-zero AC Power, DC Voltage ~300-800V, AC Current > 0A, Status = 4 (MPPT) or 5 (THROTTLED).
**Why human:** Live validation was run at nighttime (Status=SLEEPING, all power readings zero). The plausibility of power register scale factors can only be confirmed during active generation. The sleeping validation is sufficient for PROTO-02 goal achievement, but a daytime run would provide complete confidence.

#### 2. PROTO-01 dbus-fronius Source Code Basis

**Test:** Verify the claims in `docs/dbus-fronius-expectations.md` against the actual dbus-fronius source code at https://github.com/victronenergy/dbus-fronius (sunspec_detector.cpp, sunspec_updater.cpp).
**Expected:** Discovery flow, manufacturer matching strings, and model chain walk logic match what is documented.
**Why human:** Research was based on source code analysis; cannot programmatically verify against the live GitHub repo. Confidence is rated HIGH in the research document but cannot be confirmed without reading the actual source files.

---

## Gaps Summary

No gaps. All five observable truths are verified. All artifacts exist and are substantive (non-stub). All key links are wired. All three phase requirements (PROTO-01, PROTO-02, PROTO-03) have supporting evidence.

The only minor finding is a documentation hygiene issue: REQUIREMENTS.md has PROTO-02 unchecked while the work is complete. This does not constitute a gap in goal achievement — it is a metadata update that was missed after plan execution.

---

_Verified: 2026-03-18_
_Verifier: Claude (gsd-verifier)_
