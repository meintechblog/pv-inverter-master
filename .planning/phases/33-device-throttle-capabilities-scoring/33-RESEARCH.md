# Phase 33: Device Throttle Capabilities & Scoring - Research

**Researched:** 2026-03-25
**Domain:** Python dataclasses, ABC property extension, scoring algorithm, REST API enrichment
**Confidence:** HIGH

## Summary

Phase 33 introduces a `throttle_capabilities` property on the InverterPlugin ABC that each plugin implements, returning a `ThrottleCaps` dataclass describing whether the device supports proportional power limiting, binary (relay on/off) switching, or no throttling at all. A computed `throttle_score` (0-10 scale) derived from these capabilities is exposed via the device list API for use by the distributor in later phases.

This is a pure data-model + property addition phase with no control-flow changes. The distributor does NOT change behavior yet -- it continues using manual `throttle_order`. The score is informational, preparing for Phase 34 (binary throttle engine) and Phase 35 (auto-throttle algorithm).

**Primary recommendation:** Add `ThrottleCaps` dataclass to `plugin.py`, add `throttle_capabilities` as an abstract property on `InverterPlugin`, implement in all three plugins with hardcoded values per success criteria, add a `compute_throttle_score(caps: ThrottleCaps) -> float` pure function, and surface `throttle_score` + `throttle_mode` in `_build_device_list()` and `device_snapshot_handler()`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| THRT-01 | InverterPlugin ABC has a `throttle_capabilities` property returning ThrottleCaps dataclass (mode: proportional/binary/none, response_time_s, cooldown_s, startup_delay_s) | Extend ABC in plugin.py with abstract property; ThrottleCaps as frozen dataclass in same module |
| THRT-02 | SolarEdge=proportional/1s/0s/0s, OpenDTU=proportional/10s/0s/0s, Shelly=binary/0.5s/300s/30s | Hardcoded property implementations in each plugin class |
| THRT-03 | Each device exposes computed throttle_score (0-10) in API; device list includes throttle_score and throttle_mode | Pure scoring function + webapp enrichment in _build_device_list() and snapshot handlers |
</phase_requirements>

## Architecture Patterns

### Current Plugin Architecture (relevant)

```
plugin.py              -- InverterPlugin ABC + PollResult + WriteResult dataclasses
plugins/
  __init__.py          -- plugin_factory()
  solaredge.py         -- SolarEdgePlugin(InverterPlugin)
  opendtu.py           -- OpenDTUPlugin(InverterPlugin)
  shelly.py            -- ShellyPlugin(InverterPlugin)
config.py              -- InverterEntry dataclass (throttle_order, throttle_enabled, throttle_dead_time_s)
distributor.py         -- PowerLimitDistributor (uses throttle_order for waterfall)
webapp.py              -- _build_device_list(), devices_list_handler(), device_snapshot_handler()
```

### Recommended Changes Structure

```
plugin.py              -- ADD: ThrottleCaps dataclass, ThrottleMode enum (or literal),
                          ADD: abstract property throttle_capabilities on InverterPlugin,
                          ADD: compute_throttle_score(caps) pure function
plugins/solaredge.py   -- ADD: throttle_capabilities property
plugins/opendtu.py     -- ADD: throttle_capabilities property
plugins/shelly.py      -- ADD: throttle_capabilities property
webapp.py              -- MODIFY: _build_device_list() and device_snapshot_handler()
                          to include throttle_score and throttle_mode
```

### Pattern 1: ThrottleCaps Dataclass

**What:** A frozen dataclass in `plugin.py` alongside PollResult and WriteResult.
**When to use:** Every plugin returns this from its `throttle_capabilities` property.
**Example:**
```python
# Source: project codebase pattern (dataclasses for all data carriers)
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

ThrottleMode = Literal["proportional", "binary", "none"]

@dataclass(frozen=True)
class ThrottleCaps:
    """Throttle capabilities declared by an inverter plugin."""
    mode: ThrottleMode
    response_time_s: float   # Time to reach target after command
    cooldown_s: float         # Minimum time between commands
    startup_delay_s: float    # Delay after re-enable before expecting output
```

### Pattern 2: Abstract Property on ABC

**What:** Add `throttle_capabilities` as an abstract property, not a method.
**Why property:** It is a static declaration (like `get_model_120_registers`), not a dynamic operation. Using `@property` makes access natural: `plugin.throttle_capabilities.mode`.
**Example:**
```python
# In InverterPlugin ABC:
@property
@abstractmethod
def throttle_capabilities(self) -> ThrottleCaps:
    """Declare this device's throttle capabilities."""
```

### Pattern 3: Pure Scoring Function

**What:** A standalone function `compute_throttle_score(caps: ThrottleCaps) -> float` in `plugin.py`.
**Why pure function:** Testable without plugin instantiation, reusable by distributor in later phases.
**Scoring logic:** Higher score = faster/better regulation capability.
```python
def compute_throttle_score(caps: ThrottleCaps) -> float:
    """Compute throttle speed score 0-10 from capabilities.

    Higher = faster regulation. Proportional > binary > none.
    Within a mode, faster response_time and lower cooldown improve score.
    """
    if caps.mode == "none":
        return 0.0

    # Base score by mode
    if caps.mode == "proportional":
        base = 7.0  # Proportional starts higher
    else:  # binary
        base = 3.0  # Binary is inherently coarser

    # Response time penalty: 0s=+3, 10s=+0 (linear scale)
    response_bonus = max(0.0, 3.0 * (1.0 - caps.response_time_s / 10.0))

    # Cooldown penalty: 0s=+0, 300s=-2 (capped)
    cooldown_penalty = min(2.0, caps.cooldown_s / 150.0)

    # Startup delay penalty: 0s=+0, 30s=-1 (capped)
    startup_penalty = min(1.0, caps.startup_delay_s / 30.0)

    score = base + response_bonus - cooldown_penalty - startup_penalty
    return round(max(0.0, min(10.0, score)), 1)
```

**Expected scores with this formula:**
- SolarEdge (proportional/1s/0s/0s): 7.0 + 2.7 - 0 - 0 = **9.7**
- OpenDTU (proportional/10s/0s/0s): 7.0 + 0.0 - 0 - 0 = **7.0**
- Shelly (binary/0.5s/300s/30s): 3.0 + 2.85 - 2.0 - 1.0 = **2.9**

These scores correctly rank: SolarEdge (fastest proportional) > OpenDTU (slower proportional) > Shelly (binary with cooldown).

### Pattern 4: API Enrichment

**What:** Add `throttle_score` and `throttle_mode` to device list and snapshot responses.
**Where:** In `webapp.py`, modify `_build_device_list()` (line ~842) and `device_snapshot_handler()` (line ~1539).
**How:** Import `compute_throttle_score` from `plugin.py`. For each device, get the plugin from managed devices in app_ctx, call `plugin.throttle_capabilities`, compute score.

**Challenge:** `_build_device_list()` currently only accesses `config.inverters` (InverterEntry) and `app_ctx.devices` (DeviceState). It does NOT directly access the plugin. However, `DeviceState` already has a `plugin` attribute (set in `device_registry.py` line 95).

```python
# In _build_device_list, after building dev_entry:
if ds and ds.plugin and hasattr(ds.plugin, 'throttle_capabilities'):
    caps = ds.plugin.throttle_capabilities
    dev_entry["throttle_mode"] = caps.mode
    dev_entry["throttle_score"] = compute_throttle_score(caps)
else:
    dev_entry["throttle_mode"] = "none"
    dev_entry["throttle_score"] = 0.0
```

### Anti-Patterns to Avoid

- **Storing ThrottleCaps in InverterEntry/config.yaml:** These are intrinsic device capabilities, not user configuration. They belong on the plugin, not the config.
- **Making score configurable:** The score is computed from capabilities. Users configure `throttle_order` (manual override) which remains separate. Score is informational in Phase 33.
- **Changing distributor logic now:** Phase 33 is data-model only. The distributor continues using `throttle_order`. Phase 35 will add auto-throttle based on scores.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Throttle mode enum | String literals everywhere | `Literal["proportional", "binary", "none"]` | Type safety, IDE autocomplete |
| Score computation | Inline in webapp | Pure function in plugin.py | Testable, reusable by distributor |

## Common Pitfalls

### Pitfall 1: Breaking Existing Tests
**What goes wrong:** Adding abstract property to InverterPlugin breaks `test_plugin.py::TestInverterPluginABC::test_concrete_subclass_can_instantiate` because DummyPlugin doesn't implement it.
**Why it happens:** The test creates a minimal concrete subclass.
**How to avoid:** Update DummyPlugin in test_plugin.py to include `throttle_capabilities` property.
**Warning signs:** Test failures immediately after adding abstract property.

### Pitfall 2: Plugin Access in _build_device_list
**What goes wrong:** `_build_device_list` may be called before plugins are connected, or for disabled devices with no DeviceState.
**Why it happens:** Device list is built for all config entries, including disabled ones.
**How to avoid:** Fallback to "none"/0.0 when plugin is not available. For offline/disabled devices, derive throttle_mode from `entry.type` as a static fallback.
**Warning signs:** KeyError or AttributeError in device list endpoint.

### Pitfall 3: Circular Import
**What goes wrong:** Importing from `plugin.py` in `webapp.py` could cause issues if `plugin.py` imports anything from webapp.
**Why it happens:** Python circular import chains.
**How to avoid:** `plugin.py` has zero internal imports (only stdlib). Adding `ThrottleCaps` and `compute_throttle_score` there is safe. `webapp.py` already imports from `plugin` indirectly via other modules.

### Pitfall 4: Frozen Dataclass Default Gotcha
**What goes wrong:** Using mutable defaults in a frozen dataclass.
**Why it happens:** All ThrottleCaps fields are float/str primitives -- this is NOT actually a risk here, but worth noting.
**How to avoid:** All fields are immutable primitives. `frozen=True` is safe.

## Code Examples

### Plugin Implementation (SolarEdge)
```python
# In plugins/solaredge.py, inside SolarEdgePlugin class:
@property
def throttle_capabilities(self) -> ThrottleCaps:
    return ThrottleCaps(
        mode="proportional",
        response_time_s=1.0,
        cooldown_s=0.0,
        startup_delay_s=0.0,
    )
```

### Plugin Implementation (OpenDTU)
```python
# In plugins/opendtu.py, inside OpenDTUPlugin class:
@property
def throttle_capabilities(self) -> ThrottleCaps:
    return ThrottleCaps(
        mode="proportional",
        response_time_s=10.0,
        cooldown_s=0.0,
        startup_delay_s=0.0,
    )
```

### Plugin Implementation (Shelly)
```python
# In plugins/shelly.py, inside ShellyPlugin class:
@property
def throttle_capabilities(self) -> ThrottleCaps:
    return ThrottleCaps(
        mode="binary",
        response_time_s=0.5,
        cooldown_s=300.0,
        startup_delay_s=30.0,
    )
```

### Test Pattern
```python
# In tests/test_throttle_caps.py:
import pytest
from pv_inverter_proxy.plugin import ThrottleCaps, compute_throttle_score

class TestThrottleCaps:
    def test_proportional_scores_higher_than_binary(self):
        prop = ThrottleCaps(mode="proportional", response_time_s=1.0, cooldown_s=0.0, startup_delay_s=0.0)
        binary = ThrottleCaps(mode="binary", response_time_s=0.5, cooldown_s=300.0, startup_delay_s=30.0)
        assert compute_throttle_score(prop) > compute_throttle_score(binary)

    def test_none_scores_zero(self):
        caps = ThrottleCaps(mode="none", response_time_s=0.0, cooldown_s=0.0, startup_delay_s=0.0)
        assert compute_throttle_score(caps) == 0.0

    def test_score_bounded_0_to_10(self):
        extreme = ThrottleCaps(mode="proportional", response_time_s=0.0, cooldown_s=0.0, startup_delay_s=0.0)
        assert 0.0 <= compute_throttle_score(extreme) <= 10.0

    def test_solaredge_caps(self):
        caps = ThrottleCaps(mode="proportional", response_time_s=1.0, cooldown_s=0.0, startup_delay_s=0.0)
        score = compute_throttle_score(caps)
        assert score > 9.0  # Fast proportional

    def test_shelly_caps(self):
        caps = ThrottleCaps(mode="binary", response_time_s=0.5, cooldown_s=300.0, startup_delay_s=30.0)
        score = compute_throttle_score(caps)
        assert 2.0 < score < 4.0  # Binary with high cooldown
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_throttle_caps.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| THRT-01 | ThrottleCaps dataclass + abstract property on ABC | unit | `python -m pytest tests/test_throttle_caps.py tests/test_plugin.py -x` | Wave 0 |
| THRT-02 | Per-plugin hardcoded capabilities values | unit | `python -m pytest tests/test_throttle_caps.py -x` | Wave 0 |
| THRT-03 | API returns throttle_score and throttle_mode | unit | `python -m pytest tests/test_webapp.py -x -k throttle` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_throttle_caps.py tests/test_plugin.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_throttle_caps.py` -- covers THRT-01, THRT-02 (ThrottleCaps, scoring, per-plugin values)
- [ ] Update `tests/test_plugin.py` -- DummyPlugin must implement `throttle_capabilities` (THRT-01)

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/pv_inverter_proxy/plugin.py` -- current ABC with 6 abstract methods
- Project codebase: `src/pv_inverter_proxy/plugins/` -- all 3 plugin implementations
- Project codebase: `src/pv_inverter_proxy/webapp.py` -- `_build_device_list()` at line 829
- Project codebase: `src/pv_inverter_proxy/config.py` -- InverterEntry with existing throttle fields
- Project codebase: `src/pv_inverter_proxy/distributor.py` -- current waterfall using throttle_order
- Project codebase: `src/pv_inverter_proxy/context.py` -- DeviceState with plugin reference

### Secondary (MEDIUM confidence)
- Python stdlib `dataclasses` documentation -- `frozen=True` for immutable value objects
- Python `typing.Literal` -- for ThrottleMode type alias

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pure Python dataclasses, no new dependencies
- Architecture: HIGH - extends existing ABC pattern, well-understood codebase
- Pitfalls: HIGH - identified from actual test files and code paths
- Scoring algorithm: MEDIUM - formula is reasonable but may need tuning in Phase 35

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable -- no external dependencies to go stale)
