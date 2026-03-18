---
phase: 02-core-proxy-read-path
plan: 01
subsystem: proxy
tags: [sunspec, modbus, pymodbus, abc, dataclass, register-cache]

# Dependency graph
requires:
  - phase: 01-protocol-research-validation
    provides: register-mapping-spec.md, dbus-fronius-expectations.md, 27 mapping tests
provides:
  - InverterPlugin ABC defining brand plugin contract (5 abstract methods)
  - PollResult dataclass for poll results (common_registers, inverter_registers, success, error)
  - SunSpec static model chain builder (177 registers matching register-mapping-spec.md)
  - apply_common_translation() for identity substitution
  - RegisterCache with staleness tracking wrapping ModbusSequentialDataBlock
  - Package scaffolding at src/venus_os_fronius_proxy/
affects: [02-02-proxy-server-and-polling, 03-power-control-write-path]

# Tech tracking
tech-stack:
  added: [pymodbus.datastore.ModbusSequentialDataBlock]
  patterns: [ABC plugin interface, TDD red-green, cache-with-staleness, from __future__ import annotations for Python 3.9 compat]

key-files:
  created:
    - src/venus_os_fronius_proxy/__init__.py
    - src/venus_os_fronius_proxy/plugin.py
    - src/venus_os_fronius_proxy/plugins/__init__.py
    - src/venus_os_fronius_proxy/sunspec_models.py
    - src/venus_os_fronius_proxy/register_cache.py
    - tests/test_plugin.py
    - tests/test_sunspec_models.py
    - tests/test_register_cache.py
  modified: []

key-decisions:
  - "Used from __future__ import annotations for Python 3.9 compatibility (str | None syntax not supported at runtime)"
  - "RegisterCache uses time.monotonic() for staleness tracking (not wall clock)"

patterns-established:
  - "Plugin interface via ABC with async connect/poll/close lifecycle"
  - "Static register layout defined in sunspec_models.py, dynamic data via cache updates"
  - "PYTHONPATH=src for running tests without pip install -e"

requirements-completed: [PROXY-02, PROXY-04, PROXY-05, PROXY-07, PROXY-08, ARCH-01, ARCH-02]

# Metrics
duration: 4min
completed: 2026-03-18
---

# Phase 2 Plan 1: Foundation Modules Summary

**InverterPlugin ABC, SunSpec 177-register model chain builder, and RegisterCache with 30s staleness tracking using pymodbus datablock**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-18T07:24:47Z
- **Completed:** 2026-03-18T07:28:39Z
- **Tasks:** 3
- **Files created:** 8

## Accomplishments
- InverterPlugin ABC with 5 abstract methods defining the brand plugin contract (connect, poll, get_static_common_overrides, get_model_120_registers, close)
- build_initial_registers() produces exactly 177 uint16 values with correct SunSpec header, Common Model identity, Model 103 placeholder, Model 120 nameplate synthesis (including negative int16 values), Model 123 header, and End marker
- RegisterCache wraps ModbusSequentialDataBlock with staleness detection (starts stale, resets on update, configurable timeout)
- 48 new tests (12 plugin + 28 sunspec + 8 cache) all passing alongside 27 existing mapping tests = 75 total

## Task Commits

Each task was committed atomically:

1. **Task 1: Package scaffolding and plugin interface contract** - `fb9442f` (feat)
2. **Task 2: SunSpec static model chain builder** - `24280d7` (feat)
3. **Task 3: Register cache with staleness tracking** - `caee0cb` (feat)

_All tasks followed TDD: RED (failing test) -> GREEN (implementation)_

## Files Created/Modified
- `src/venus_os_fronius_proxy/__init__.py` - Package marker
- `src/venus_os_fronius_proxy/plugin.py` - InverterPlugin ABC and PollResult dataclass
- `src/venus_os_fronius_proxy/plugins/__init__.py` - Plugin subpackage marker
- `src/venus_os_fronius_proxy/sunspec_models.py` - Static SunSpec model chain builder with address constants
- `src/venus_os_fronius_proxy/register_cache.py` - Cache wrapper with staleness tracking
- `tests/test_plugin.py` - 12 tests for ABC contract and PollResult fields
- `tests/test_sunspec_models.py` - 28 tests for register layout, encoding, translation
- `tests/test_register_cache.py` - 8 tests for staleness lifecycle and datablock writes

## Decisions Made
- Used `from __future__ import annotations` for Python 3.9 compatibility since `str | None` union syntax is not supported at runtime in 3.9
- Used `time.monotonic()` for staleness tracking rather than wall clock time (immune to system clock changes)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `from __future__ import annotations` for Python 3.9 compat**
- **Found during:** Task 1 (plugin.py)
- **Issue:** Python 3.9 does not support `str | None` union syntax at runtime in dataclass fields
- **Fix:** Added `from __future__ import annotations` to defer type evaluation
- **Files modified:** src/venus_os_fronius_proxy/plugin.py
- **Verification:** Import succeeds, all tests pass
- **Committed in:** fb9442f (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor syntax adaptation for Python 3.9 runtime. No scope change.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three foundation modules ready for Plan 02 (proxy server + polling)
- InverterPlugin ABC defines the contract the SolarEdge plugin will implement
- build_initial_registers() provides the initial datablock for ModbusTcpServer
- RegisterCache provides the staleness-tracked wrapper for the poller to update
- 75 tests provide regression safety for Plan 02 development

## Self-Check: PASSED

All 8 files verified present. All 3 task commits verified in git log.

---
*Phase: 02-core-proxy-read-path*
*Completed: 2026-03-18*
