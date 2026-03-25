---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: Shelly Plugin
status: Ready to plan
stopped_at: Completed 33-02-PLAN.md
last_updated: "2026-03-25T16:05:15.668Z"
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Venus OS muss alle PV-Inverter als einen virtuellen Fronius-Inverter erkennen und steuern koennen
**Current focus:** Phase 33 — device-throttle-capabilities-scoring

## Current Position

Phase: 34
Plan: Not started

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
- [Phase 28]: Profile-based Gen1/Gen2 abstraction using ShellyProfile ABC -- swappable API implementations
- [Phase 28]: Zero new deps for Shelly -- reuse aiohttp, energy offset tracking for counter resets
- [Phase 29]: ShellyPlugin.switch() wraps profile.switch() with session injection and error handling
- [Phase 29]: Shelly devices default throttle_enabled=False (on/off only, no percentage limiting)
- [Phase 30]: Reused mDNS discovery pattern from mdns_discovery.py for Shelly devices
- [Phase 30]: Gen2+ devices map to generation=gen2 with gen_display showing actual gen number
- [Phase 30]: Probe-on-Add: single click probes Shelly, shows generation, then auto-saves
- [Phase 30]: Type-filtered discovery: Discover button routes to mDNS for Shelly vs Modbus scan for SolarEdge
- [Phase 33]: Scoring formula: proportional base=7, binary base=3, none=0 with response/cooldown/startup penalties
- [Phase 33]: Used hasattr guard pattern for throttle_capabilities to handle plugins without the property gracefully

### Roadmap Evolution

- Phase 33 added: Binary Throttle (Relay On/Off) for Shelly Devices

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-25T16:00:30.536Z
Stopped at: Completed 33-02-PLAN.md
Resume point: Plan phase 28 (Plugin Core & Profiles)
