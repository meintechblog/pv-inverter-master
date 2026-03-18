---
phase: 06-live-dashboard
plan: 01
subsystem: infra
tags: [websocket, aiohttp, real-time, push]

# Dependency graph
requires:
  - phase: 05-data-pipeline
    provides: DashboardCollector, TimeSeriesBuffer, shared_ctx pattern
provides:
  - /ws WebSocket endpoint with snapshot + history on connect
  - broadcast_to_clients function for poll-loop integration
  - Dead client cleanup via WeakSet + discard pattern
  - shared_ctx["webapp"] bridge between proxy and webapp
affects: [06-02-live-dashboard, 07-power-control]

# Tech tracking
tech-stack:
  added: []
  patterns: [WebSocket push via aiohttp native ws, monotonic-to-wallclock timestamp conversion, downsample with slice step]

key-files:
  created:
    - tests/test_websocket.py
  modified:
    - src/venus_os_fronius_proxy/webapp.py
    - src/venus_os_fronius_proxy/proxy.py
    - src/venus_os_fronius_proxy/__main__.py

key-decisions:
  - "Use plain set for ws_clients in tests, WeakSet in production create_webapp"
  - "Downsample history with [::10] slice step (simple, deterministic)"
  - "Late import of broadcast_to_clients in proxy.py to avoid circular dependency"
  - "Send all buffer keys in history message (not just ac_power_w) for future use"

patterns-established:
  - "WebSocket broadcast pattern: serialize once, iterate clients, discard on error"
  - "Monotonic-to-wallclock conversion: offset = time.time() - time.monotonic()"

requirements-completed: [INFRA-01]

# Metrics
duration: 2min
completed: 2026-03-18
---

# Phase 6 Plan 1: WebSocket Push Infrastructure Summary

**aiohttp WebSocket endpoint at /ws with snapshot+history on connect, poll-loop broadcast, and dead-client cleanup**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-18T16:13:51Z
- **Completed:** 2026-03-18T16:15:57Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- WebSocket handler at /ws sends latest snapshot immediately on connect
- Downsampled history (all 6 time-series buffers) sent as second message on connect
- broadcast_to_clients pushes snapshots to all connected clients after each poll cycle
- Dead/disconnected clients automatically cleaned up without errors
- Full TDD cycle: 5 failing tests (RED) then all passing (GREEN)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create WebSocket test suite (RED phase)** - `f9e30aa` (test)
2. **Task 2: Implement WebSocket handler, broadcast, and wire into proxy (GREEN phase)** - `07a5421` (feat)

## Files Created/Modified
- `tests/test_websocket.py` - 5 WebSocket integration tests (snapshot, history, broadcast, dead-client, no-collector)
- `src/venus_os_fronius_proxy/webapp.py` - Added ws_handler, broadcast_to_clients, /ws route, ws_clients WeakSet
- `src/venus_os_fronius_proxy/proxy.py` - Added broadcast_to_clients call after dashboard_collector.collect()
- `src/venus_os_fronius_proxy/__main__.py` - Store runner.app in shared_ctx["webapp"]

## Decisions Made
- Used plain `set()` for ws_clients in test fixtures (WeakSet in production via create_webapp)
- Downsample with `[::10]` step -- simple and deterministic for sparklines
- Late import of broadcast_to_clients in proxy.py following existing DashboardCollector pattern
- Send all 6 buffer keys in history message for future dashboard widgets

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- /ws endpoint ready for frontend JavaScript WebSocket client in Plan 02
- History message provides all 6 metrics for sparkline charts
- broadcast_to_clients automatically pushes after each poll cycle

---
*Phase: 06-live-dashboard*
*Completed: 2026-03-18*

## Self-Check: PASSED
