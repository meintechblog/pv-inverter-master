---
phase: 20
slug: discovery-ui-onboarding
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run python -m pytest tests/ -x -q` |
| **Full suite command** | `uv run python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

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
| 20-01-01 | 01 | 1 | DISC-05 | unit | `uv run python -m pytest tests/test_scanner.py -x -q` | ✅ | ⬜ pending |
| 20-01-02 | 01 | 1 | UX-02 | unit | `uv run python -m pytest tests/test_scanner.py -x -q` | ✅ | ⬜ pending |
| 20-02-01 | 02 | 2 | UX-01, UX-03 | manual | Browser: open config with empty inverter list | N/A | ⬜ pending |
| 20-02-02 | 02 | 2 | CONF-04 | manual | Browser: trigger scan, confirm results | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. Scanner tests already exist in `tests/test_scanner.py`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Progress bar animation during scan | DISC-05 | Visual UI element | Open config, click Discover, observe progress bar fills with phase text |
| Auto-scan on empty config | UX-01 | Browser behavior | Delete all inverters, navigate to config, observe auto-scan starts |
| Scan results with checkboxes | UX-03 | Visual UI element | Complete scan, verify result list with checkboxes appears |
| Already-configured marked in results | CONF-04 | Visual UI element | Have configured inverter, scan, verify it appears greyed out |
| Discovered inverters added to config | CONF-04 | End-to-end flow | Select results, click add, verify they appear in inverter list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
