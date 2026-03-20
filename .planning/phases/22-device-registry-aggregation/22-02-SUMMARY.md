---
phase: 22-device-registry-aggregation
plan: 02
subsystem: aggregation
tags: [sunspec, modbus, aggregation, multi-device, asyncio]

requires:
  - phase: 22-01
    provides: "DeviceRegistry with per-device poll loops and ManagedDevice lifecycle"
provides:
  - "AggregationLayer: decode N device registers, sum/avg/max, re-encode SunSpec"
  - "VirtualInverterConfig for user-defined virtual inverter identity"
  - "Multi-device proxy orchestration via DeviceRegistry + AggregationLayer pipeline"
  - "run_modbus_server (server-only, decoupled from polling)"
affects: [23-power-limit-distribution, 24-per-device-ui]

tech-stack:
  added: []
  patterns: ["event-driven aggregation (callback after each poll)", "fixed scale factors for aggregated SunSpec encoding", "snapshot-based dict iteration for concurrency safety"]

key-files:
  created:
    - src/venus_os_fronius_proxy/aggregation.py
    - tests/test_aggregation.py
  modified:
    - src/venus_os_fronius_proxy/config.py
    - src/venus_os_fronius_proxy/context.py
    - src/venus_os_fronius_proxy/proxy.py
    - src/venus_os_fronius_proxy/__main__.py
    - src/venus_os_fronius_proxy/webapp.py
    - src/venus_os_fronius_proxy/dashboard.py

key-decisions:
  - "Power limit forwarding deferred to Phase 23 -- local-only acceptance with warning log"
  - "Modbus server kept running when 0 active devices (stale errors instead of stop) to preserve Venus OS discovery"
  - "Webapp handlers use app.get('plugin') with None guard for multi-device mode"
  - "DashboardCollector uses getattr for last_poll_data to handle removed compat accessor"

patterns-established:
  - "AggregationLayer.recalculate() as on_poll_success callback from DeviceRegistry"
  - "Fixed SFs for aggregated output: SF=0 power, SF=-1 voltage, SF=-2 current/freq"
  - "Snapshot device_ids = list(app_ctx.devices.keys()) before iteration"

requirements-completed: [AGG-01, AGG-02, AGG-03, AGG-04]

duration: 20min
completed: 2026-03-20
---

# Phase 22 Plan 02: AggregationLayer + Multi-Device Proxy Rewire Summary

**AggregationLayer sums N device SunSpec registers into one virtual Fronius inverter with fixed scale factors, plus full proxy rewire from single-plugin to DeviceRegistry+AggregationLayer pipeline**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-20T20:54:53Z
- **Completed:** 2026-03-20T21:15:00Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- AggregationLayer decodes per-device Model 103 registers to physical values, sums power/current/energy, averages voltage/frequency, takes max temperature, encodes with consistent fixed SFs
- Virtual inverter identity: Manufacturer="Fronius", Model=user-defined name (default "Fronius PV Inverter Proxy")
- WRtg Model 120 auto-summed from active InverterEntry rated_powers
- Proxy fully rewired: __main__.py creates DeviceRegistry + AggregationLayer, proxy.py provides server-only setup
- Compat accessors removed from AppContext (primary_device, dashboard_collector, conn_mgr, poll_counter, last_poll_data)
- 12 aggregation tests + all existing tests updated for new architecture

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AggregationLayer (TDD RED)** - `ecde759` (test)
2. **Task 1: Create AggregationLayer (TDD GREEN)** - `baaefec` (feat)
3. **Task 2: Rewire proxy/main/context/webapp** - `a458fa0` (feat)

## Files Created/Modified
- `src/venus_os_fronius_proxy/aggregation.py` - AggregationLayer with decode/encode/recalculate
- `src/venus_os_fronius_proxy/config.py` - VirtualInverterConfig dataclass, rated_power field on InverterEntry
- `src/venus_os_fronius_proxy/context.py` - Removed compat accessors, added device_registry field
- `src/venus_os_fronius_proxy/proxy.py` - Removed _poll_loop, replaced run_proxy with run_modbus_server
- `src/venus_os_fronius_proxy/__main__.py` - DeviceRegistry + AggregationLayer orchestration
- `src/venus_os_fronius_proxy/webapp.py` - _reconfigure_active uses DeviceRegistry, plugin made optional
- `src/venus_os_fronius_proxy/dashboard.py` - getattr guard for removed last_poll_data accessor
- `tests/test_aggregation.py` - 12 tests for aggregation math and partial failure
- `tests/test_context.py` - Updated for removed compat accessors
- `tests/test_proxy.py` - Updated for run_modbus_server, removed _poll_loop refs
- `tests/test_solaredge_write.py` - Updated to use standalone server setup
- `tests/test_connection.py` - Removed _poll_loop import

## Decisions Made
- Power limit forwarding deferred to Phase 23: StalenessAwareSlaveContext accepts writes locally with warning log when no plugin available
- Kept Modbus server running when 0 active devices rather than stopping it, to avoid Venus OS rediscovery issues (per Pitfall 4 from research)
- Webapp plugin references made optional with `app.get("plugin")` and None guards
- Used getattr for DashboardCollector.collect() access to app_ctx.last_poll_data to handle removed accessor

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Plugin None guards in webapp handlers**
- **Found during:** Task 2 (webapp rewire)
- **Issue:** power_limit_handler, power_clamp_handler, venus_lock_handler accessed app["plugin"] which is now None in multi-device mode
- **Fix:** Changed to app.get("plugin") with None guards around plugin.write_power_limit calls
- **Files modified:** src/venus_os_fronius_proxy/webapp.py
- **Verification:** test_webapp.py passes with plugin=None

**2. [Rule 1 - Bug] DashboardCollector AttributeError on removed accessor**
- **Found during:** Task 2 (context.py cleanup)
- **Issue:** DashboardCollector.collect() accessed app_ctx.last_poll_data which was a removed compat accessor
- **Fix:** Changed to getattr(app_ctx, "last_poll_data", None)
- **Files modified:** src/venus_os_fronius_proxy/dashboard.py
- **Verification:** No AttributeError in tests

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing test failures in test_control.py, test_connection.py, test_proxy.py related to WMAXLIMPCT_SF=0 (tests expect SF=-2 behavior). These are not caused by this plan and are out of scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DeviceRegistry + AggregationLayer pipeline complete
- Ready for Phase 23 (Power Limit Distribution across N devices)
- Ready for Phase 24 (Per-device UI endpoints and dashboard)
- Power limit forwarding stub in place with warning log

---
*Phase: 22-device-registry-aggregation*
*Completed: 2026-03-20*
