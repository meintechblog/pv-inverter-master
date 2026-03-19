---
phase: 14
slug: config-page-dashboard-ux
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 14 — Validation Strategy

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
| TBD | 01 | 1 | CFG-01, CFG-02 | unit+manual | `pytest tests/ -k config` | ✅ | ⬜ pending |
| TBD | 02 | 2 | SETUP-02, SETUP-03 | unit+manual | `pytest tests/ -k mqtt_gate or dashboard` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test stubs for MQTT gate CSS class verification (if backend-testable)

*Existing test infrastructure covers config API and webapp handlers.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Config page shows pre-filled defaults on first visit | CFG-01 | Visual UI check | Load config page fresh, verify fields show 192.168.3.18:1502 |
| Connection bobble turns green/red/amber after Save | CFG-02 | WebSocket visual feedback | Save config, observe bobble color change |
| MQTT setup guide card appears when disconnected | SETUP-02 | Visual UI card | Disconnect MQTT, verify hint card visible |
| MQTT-gated elements greyed out with overlay | SETUP-03 | Visual CSS check | Disconnect MQTT, verify Lock Toggle greyed |
| Power gauge/slider remain functional without MQTT | SETUP-03 | Visual UI check | Disconnect MQTT, verify gauge still animates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
