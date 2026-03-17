---
phase: 01-protocol-research-validation
plan: 02
subsystem: protocol
tags: [sunspec, modbus, solaredge, se30k, live-validation, register-mapping]

# Dependency graph
requires:
  - phase: 01-01
    provides: register mapping specification with expected addresses and model chain
provides:
  - Live-validated SolarEdge SE30K register layout
  - Confirmed model chain structure (15 models, no Model 120/123)
  - Discovery of Model 704 (DER Controls) as potential alternative to proprietary registers
affects: [02-core-proxy]

# Tech tracking
tech-stack:
  added: [pymodbus]
  patterns: [sunspec-model-chain-walk, modbus-tcp-live-validation]

key-files:
  created:
    - scripts/validate_se30k.py
    - docs/se30k-validation-results.md
  modified: []

key-decisions:
  - "Model 120 and Model 123 are confirmed absent from SE30K — proxy MUST synthesize both"
  - "Model 704 (DER Controls) discovered at address 40521 — SE30K supports standard SunSpec DER controls natively"
  - "Second Common Model (Model 1) at 40121 likely represents meter/optimizer aggregate — proxy must NOT pass this through"
  - "SE30K responds normally while sleeping (Status=2) — all measurement registers read zero except grid frequency"

patterns-established:
  - "SunSpec model chain walk: read DID+Length at address, if DID==0xFFFF stop, else advance by 2+Length"
  - "SE30K full chain: 103 -> 1 -> 203 -> 701-713 -> END (15 models total)"

requirements-completed: [PROTO-02]

# Metrics
duration: 5min
completed: 2026-03-18
---

# Phase 1 Plan 2: Live SolarEdge Register Validation Summary

**Live Modbus TCP validation of SE30K at 192.168.3.18:1502 confirming register layout, model chain (15 models, no 120/123), and discovery of Model 704 DER Controls**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-17T23:43:00Z
- **Completed:** 2026-03-18T00:44:00Z
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files modified:** 2

## Accomplishments
- Connected to live SE30K via Modbus TCP and validated all 5 register areas (header, Common, Inverter, chain walk, summary)
- Confirmed Model 120 (Nameplate) and Model 123 (Immediate Controls) are absent — proxy synthesis is mandatory
- Discovered Model 704 (DER Controls) at address 40521 — SE30K supports standard SunSpec DER controls, potential alternative to proprietary 0xF300/0xF322 registers
- Mapped complete model chain: 103 -> 1 -> 203 -> 701 -> 702 -> 703 -> 704 -> 705 -> 706 -> 707 -> 708 -> 709 -> 710 -> 711 -> 712 -> 713 -> END

## Task Commits

1. **Task 1: Live SE30K register validation script + results** - `6e33e26` (feat)
2. **Task 2: Human verification checkpoint** - approved by user

## Files Created/Modified
- `scripts/validate_se30k.py` - Comprehensive Modbus TCP validation script with 6 test sections
- `docs/se30k-validation-results.md` - Complete validation output with analysis and implications

## Decisions Made
- Confirmed proxy design assumptions: Model 120 and 123 synthesis is required
- Noted Model 704 as potential future optimization path (v1 proxy still uses Model 123 synthesis)
- Identified second Common Model at 40121 as device boundary the proxy must respect

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Validation ran at nighttime (inverter Status=SLEEPING). All power readings were zero as expected. Grid frequency (49.98 Hz) and lifetime energy (20.6 MWh) confirmed the inverter is responsive and data is plausible.

## User Setup Required

None - validation script is a one-time tool, not a deployed service.

## Next Phase Readiness
- All PROTO requirements (01, 02, 03) are now complete
- Register layout is validated against live hardware — proxy implementation can proceed with confidence
- Model 704 discovery provides an alternative control path if proprietary register translation proves problematic

## Self-Check: PASSED

Both files verified present. Commit 6e33e26 found in git log.

---
*Phase: 01-protocol-research-validation*
*Completed: 2026-03-18*
