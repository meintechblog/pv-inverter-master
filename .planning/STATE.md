---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: Shelly Plugin
status: ready_to_plan
stopped_at: Roadmap created, ready to plan phase 28
last_updated: "2026-03-24"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Venus OS muss alle PV-Inverter als einen virtuellen Fronius-Inverter erkennen und steuern koennen
**Current focus:** v6.0 Shelly Plugin -- Phase 28 ready to plan

## Current Position

Phase: 28 of 32 (Plugin Core & Profiles) -- first of 5 in v6.0
Plan: --
Status: Ready to plan
Last activity: 2026-03-24 -- Roadmap created for v6.0

Progress: [..........] 0%

## Performance Metrics

**Prior milestones:**

- v1.0: 4 phases, 9 plans
- v2.0: 4 phases, 7 plans
- v2.1: 4 phases, 7 plans
- v3.0: 4 phases, 6 plans
- v3.1: 4 phases, 7 plans
- v4.0: 4 phases, 8 plans
- v5.0: 3 phases, 6 plans

## Accumulated Context

### Decisions

- [v4.0]: DeviceRegistry per-device asyncio poll loops with independent lifecycle
- [v4.0]: AggregationLayer SunSpec register summation across heterogeneous sources
- [v4.0]: Device-centric SPA with hash routing and per-device sub-tabs
- [v5.0]: aiomqtt for publisher, queue-based decoupling, HA discovery
- [v6.0]: Profile-based Gen1/Gen2 abstraction (dict, not class hierarchy) -- from research
- [v6.0]: Zero new deps -- reuse aiohttp for all Shelly HTTP communication
- [v6.0]: write_power_limit() as no-op -- Shelly only supports on/off switching

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-24
Stopped at: Roadmap created for v6.0 Shelly Plugin
Resume point: Plan phase 28 (Plugin Core & Profiles)
