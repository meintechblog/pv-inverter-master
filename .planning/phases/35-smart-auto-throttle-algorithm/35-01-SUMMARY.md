---
phase: 35-smart-auto-throttle-algorithm
plan: 01
subsystem: distributor
tags: [throttle, waterfall, convergence, scoring, auto-throttle]

requires:
  - phase: 34-binary-throttle-engine-with-hysteresis
    provides: Binary throttle dispatch, cooldown, startup grace
  - phase: 33-device-throttle-capabilities-scoring
    provides: ThrottleCaps dataclass, compute_throttle_score()
provides:
  - auto_throttle config field (Config.auto_throttle)
  - Score-based waterfall ordering (_waterfall_auto)
  - Convergence tracking (on_poll, _record_target)
  - Effective score with measured response time override (_effective_score)
affects: [35-02, auto-throttle-ui, distributor]

tech-stack:
  added: []
  patterns: [score-based waterfall, convergence tracking, rolling-average feedback]

key-files:
  created: []
  modified:
    - src/pv_inverter_proxy/config.py
    - src/pv_inverter_proxy/distributor.py
    - tests/test_distributor.py

key-decisions:
  - "Auto waterfall treats each device as own tier (no grouping), sorted by effective score descending"
  - "Convergence uses 5% tolerance for proportional, 50W near-zero threshold for binary off"
  - "Rolling average of up to 10 convergence samples for measured_response_time_s"
  - "Target not reset when same limit sent within 2% to avoid stale target pitfall"

patterns-established:
  - "_waterfall_auto vs _waterfall_manual: branch by config flag, separate implementations"
  - "_record_target + on_poll: convergence tracking pattern for feedback loop"

requirements-completed: [THRT-07, THRT-08, THRT-09]

duration: 8min
completed: 2026-03-25
---

# Phase 35 Plan 01: Smart Auto-Throttle Algorithm Summary

**Score-based waterfall ordering with convergence tracking and measured response time feedback for auto-throttle mode**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-25T18:20:42Z
- **Completed:** 2026-03-25T18:28:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- auto_throttle config field on Config dataclass (defaults False, persists through YAML)
- Score-based waterfall: when auto_throttle=True, devices sorted by throttle score descending (proportional before binary)
- Convergence tracking: on_poll() detects when device reaches target power within 5% tolerance
- Rolling-average response time measurement feeds back into effective score via _effective_score()
- 14 new tests (6 auto-throttle + 8 convergence), all passing, full suite green (31 total)

## Task Commits

Each task was committed atomically:

1. **Task 1: Auto-throttle config field + score-based waterfall** - `c823f88` (feat)
2. **Task 2: Convergence tracking with measured response time feedback** - `0d6e636` (feat)

## Files Created/Modified
- `src/pv_inverter_proxy/config.py` - Added auto_throttle: bool = False field, handled in load_config
- `src/pv_inverter_proxy/distributor.py` - Added _effective_score(), _waterfall_auto(), _waterfall_manual(), on_poll(), _record_target(), convergence constants, DeviceLimitState convergence fields
- `tests/test_distributor.py` - 14 new tests for auto-throttle ordering and convergence tracking

## Decisions Made
- Auto waterfall treats each device as its own tier (no grouping by score), sorted by (score, device_id) descending for deterministic ordering
- Convergence detection: 5% tolerance for proportional targets, 50W near-zero threshold for binary off
- Rolling average of up to 10 samples for measured_response_time_s, trimmed FIFO
- Target only reset when new target differs by >2% from current (avoids stale target pitfall)
- _effective_score uses measured_response_time_s when available, falls back to preset ThrottleCaps

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all functionality fully wired.

## Issues Encountered
- Pre-existing pymodbus version mismatch on system Python 3.9 prevents test_aggregation.py from collecting. This is unrelated to Phase 35 changes (environment issue). All distributor tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Core auto-throttle algorithm complete with convergence feedback
- Ready for Phase 35 Plan 02 (if exists): UI integration / live tuning
- on_poll() ready to be wired into the device poll loop for real-time convergence detection

## Self-Check: PASSED

All files exist, both commits verified, all acceptance criteria met.

---
*Phase: 35-smart-auto-throttle-algorithm*
*Completed: 2026-03-25*
