---
phase: 38
slug: plugin-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/test_sungrow_plugin.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_sungrow_plugin.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | PLUG-01 | — | N/A | unit | `python -m pytest tests/test_sungrow_plugin.py::test_connect -x` | ❌ W0 | ⬜ pending |
| 38-01-02 | 01 | 1 | PLUG-01 | — | N/A | unit | `python -m pytest tests/test_sungrow_plugin.py::test_poll_registers -x` | ❌ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | PLUG-02 | — | N/A | unit | `python -m pytest tests/test_sungrow_plugin.py::test_encode_model_103 -x` | ❌ W0 | ⬜ pending |
| 38-01-04 | 01 | 1 | PLUG-03 | — | N/A | unit | `python -m pytest tests/test_sungrow_plugin.py::test_reconfigure -x` | ❌ W0 | ⬜ pending |
| 38-01-05 | 01 | 1 | PLUG-04 | — | N/A | unit | `python -m pytest tests/test_sungrow_plugin.py::test_throttle_caps -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sungrow_plugin.py` — stubs for PLUG-01 through PLUG-04
- [ ] Mock fixtures for pymodbus AsyncModbusTcpClient

*Existing infrastructure covers pytest setup and conftest.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Modbus TCP connection to Sungrow at 192.168.2.151:502 | PLUG-01 | Requires physical device on network | Run proxy with sungrow plugin configured, verify poll logs show real register values |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
