---
phase: 24
slug: device-centric-api-frontend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run python -m pytest tests/ -x -q` |
| **Full suite command** | `uv run python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/ -x -q`
- **After every plan wave:** Run `uv run python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | API-01, API-02, API-03 | unit | `uv run python -m pytest tests/test_webapp.py -x -q` | Yes | pending |
| 24-02-01 | 02 | 2 | UI-01, UI-02, UI-03, UI-04, UI-05, UI-06 | visual | checkpoint:human-verify | N/A | pending |

*Status: pending · green · red · flaky*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sidebar renders devices dynamically | UI-01 | Browser DOM rendering | Navigate to app, verify sidebar shows all devices |
| Sub-tabs work per device | UI-02 | Visual navigation | Click device, verify Dashboard/Registers/Config tabs |
| Venus OS page shows MQTT+ESS+Config | UI-03 | Visual layout | Navigate to Venus OS entry |
| Virtual PV shows stacked bar | UI-04 | Canvas/SVG rendering | Navigate to Virtual PV |
| '+' button adds device | UI-05 | Interactive flow | Click +, add device, verify appears |
| Disable greys out data | UI-06 | Visual state | Toggle off, verify greyed out |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
