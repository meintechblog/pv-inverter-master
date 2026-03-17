---
phase: 01-protocol-research-validation
plan: 01
subsystem: protocol
tags: [sunspec, modbus, dbus-fronius, register-mapping, solaredge, fronius]

# Dependency graph
requires:
  - phase: none
    provides: first plan in project
provides:
  - Project scaffolding (pyproject.toml, requirements.txt)
  - Formal dbus-fronius expectations document (PROTO-01)
  - Complete register mapping specification (PROTO-03)
  - 27 passing unit tests for register mapping correctness
affects: [01-02, 02-core-proxy]

# Tech tracking
tech-stack:
  added: [pymodbus, pytest, pytest-asyncio]
  patterns: [sunspec-model-chain, integer-scale-factor-encoding, cache-based-proxy]

key-files:
  created:
    - pyproject.toml
    - requirements.txt
    - docs/dbus-fronius-expectations.md
    - docs/register-mapping-spec.md
    - tests/test_register_mapping.py
  modified: []

key-decisions:
  - "Model chain addresses recalculated from actual SunSpec model lengths: Model 120 = 26 regs, Model 123 = 24 regs, giving Controls at 40149 and End at 40175"
  - "Model 123 field layout uses standard SunSpec ordering: WMaxLimPct at 40154, WMaxLim_Ena at 40158"

patterns-established:
  - "Register address calculation: next_model_addr = prev_addr + 2 (header) + length (data)"
  - "Translation types: STATIC, REPLACED, PASSTHROUGH, SYNTHESIZED, TRANSLATED"
  - "Power control write sequence: enable 0xF300 first, then set 0xF322"

requirements-completed: [PROTO-01, PROTO-03]

# Metrics
duration: 5min
completed: 2026-03-18
---

# Phase 1 Plan 1: Project Scaffolding and Protocol Specs Summary

**SunSpec register mapping spec with 27 unit tests covering model chain structure, Fronius identity substitution, Model 120 synthesis, and Model 123 write translation to SolarEdge proprietary registers**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-17T23:32:52Z
- **Completed:** 2026-03-17T23:38:33Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Project scaffolded with pymodbus and pytest dependencies
- dbus-fronius expectations formally documented: discovery flow, required SunSpec models (1, 103, 120, 123), unit ID 126, Fronius-specific behaviors, and a 6-item proxy emulation checklist
- Complete register mapping specification covering all 176 proxy registers from 40000 to 40176, with translation type (STATIC/REPLACED/PASSTHROUGH/SYNTHESIZED/TRANSLATED) for every field
- 27 unit tests passing: model chain addresses, manufacturer substitution, Model 103 passthrough, Model 120 synthesis values, Model 123 write translation to SE proprietary registers, scale factor math, end marker

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding and dbus-fronius expectations document** - `d710bf1` (feat)
2. **Task 2: Register mapping specification and unit tests** - `4433513` (feat)

## Files Created/Modified
- `pyproject.toml` - Python project config with pymodbus and pytest dependencies
- `requirements.txt` - Pip-installable dependency list for LXC deployment
- `docs/dbus-fronius-expectations.md` - Formal PROTO-01 deliverable: what Venus OS expects from a Fronius inverter
- `docs/register-mapping-spec.md` - Formal PROTO-03 deliverable: register-by-register translation table
- `tests/__init__.py` - Test package init
- `tests/test_register_mapping.py` - 27 unit tests verifying specification correctness

## Decisions Made
- Recalculated model chain addresses from actual SunSpec model lengths (Model 120 = 26 registers, not 28 as assumed in RESEARCH.md). This moves Model 123 to 40149 and End Marker to 40175 instead of the research document's 40151/40179.
- Used standard SunSpec Model 123 field ordering for proxy register layout, placing WMaxLimPct at 40154 and WMaxLim_Ena at 40158.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Python 3.9.6 on macOS lacks `tomllib` module (added in 3.11). Used grep-based verification as fallback for pyproject.toml validation. Not a problem since the project targets Python >= 3.11 on the LXC.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Protocol specifications are complete and tested, ready for Plan 01-02 (live SE30K register validation)
- pyproject.toml and test infrastructure in place for all future development
- Register addresses and translation rules are formally specified, providing the blueprint for proxy implementation in Phase 2

## Self-Check: PASSED

All 6 files verified present. Both task commits (d710bf1, 4433513) found in git log.

---
*Phase: 01-protocol-research-validation*
*Completed: 2026-03-18*
