---
phase: 26-telemetry-publishing-ha-discovery
plan: 01
subsystem: mqtt
tags: [mqtt, home-assistant, ha-discovery, telemetry, pure-functions]

# Dependency graph
requires:
  - phase: 25-mqtt-publisher-infrastructure
    provides: MqttPublishConfig, publisher queue, LWT topics
provides:
  - device_payload() for flat telemetry extraction from snapshots
  - virtual_payload() for virtual PV aggregation payloads
  - ha_discovery_configs() generating 16 HA sensor configs per device
  - ha_discovery_topic() for discovery topic path construction
  - virtual_ha_discovery_configs() for virtual device HA discovery
  - SENSOR_DEFS table with device_class/state_class/unit/precision
affects: [26-02, mqtt_publisher integration, HA auto-discovery]

# Tech tracking
tech-stack:
  added: []
  patterns: [pure-function payload module, SENSOR_DEFS data-driven config table]

key-files:
  created:
    - src/venus_os_fronius_proxy/mqtt_payloads.py
    - tests/test_mqtt_payloads.py
  modified: []

key-decisions:
  - "SENSOR_DEFS as list-of-tuples for data-driven HA config generation"
  - "Omit device_class/state_class/unit keys entirely when None (HA best practice for enum sensors)"
  - "temperature_sink_c renamed to temperature_c in payload for HA-friendly naming"

patterns-established:
  - "Pure-function payload module: zero side effects, no MQTT dependency, testable without broker"
  - "Data-driven sensor definitions: SENSOR_DEFS table drives both discovery configs and payload field mapping"

requirements-completed: [PUB-01, PUB-02, HA-01, HA-02, HA-03]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 26 Plan 01: MQTT Payloads Summary

**Pure-function module converting DashboardCollector snapshots to flat MQTT payloads and 16 HA auto-discovery sensor configs per device**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-22T10:41:24Z
- **Completed:** 2026-03-22T10:43:32Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Created mqtt_payloads.py with 5 public functions and zero side effects
- 16 HA sensor definitions matching FEATURES.md spec exactly (device_class, state_class, unit, precision)
- 19 passing tests covering payload extraction, HA discovery structure, availability, device grouping
- temperature_sink_c properly renamed to temperature_c in output payloads

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `44ea8ab` (test)
2. **Task 1 GREEN: Implementation** - `1dd127a` (feat)

## Files Created/Modified
- `src/venus_os_fronius_proxy/mqtt_payloads.py` - Pure-function payload extraction and HA discovery config builders (242 lines)
- `tests/test_mqtt_payloads.py` - 19 test functions covering all public APIs (263 lines)

## Decisions Made
- SENSOR_DEFS as list-of-tuples for data-driven config generation -- easy to extend, single source of truth
- Omit device_class/state_class/unit_of_measurement keys entirely when None rather than setting to null -- HA treats missing keys as "no class" which is correct for enum sensors like Status
- temperature_sink_c renamed to temperature_c in payload output for cleaner HA entity naming
- Virtual device gets "pv_proxy_virtual" as device identifier, separate from per-device identifiers
- Contribution entries stripped to device_id/name/power_w only -- throttle metadata not published to MQTT

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions fully implemented with real data extraction logic.

## Next Phase Readiness
- mqtt_payloads.py ready for import by mqtt_publisher.py in Plan 02
- SENSOR_DEFS table can be extended if new sensors are added
- ha_discovery_topic() provides the topic path for publisher to use when sending retained discovery messages

---
*Phase: 26-telemetry-publishing-ha-discovery*
*Completed: 2026-03-22*
