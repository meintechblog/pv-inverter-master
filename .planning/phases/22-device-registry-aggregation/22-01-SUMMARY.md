---
phase: 22-device-registry-aggregation
plan: 01
subsystem: core
tags: [asyncio, device-management, poll-loop, backoff, lifecycle]

# Dependency graph
requires:
  - phase: 21-data-model-opendtu-plugin
    provides: "InverterEntry, Config, plugin_factory, ConnectionManager, AppContext, DeviceState"
provides:
  - "DeviceRegistry class with start/stop/enable/disable per-device lifecycle"
  - "ManagedDevice dataclass for tracking device + poll task"
  - "_device_poll_loop async function for per-device polling"
affects: [22-02-aggregation-layer, 23-multi-inverter-proxy, 24-frontend-multi-device]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-device-asyncio-tasks, lazy-imports-for-compat]

key-files:
  created:
    - src/venus_os_fronius_proxy/device_registry.py
    - tests/test_device_registry.py
  modified: []

key-decisions:
  - "Lazy imports for plugin_factory and DashboardCollector to avoid Python 3.9 timeseries.py slots= incompatibility"
  - "Poll loop stores raw poll data on DeviceState but defers cache writes and aggregation to Plan 02"
  - "enable_device/disable_device delegate to start_device/stop_device for simplicity"

patterns-established:
  - "Per-device asyncio tasks: each device gets independent poll task via asyncio.create_task with name=poll-{id}"
  - "Lazy module imports: use local imports inside methods when top-level import chain has version incompatibilities"

requirements-completed: [REG-01, REG-02, REG-03]

# Metrics
duration: 5min
completed: 2026-03-20
---

# Phase 22 Plan 01: DeviceRegistry Summary

**Per-device asyncio poll lifecycle manager with independent ConnectionManager backoff, task leak prevention, and runtime enable/disable**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T19:46:31Z
- **Completed:** 2026-03-20T19:51:46Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments
- DeviceRegistry class managing N inverter devices with independent asyncio poll tasks
- Per-device isolation: each device gets its own ConnectionManager, DashboardCollector, poll_counter
- Clean lifecycle: start_device creates plugin + task, stop_device cancels + closes + removes
- No asyncio task leaks verified across 5 start/stop cycles
- CancelledError properly propagated (not swallowed by except Exception)
- 10 comprehensive tests covering all lifecycle scenarios

## Task Commits

Each task was committed atomically (TDD):

1. **Task 1 RED: Failing tests** - `156ca38` (test)
2. **Task 1 GREEN: DeviceRegistry implementation** - `f49c660` (feat)

## Files Created/Modified
- `src/venus_os_fronius_proxy/device_registry.py` - DeviceRegistry class with ManagedDevice, _device_poll_loop (238 lines)
- `tests/test_device_registry.py` - 10 tests covering lifecycle, backoff, callbacks, task leaks (306 lines)

## Decisions Made
- Lazy imports for plugin_factory and DashboardCollector inside start_device() to avoid Python 3.9 timeseries.py `@dataclass(slots=True)` incompatibility
- Poll loop stores raw poll data on DeviceState but defers cache writes, common translation, and night mode injection to AggregationLayer (Plan 02)
- enable_device/disable_device are thin wrappers around start/stop for API clarity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy imports to avoid Python 3.9 import chain failure**
- **Found during:** Task 1 GREEN (implementation)
- **Issue:** Top-level `from venus_os_fronius_proxy.dashboard import DashboardCollector` triggers `timeseries.py` which uses `@dataclass(slots=True)` (Python 3.10+), breaking on Python 3.9
- **Fix:** Moved plugin_factory and DashboardCollector imports to lazy local imports inside start_device(). Tests pre-mock the dashboard module via sys.modules.
- **Files modified:** device_registry.py, test_device_registry.py
- **Verification:** All 10 tests pass on Python 3.9
- **Committed in:** f49c660

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Import compatibility fix required for correctness. No scope creep.

## Issues Encountered
None beyond the import chain fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DeviceRegistry ready for integration with AggregationLayer (Plan 02)
- Plan 02 will add cache writes, common translation, and aggregated register merging
- No blockers

---
*Phase: 22-device-registry-aggregation*
*Completed: 2026-03-20*
