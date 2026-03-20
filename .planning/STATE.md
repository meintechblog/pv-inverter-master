---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Auto-Discovery & Inverter Management
status: requirements
stopped_at: null
last_updated: "2026-03-20"
last_activity: 2026-03-20 — Milestone v3.1 started
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** Venus OS muss den SolarEdge-Inverter genauso erkennen und steuern koennen wie einen echten Fronius-Inverter
**Current focus:** v3.1 Auto-Discovery & Inverter Management — Defining requirements

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-20 — Milestone v3.1 started

## Performance Metrics

**v1.0:** 4 phases, 9 plans, ~1 hour
**v2.0:** 4 phases, 7 plans, ~3 hours
**v2.1:** 4 phases, 7 plans
**v3.0:** 4 phases, 6 plans

## Accumulated Context

### Decisions

- 50W gauge deadband for 30kW inverter (09-01)
- Lock duration hard-capped at 900s — safety-critical (11-01)
- Locked writes silently accepted but NOT forwarded (11-01)
- Override log collapsed by default with event count badge (12-01)
- Empty venus host = not configured, proxy runs without MQTT (13-01)
- CONNACK rejection raises ConnectionError with return code (13-01)
- Portal ID discovery retries every 30s in while-True loop before main MQTT loop (13-02)
- 503 status for unconfigured Venus OS handlers (graceful degradation) (13-02)
- CONNACK validated in _mqtt_write_venus for consistency (13-02)
- Venus config change detected via tuple comparison of (host, port, portal_id) (14-01)
- Three-state venus status: connected/disconnected/not configured (14-01)
- Nested config API format {inverter: {...}, venus: {...}} (14-01)
- Connection bobbles replace Test Connection button for live status (14-02)
- venus-dependent class + mqtt-gated CSS for dashboard feature gating (14-02)
- MQTT setup guide card shown contextually when configured but disconnected (14-02)
- Detection is one-shot: flag set on first Model 123 write only (15-01)
- Banner placed before config form, outside form element (15-01)
- window._lastVenusDetected tracks state for input listener restore (15-01)
- [Phase 16]: Migration warning (not auto-migration) for old solaredge: config key
- [Phase 16]: Port 502 check is warning not hard fail (previous install may hold port)

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-20
Stopped at: Milestone v3.1 initialization
