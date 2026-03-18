---
phase: 02
slug: core-proxy-read-path
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (already in pyproject.toml) |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-02 | 01 | 1 | PROXY-04, PROXY-05, PROXY-07, PROXY-08 | unit | `python -m pytest tests/test_sunspec_models.py -v` | tests/test_sunspec_models.py | pending |
| 02-01-03 | 01 | 1 | ARCH-01, ARCH-02 | unit | `python -m pytest tests/test_register_cache.py -v` | tests/test_register_cache.py | pending |
| 02-02-01 | 02 | 2 | PROXY-03, PROXY-06 | unit | `python -m pytest tests/test_solaredge_plugin.py -v` | tests/test_solaredge_plugin.py | pending |
| 02-02-02 | 02 | 2 | PROXY-01, PROXY-09 | integration | `python -m pytest tests/test_proxy.py -v --timeout=30` | tests/test_proxy.py | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_sunspec_models.py` — tests for SunSpec model chain builder (build_initial_registers, encode_string, apply_common_translation)
- [ ] `tests/test_register_cache.py` — tests for cache staleness tracking (starts stale, update resets, configurable timeout)
- [ ] `tests/test_solaredge_plugin.py` — tests for SolarEdge plugin (interface, polling, overrides, model 120)
- [ ] `tests/test_proxy.py` — integration tests for proxy server (connection, discovery flow, cache serving, staleness errors, unit ID filtering)
- [ ] `tests/conftest.py` — shared fixtures (mock SE30K registers, test cache) if needed

*Existing infrastructure: pytest already configured, 27 register mapping tests passing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Venus OS discovers proxy as Fronius | PROXY-09 | Requires live Venus OS instance | 1. Start proxy on LXC. 2. Add device in Venus OS at 192.168.3.191:502. 3. Verify "Fronius" appears in device list. |
| Live power data displays correctly | PROXY-03 | Requires live SE30K + Venus OS | 1. Run proxy during daytime. 2. Check Venus OS shows non-zero power. 3. Compare with SE30K direct readings. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
