---
phase: 30-add-device-flow-discovery
plan: 02
subsystem: ui
tags: [shelly, add-device, mdns-discovery, probe, vanilla-js, venus-os]

# Dependency graph
requires:
  - phase: 30-01
    provides: Shelly probe, discover, and device-add API endpoints
provides:
  - Shelly type card in add-device modal
  - Shelly form with probe-on-add flow and hint-card feedback
  - mDNS discovery integration for Shelly devices
  - Shelly config page with Generation badge and Rated Power
affects: [31-shelly-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [type-filtered discovery, probe-before-save]

key-files:
  created: []
  modified:
    - src/pv_inverter_proxy/static/app.js
    - src/pv_inverter_proxy/static/style.css

key-decisions:
  - "Probe-on-Add: single click probes Shelly, shows generation, then auto-saves (same UX as OpenDTU auth-test)"
  - "Type-filtered discovery: Discover button routes to mDNS for Shelly, Modbus scan for SolarEdge"
  - "Port/UnitID hidden for Shelly since they are irrelevant (HTTP-only device)"

patterns-established:
  - "Type-filtered discovery: Discover button behavior depends on selected device type"
  - "Probe-before-save: validate device reachability before persisting config"

requirements-completed: [UI-01, UI-02, UI-05, UI-06]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 30 Plan 02: Add-Device Flow & Discovery Summary

**Shelly add-device flow with type card, probe-on-add with hint-card feedback, mDNS discovery, and Shelly-specific config page fields**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-24T01:45:01Z
- **Completed:** 2026-03-24T01:49:48Z (checkpoint pending)
- **Tasks:** 2/3 (Task 3 is human-verify checkpoint)
- **Files modified:** 2

## Accomplishments
- Shelly Device card as third option in add-device modal alongside SolarEdge and OpenDTU
- Shelly form with Name, Host IP, Rated Power fields and probe-on-Add flow with green/orange hint-card feedback
- mDNS discovery via triggerShellyDiscover() with checkbox-list results that fill in form fields
- Config page shows Generation as readonly blue badge and Rated Power as editable field
- Port/UnitID hidden for Shelly devices, dirty tracking works for rated_power

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Shelly type card, form, probe flow, and discovery in app.js** - `b43e0f4` (feat)
2. **Task 2: Add generation badge CSS to style.css** - `c1aa146` (feat)
3. **Task 3: Verify add-device flow and config page** - CHECKPOINT (human-verify)

## Files Created/Modified
- `src/pv_inverter_proxy/static/app.js` - Shelly type card, form, probe flow, discovery, config fields, dirty tracking
- `src/pv_inverter_proxy/static/style.css` - .ve-gen-badge CSS class for generation badge

## Decisions Made
- Probe-on-Add: single click probes Shelly, shows generation hint-card, then auto-saves (mirrors OpenDTU auth-test UX)
- Type-filtered discovery: Discover button routes to mDNS for Shelly vs Modbus scan for SolarEdge
- Port/UnitID fields hidden for Shelly (HTTP-only device, no Modbus)
- Guarded portInput/unitInput with null checks throughout config form to handle Shelly correctly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Guarded portInput/unitInput null references in config form**
- **Found during:** Task 1 (config form extension)
- **Issue:** Port and UnitID inputs are null for Shelly devices since they are hidden, causing crashes in dirty tracking and save
- **Fix:** Added null guards for portInput/unitInput in checkDirty, cancel handler, save payload, and save callback
- **Files modified:** src/pv_inverter_proxy/static/app.js
- **Verification:** Code review confirms no null dereference paths
- **Committed in:** b43e0f4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correctness when Port/UnitID are hidden. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Awaiting human verification of the add-device flow at http://192.168.3.191
- After approval, Phase 31 (Shelly Dashboard) can proceed

---
*Phase: 30-add-device-flow-discovery*
*Completed: 2026-03-24 (pending checkpoint)*
