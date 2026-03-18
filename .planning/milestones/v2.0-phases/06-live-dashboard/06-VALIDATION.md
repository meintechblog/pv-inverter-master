---
phase: 06
slug: live-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 06 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~10 seconds |

## Sampling Rate

- **After every task commit:** `python -m pytest tests/ -x -q`
- **After every plan wave:** `python -m pytest tests/ -v --timeout=30`
- **Max feedback latency:** 10 seconds

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| TBD | TBD | TBD | INFRA-01 | unit | `pytest tests/test_websocket.py -v` | pending |
| TBD | TBD | TBD | DASH-02, DASH-03, DASH-06 | visual | checkpoint:human-verify | pending |
| TBD | TBD | TBD | INFRA-05 | unit | `pytest tests/ -x -q` | pending |

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Power gauge animates live | DASH-02 | Visual | Open dashboard, verify power gauge updates |
| Sparkline grows over time | DASH-06 | Visual | Watch sparkline for 2+ minutes |
| Responsive layout | DASH-02 | Visual | Resize browser |

## Validation Sign-Off

- [ ] All tasks have automated verify or checkpoint
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
