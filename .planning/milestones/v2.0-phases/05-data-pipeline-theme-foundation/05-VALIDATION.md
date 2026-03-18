---
phase: 05
slug: data-pipeline-theme-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (already configured) |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

*Task IDs filled after planning.*

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | INFRA-02 | unit | `python -m pytest tests/test_dashboard_collector.py -v` | TBD | pending |
| TBD | TBD | TBD | INFRA-03 | unit | `python -m pytest tests/test_timeseries.py -v` | TBD | pending |
| TBD | TBD | TBD | INFRA-04 | unit | `python -m pytest tests/test_static_serving.py -v` | TBD | pending |
| TBD | TBD | TBD | DASH-01 | visual | checkpoint:human-verify | TBD | pending |

---

## Wave 0 Requirements

- [ ] `tests/test_dashboard_collector.py` — DashboardCollector unit tests
- [ ] `tests/test_timeseries.py` — TimeSeriesBuffer ring buffer tests
- [ ] `tests/conftest.py` — extend with collector fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Venus OS theme looks correct | DASH-01 | Visual verification needed | Open http://192.168.3.191, verify colors match Venus OS palette |
| Sidebar responsive on mobile | DASH-01 | Requires browser resize | Open on phone or resize browser to 375px |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
