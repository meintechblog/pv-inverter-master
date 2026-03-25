---
phase: 33
slug: device-throttle-capabilities-scoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_throttle_caps.py tests/test_plugin.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_throttle_caps.py tests/test_plugin.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | THRT-01 | unit | `python -m pytest tests/test_throttle_caps.py tests/test_plugin.py -x` | ❌ W0 | ⬜ pending |
| 33-01-02 | 01 | 1 | THRT-02 | unit | `python -m pytest tests/test_throttle_caps.py -x` | ❌ W0 | ⬜ pending |
| 33-01-03 | 01 | 1 | THRT-03 | unit | `python -m pytest tests/test_webapp.py -x -k throttle` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_throttle_caps.py` — stubs for THRT-01, THRT-02 (ThrottleCaps dataclass, scoring, per-plugin values)
- [ ] Update `tests/test_plugin.py` — DummyPlugin must implement `throttle_capabilities` (THRT-01)

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
