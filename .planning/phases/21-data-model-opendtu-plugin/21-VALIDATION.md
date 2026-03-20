---
phase: 21
slug: data-model-opendtu-plugin
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run python -m pytest tests/ -x -q` |
| **Full suite command** | `uv run python -m pytest tests/ -v` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/ -x -q`
- **After every plan wave:** Run `uv run python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | DATA-01, DATA-02 | unit | `uv run python -m pytest tests/test_config.py -x -q` | ✅ | ⬜ pending |
| 21-01-02 | 01 | 1 | DATA-03 | unit | `uv run python -m pytest tests/test_config.py -x -q` | ✅ | ⬜ pending |
| 21-02-01 | 02 | 2 | DTU-01, DTU-02, DTU-04 | unit | `uv run python -m pytest tests/test_opendtu.py -x -q` | ❌ W0 | ⬜ pending |
| 21-02-02 | 02 | 2 | DTU-03, DTU-05 | unit | `uv run python -m pytest tests/test_opendtu.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_opendtu.py` — stubs for DTU-01 through DTU-05 (plugin poll, power limit, dead-time)
- [ ] Fixture: mock OpenDTU API responses (livedata/status, limit/config, limit/status)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OpenDTU live polling | DTU-01 | Requires real OpenDTU at 192.168.3.98 | Deploy to LXC, verify data appears in logs |
| Power limit to Hoymiles | DTU-03 | Requires real hardware | Set limit via API, observe OpenDTU confirm |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
