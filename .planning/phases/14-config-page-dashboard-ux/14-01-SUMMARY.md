---
phase: 14-config-page-dashboard-ux
plan: 01
subsystem: api
tags: [aiohttp, mqtt, config, hot-reload, venus-os]

# Dependency graph
requires:
  - phase: 13-mqtt-config-backend
    provides: VenusConfig dataclass, validate_venus_config, venus_mqtt_loop
provides:
  - Nested config API format {inverter: {...}, venus: {...}}
  - Venus MQTT hot-reload on config change
  - Real venus_mqtt_connected status in /api/status
affects: [14-02-frontend-config-page]

# Tech tracking
tech-stack:
  added: []
  patterns: [nested config API response, venus MQTT task lifecycle management]

key-files:
  created: []
  modified:
    - src/venus_os_fronius_proxy/webapp.py
    - tests/test_webapp.py

key-decisions:
  - "Venus config change detection via tuple comparison of (host, port, portal_id)"
  - "asyncio.ensure_future for venus_mqtt_loop task creation on config save"
  - "Three-state venus status: connected/disconnected/not configured based on shared_ctx key presence"

patterns-established:
  - "Nested config API: GET/POST /api/config uses {inverter: {...}, venus: {...}} format"
  - "Hot-reload pattern: cancel old task, start new one via asyncio.ensure_future"

requirements-completed: [CFG-01, CFG-02]

# Metrics
duration: 3min
completed: 2026-03-19
---

# Phase 14 Plan 01: Venus Config API Summary

**Extended webapp API to serve/save venus config in nested format, hot-reload MQTT on change, and report real connection state**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T18:31:24Z
- **Completed:** 2026-03-19T18:34:48Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Config GET/POST endpoints now return and accept nested {inverter, venus} format
- Venus config changes trigger MQTT hot-reload (cancel old task, start new venus_mqtt_loop)
- Status endpoint reports real venus_mqtt_connected state instead of hardcoded "active"
- 6 new tests added, 2 existing tests updated for new format

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for venus config API** - `8e7e48d` (test)
2. **Task 1 GREEN: Implement venus config handlers** - `ac0f088` (feat)

## Files Created/Modified
- `src/venus_os_fronius_proxy/webapp.py` - Extended config_get_handler, config_save_handler, status_handler; added venus_mqtt_loop and validate_venus_config imports
- `tests/test_webapp.py` - Added 6 new tests for venus config GET/POST/hot-reload/status; updated 2 existing tests for nested format

## Decisions Made
- Venus config change detected by comparing old vs new (host, port, portal_id) tuples
- asyncio.ensure_future used to spawn new venus_mqtt_loop task (consistent with existing codebase patterns)
- Three-state venus status: "connected" (True), "disconnected" (False), "not configured" (key absent)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failures in test_power_limit_set_valid and test_power_limit_venus_override_rejection (wmaxlimpct_raw assertion mismatch) -- not caused by this plan's changes, logged as out-of-scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Backend API ready for Plan 02 (frontend config page) to consume
- GET /api/config provides both inverter and venus sections
- POST /api/config accepts nested format with automatic MQTT reload
- Status endpoint provides real-time venus connection state for UI bobbles

---
*Phase: 14-config-page-dashboard-ux*
*Completed: 2026-03-19*
