---
phase: 03-control-path-production-hardening
plan: 02
subsystem: connection
tags: [reconnection, backoff, night-mode, state-machine, resilience]

# Dependency graph
requires:
  - phase: 03-control-path-production-hardening
    provides: "ControlState, write_power_limit, StalenessAwareSlaveContext, _poll_loop"
provides:
  - "ConnectionManager state machine with exponential backoff (5s-60s)"
  - "ConnectionState enum: CONNECTED, RECONNECTING, NIGHT_MODE"
  - "Night mode synthetic register injection with SLEEPING status"
  - "Automatic power limit restore after night mode reconnect"
  - "build_night_mode_inverter_registers for synthetic Model 103 data"
affects: [03-03, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [state machine for connection lifecycle, injectable time for testing, night mode register synthesis]

key-files:
  created:
    - src/venus_os_fronius_proxy/connection.py
    - tests/test_connection.py
  modified:
    - src/venus_os_fronius_proxy/proxy.py
    - src/venus_os_fronius_proxy/plugins/solaredge.py

key-decisions:
  - "conn_mgr and control_state parameters default to None in _poll_loop for backward compatibility with existing tests"
  - "Night mode forces cache freshness (last_successful_poll + _has_been_updated) to prevent staleness from overriding night mode registers"
  - "SolarEdgePlugin.close() sets self._client = None to enable clean reconnection cycle"

patterns-established:
  - "Injectable time parameter (now: float) for deterministic state machine testing without real timers"
  - "ConnectionManager.reconnected_from_night as consumable flag (resets after read)"

requirements-completed: [DEPL-02, DEPL-03]

# Metrics
duration: 5min
completed: 2026-03-18
---

# Phase 03 Plan 02: Reconnection and Night Mode Summary

**ConnectionManager state machine with exponential backoff (5s-60s), night mode after 5-min failure serving synthetic SLEEPING registers, and automatic power limit restore on reconnect**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-18T09:42:33Z
- **Completed:** 2026-03-18T09:47:27Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ConnectionManager state machine: CONNECTED -> RECONNECTING -> NIGHT_MODE with exponential backoff 5s to 60s
- Night mode activates after 5 minutes of continuous failure, injects synthetic Model 103 registers with SLEEPING (4) status and preserved energy
- Automatic power limit restore via plugin.write_power_limit when reconnecting from night mode with active control state
- SolarEdgePlugin close/reconnect cycle fixed (self._client = None)
- All 147 tests pass including 19 new connection tests (16 unit + 3 integration)

## Task Commits

Each task was committed atomically:

1. **Task 1: ConnectionManager state machine (TDD)** - `6e49f47` (test: RED) + `e0aed19` (feat: GREEN)
2. **Task 2: Proxy poll loop integration** - `b9642a7` (feat)

_Note: Task 1 used TDD with separate test and implementation commits_

## Files Created/Modified
- `src/venus_os_fronius_proxy/connection.py` - ConnectionManager state machine, ConnectionState enum, build_night_mode_inverter_registers
- `src/venus_os_fronius_proxy/proxy.py` - Poll loop integrated with ConnectionManager, night mode register injection, power limit restore
- `src/venus_os_fronius_proxy/plugins/solaredge.py` - close() sets self._client = None for reconnection
- `tests/test_connection.py` - 16 unit tests + 3 async integration tests for backoff, night mode, reconnect

## Decisions Made
- Made conn_mgr and control_state optional (None default) in _poll_loop to maintain backward compatibility with all existing Phase 2 and 3 tests
- Night mode forces cache freshness by writing last_successful_poll and _has_been_updated directly, preventing staleness timeout from overriding night mode's synthetic registers
- SolarEdgePlugin.close() now sets self._client = None so that connect() creates a fresh client on reconnection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Reconnection and night mode complete, ready for Phase 03 Plan 03 (structured logging and observability)
- ConnectionManager integrated into poll loop, all state transitions tested
- Power limit restore ensures control state survives night mode transitions

---
*Phase: 03-control-path-production-hardening*
*Completed: 2026-03-18*
