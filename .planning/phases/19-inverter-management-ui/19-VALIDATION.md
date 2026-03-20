---
phase: 19
slug: inverter-management-ui
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-20
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `python3 -m pytest tests/test_webapp.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | CONF-02 | unit (API) | `python3 -m pytest tests/test_webapp.py -x -q -k "inverter"` | ✅ (Phase 18) | ⬜ pending |
| 19-01-01 | 01 | 1 | CONF-03 | unit (API) | `python3 -m pytest tests/test_webapp.py -x -q -k "inverter"` | ✅ (Phase 18) | ⬜ pending |
| 19-01-01 | 01 | 1 | CONF-02 | manual | Visual: toggle slider renders and toggles | N/A | ⬜ pending |
| 19-01-01 | 01 | 1 | CONF-03 | manual | Visual: inline confirm and delete flow | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. Phase 18 CRUD tests verify backend. Frontend is vanilla JS without browser test framework — visual behavior verified manually.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toggle slider renders enabled/disabled state | CONF-02 | Vanilla JS UI, no browser test framework | Open config page, verify toggle reflects inverter enabled status, toggle and verify instant persistence |
| Delete inline-confirm flow | CONF-03 | Vanilla JS UI, no browser test framework | Click delete icon, verify confirm message appears, confirm delete, verify row removed |
| Active inverter blue border | CONF-02 | Visual CSS property | Open config page with multiple inverters, verify active has blue left border |
| Empty state hint card | CONF-03 | Visual UI state | Delete all inverters, verify hint card appears |
| Add inverter form | CONF-02 | Interactive form flow | Click plus button, fill form, submit, verify new row appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
