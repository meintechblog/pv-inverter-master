---
phase: 18
slug: multi-inverter-config
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23.x |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `python3 -m pytest tests/test_config.py tests/test_config_save.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_config.py tests/test_config_save.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_config.py -x -k inverter_entry` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_config.py -x -k config_inverters` | ❌ W0 | ⬜ pending |
| 18-01-03 | 01 | 1 | CONF-05 | unit | `python3 -m pytest tests/test_config.py -x -k migration` | ❌ W0 | ⬜ pending |
| 18-01-04 | 01 | 1 | CONF-05 | unit | `python3 -m pytest tests/test_config_save.py -x -k roundtrip_inverters` | ❌ W0 | ⬜ pending |
| 18-01-05 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_list` | ❌ W0 | ⬜ pending |
| 18-01-06 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_add` | ❌ W0 | ⬜ pending |
| 18-01-07 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_update` | ❌ W0 | ⬜ pending |
| 18-01-08 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_webapp.py -x -k inverters_delete` | ❌ W0 | ⬜ pending |
| 18-01-09 | 01 | 1 | CONF-01 | unit | `python3 -m pytest tests/test_config.py -x -k active_inverter` | ❌ W0 | ⬜ pending |
| 18-01-10 | 01 | 1 | CONF-05 | unit | `python3 -m pytest tests/test_config.py -x -k fresh_default` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — new tests for InverterEntry dataclass, migration, active inverter, fresh default
- [ ] `tests/test_config_save.py` — new tests for multi-inverter roundtrip save/load
- [ ] `tests/test_webapp.py` — new tests for CRUD inverter endpoints

*Existing test infrastructure covers framework setup. No new framework installs needed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
