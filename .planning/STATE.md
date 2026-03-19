---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Setup & Onboarding
status: active
stopped_at: null
last_updated: "2026-03-19"
last_activity: 2026-03-19 — Milestone v3.0 started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Venus OS muss den SolarEdge-Inverter genauso erkennen und steuern koennen wie einen echten Fronius-Inverter
**Current focus:** v3.0 Setup & Onboarding

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-19 — Milestone v3.0 started

## Performance Metrics

**v1.0:** 4 phases, 9 plans, ~1 hour
**v2.0:** 4 phases, 7 plans, ~3 hours
**v2.1:** 4 phases, 7 plans

## Accumulated Context

### Decisions

- 50W gauge deadband for 30kW inverter balances responsiveness with jitter suppression (09-01)
- Per-metric flash thresholds tuned for inverter noise: voltage 2V, current 0.5A, power 100W, temp 1C (09-01)
- Entrance animation one-shot on first WS connect only; reconnects do not replay (09-01)
- Toast container uses pointer-events:none with auto on children for click-through (09-02)
- Oldest non-error toast dismissed first when max exceeded (09-02)
- Tiered auto-dismiss: 3s info/success, 5s warning, 8s error (09-02)
- Operating hours precision 4 decimal places to avoid rounding small intervals to zero (10-01)
- Bottom dashboard grid changed to auto-fit for graceful 4-card wrapping (10-01)
- Lock duration hard-capped at 900s regardless of input — safety-critical (11-01)
- Locked writes silently accepted but NOT forwarded — prevents Venus OS retry storms (11-01)
- Lock defaults to unlocked on restart — safe default (11-01)
- Locked writes do not update last_source — lock means "pretend write didn't happen" (11-01)
- [Phase 11]: Toggle disabled when Venus OS offline but enabled for unlock even if offline (11-02)
- [Phase 11]: Countdown interpolated client-side between snapshots for smooth mm:ss display (11-02)
- [Phase 11]: Auto-unlock detected by diffing previous vs current snapshot is_locked field (11-02)
- [Phase 12]: Power control elements keep identical IDs after move — JS bindings work unchanged via getElementById (12-01)
- [Phase 12]: Override log collapsed by default with event count badge for compact layout (12-01)
- [Phase 12]: Navigation null-guarded against removed pages for forward safety (12-01)

### Pending Todos

None.

### Blockers/Concerns

- Venus OS Modbus TCP must be enabled manually in Venus OS settings (for MQTT)
- Venus OS register addresses need validation against running v3.71 instance
- MQTT host + portal ID currently hardcoded — v3.0 will make configurable

## Session Continuity

Last session: 2026-03-19
Stopped at: Milestone v3.0 started — defining requirements
