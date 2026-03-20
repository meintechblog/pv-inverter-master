---
phase: 17
slug: discovery-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | DISC-01 | unit | `pytest tests/test_scanner.py -k test_tcp_port_scan` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | DISC-02 | unit | `pytest tests/test_scanner.py -k test_sunspec_verification` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 1 | DISC-03 | unit | `pytest tests/test_scanner.py -k test_common_block_read` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 1 | DISC-04 | unit | `pytest tests/test_scanner.py -k test_unit_id_scan` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scanner.py` — stubs for DISC-01 through DISC-04
- [ ] Mock fixtures for AsyncModbusTcpClient responses (SunSpec header, Common Block)

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real network scan finds inverter | DISC-01..04 | Requires LAN with real Modbus device | Run scan on 192.168.3.0/24, verify SE30K found |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
