---
phase: 13
slug: mqtt-config-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | CFG-03 | unit | `pytest tests/ -k venus_config` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | CFG-03 | unit | `pytest tests/ -k mqtt_connect` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | CFG-04 | unit | `pytest tests/ -k portal_discovery` | ❌ W0 | ⬜ pending |
| TBD | 02 | 1 | CFG-03 | integration | `pytest tests/ -k connack` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_venus_config.py` — stubs for CFG-03 (VenusConfig dataclass, config load/save)
- [ ] `tests/test_mqtt_connect.py` — stubs for CFG-03 (MQTT connection with config params)
- [ ] `tests/test_portal_discovery.py` — stubs for CFG-04 (portal ID auto-discovery)

*Existing test infrastructure covers framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MQTT connects to live Venus OS | CFG-03 | Requires real Venus OS MQTT broker | Deploy to LXC, verify logs show connection to configured IP |
| Portal ID auto-discovered from live broker | CFG-04 | Requires real Venus OS publishing portal ID | Leave portal_id blank in config, verify logs show discovered ID |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
