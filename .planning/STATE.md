---
gsd_state_version: 1.0
milestone: v4.0
milestone_name: Multi-Source Virtual Inverter
status: in_progress
stopped_at: Roadmap created for v4.0
last_updated: "2026-03-20T18:00:00.000Z"
last_activity: 2026-03-20 — Roadmap created for v4.0 Multi-Source Virtual Inverter (4 phases, 28 requirements)
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 7
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** Venus OS muss alle PV-Inverter als einen virtuellen Fronius-Inverter erkennen und steuern koennen
**Current focus:** Phase 21 - Data Model & OpenDTU Plugin

## Current Position

Phase: 21 of 24 (Data Model & OpenDTU Plugin)
Plan: 0 of 2 in current phase
Status: Ready to plan
Last activity: 2026-03-20 -- Roadmap created for v4.0 milestone

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Prior milestones:**
- v1.0: 4 phases, 9 plans, ~1 hour
- v2.0: 4 phases, 7 plans, ~3 hours
- v2.1: 4 phases, 7 plans
- v3.0: 4 phases, 6 plans
- v3.1: 4 phases, 7 plans

**v4.0:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

## Accumulated Context

### Decisions

- [v4.0 Roadmap]: Coarse granularity -- 4 phases (21-24) covering 28 requirements
- [v4.0 Roadmap]: Config refactor + OpenDTU plugin bundled in Phase 21 (both foundational)
- [v4.0 Roadmap]: Discovery uses manual scan only -- no auto-scan-on-empty-list
- [v3.1]: SolarEdge single-connection constraint remains (scanner uses sequential access)
- [v3.1]: Inverters use instant CRUD (PUT/DELETE) not dirty-tracking

### Pending Todos

None.

### Blockers/Concerns

- OpenDTU dead-time (25-30s) estimated from GitHub issues -- validate on real HM-800 during Phase 21
- Hoymiles serials at 192.168.3.98 must be confirmed from live API response
- SolarEdge single-connection constraint affects concurrent polling design

## Session Continuity

Last session: 2026-03-20
Stopped at: Roadmap created for v4.0 Multi-Source Virtual Inverter
Resume file: None
