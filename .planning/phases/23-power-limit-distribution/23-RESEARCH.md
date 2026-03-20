# Phase 23: Power Limit Distribution - Research

**Researched:** 2026-03-20
**Domain:** Power limit distribution across heterogeneous inverters (asyncio, SunSpec Model 123)
**Confidence:** HIGH

## Summary

Phase 23 replaces the current single-plugin power limit forwarding (or the Phase 22 stub that logs "not available until Phase 23") with a PowerLimitDistributor that implements a waterfall algorithm. Venus OS sends a single WMaxLimPct value representing a percentage of the virtual inverter's total rated power. The distributor converts this to absolute watts, then distributes the allowed power budget across inverters using Throttling Order (TO) priority: TO 1 gets throttled first (down to 0%), then TO 2, and so on.

The existing codebase provides all necessary building blocks: `ControlState` for tracking the Venus OS limit, `InverterPlugin.write_power_limit(enable, limit_pct)` implemented by both SolarEdge and OpenDTU plugins, `AggregationLayer._update_wrtg()` which already computes total rated power, and `DeviceRegistry` with `ManagedDevice` providing access to all active plugins. The main work is a new `PowerLimitDistributor` class, three new fields on `InverterEntry`, and rewiring `StalenessAwareSlaveContext` to call the distributor instead of a single plugin.

**Primary recommendation:** Create a single `PowerLimitDistributor` class in a new `distributor.py` module that encapsulates the waterfall algorithm, dead-time management, and offline failover. Wire it into `StalenessAwareSlaveContext` via the existing `_handle_local_control_write` path (replacing the Phase 22 stub).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Begriff: "Throttling Order" (TO) statt "Prioritaet" -- TO 1 = wird als ERSTES gedrosselt, TO 2 = danach, etc.
- Wasserfall-Prinzip: TO 1 wird komplett runtergedreht (bis 0% wenn noetig). Erst wenn TO 1 am Minimum, wird TO 2 gedrosselt
- Minimum pro Inverter: 0% (komplett aus) -- kein Hardware-Minimum-Clamp
- Umrechnung: Venus OS WMaxLimPct (Prozent der Gesamtnennleistung) -> absolute Watt -> Wasserfall-Verteilung auf einzelne Inverter -> pro Inverter Prozentwert berechnen und senden
- Gleiche TO-Nummer erlaubt: Inverter mit gleicher TO werden gleichmaessig aufgeteilt (50/50)
- 3 Zustaende pro Inverter: Enabled (voll) / Monitoring-Only / Disabled
- Monitoring-Only = Throttle-Checkbox unchecked: Polling ja, Daten fliessen in Aggregation, aber KEIN Limit-Befehl wird gesendet
- Dead-Time pro Device konfigurierbar: Default = 0s
- Config-Felder: `throttle_order: int`, `throttle_enabled: bool`, `throttle_dead_time_s: float` in InverterEntry
- Waehrend Dead-Time: neue Venus OS Befehle werden zwischengespeichert und nach Ablauf angewandt (latest wins)
- Bei Offline eines Inverters waehrend aktivem Limit: Anteil wird sofort auf naechste in TO-Reihenfolge umverteilt

### Claude's Discretion
- Internes Datenmodell fuer Limit-State pro Device
- Wie die Umrechnung Prozent -> Watt -> pro-Device exakt implementiert wird
- Error-Handling bei fehlgeschlagenem Limit-Write
- Ob Limit-Aenderungen geloggt werden (empfohlen: ja, structlog)

### Deferred Ideas (OUT OF SCOPE)
- Live-Test des Regelverhaltens mit echten Invertern -- nach Deploy auf LXC (manuelle Session)
- UI-Darstellung der Throttling Order und Throttle-Checkbox -- Phase 24
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PWR-01 | User definiert Prioritaets-Reihenfolge: welcher Inverter bei Limitierung zuerst gedrosselt wird | `throttle_order: int` on InverterEntry, waterfall algorithm sorts by TO ascending |
| PWR-02 | Individuelle Inverter koennen vom Regelverhalten ausgeschlossen werden (nur Monitoring) | `throttle_enabled: bool` on InverterEntry; distributor skips these for limit writes but includes their power in aggregation |
| PWR-03 | Distribution beruecksichtigt unterschiedliche Latenzzeiten (SolarEdge instant vs Hoymiles 25s) | `throttle_dead_time_s: float` per device; distributor tracks per-device dead-time with latest-wins buffering |
| PWR-04 | Power Limit wird anteilig nach Prioritaet auf die Inverter verteilt (hoechste Prio wird zuerst gedrosselt) | Waterfall: TO 1 throttled to 0% first, then TO 2, with same-TO split equally |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio | stdlib | Concurrent limit writes | Already used throughout project |
| structlog | 24.x | Logging limit distribution events | Project convention per CLAUDE.md |
| dataclasses | stdlib | DeviceLimitState, config fields | Project convention per config.py pattern |

### Supporting
No new dependencies needed. All building blocks exist in-project.

## Architecture Patterns

### Recommended Project Structure
```
src/venus_os_fronius_proxy/
  distributor.py          # NEW: PowerLimitDistributor class
  config.py               # MODIFIED: add 3 fields to InverterEntry
  proxy.py                # MODIFIED: wire distributor into StalenessAwareSlaveContext
  control.py              # UNCHANGED (reuse ControlState as-is)
  plugin.py               # UNCHANGED (write_power_limit interface already correct)
  device_registry.py      # UNCHANGED (provides ManagedDevice access)
  aggregation.py          # UNCHANGED (already computes total_rated via _update_wrtg)
```

### Pattern 1: PowerLimitDistributor (New Module)

**What:** A class that receives a WMaxLimPct command from Venus OS and distributes it across N inverter plugins using the waterfall algorithm.

**When to use:** Every time Venus OS writes to Model 123 WMaxLimPct or WMaxLim_Ena registers.

**Design:**
```python
@dataclass
class DeviceLimitState:
    """Per-device limit tracking."""
    device_id: str
    entry: InverterEntry          # for rated_power, throttle_order, throttle_enabled
    plugin: InverterPlugin        # for write_power_limit()
    current_limit_pct: float = 100.0   # last sent to this device
    last_write_ts: float = 0.0         # monotonic time of last write
    pending_limit_pct: float | None = None  # buffered during dead-time
    is_online: bool = True

class PowerLimitDistributor:
    def __init__(self, app_ctx: AppContext, config: Config):
        self._app_ctx = app_ctx
        self._config = config
        self._device_states: dict[str, DeviceLimitState] = {}
        self._global_limit_pct: float = 100.0  # last Venus OS command
        self._enabled: bool = False

    async def distribute(self, limit_pct: float, enable: bool) -> None:
        """Main entry: convert global % to per-device limits via waterfall."""

    def _waterfall(self, allowed_watts: float) -> dict[str, float]:
        """Pure function: returns {device_id: limit_pct} mapping."""

    async def _send_limit(self, device_id: str, limit_pct: float) -> None:
        """Send limit to one device, respecting dead-time."""

    async def on_device_offline(self, device_id: str) -> None:
        """Redistribute when a device goes offline."""

    def sync_devices(self) -> None:
        """Sync internal state with DeviceRegistry (add/remove tracking)."""
```

### Pattern 2: Waterfall Algorithm (Pure Function)

**What:** Given total allowed watts, distribute across devices sorted by TO.

**Algorithm:**
```python
def _waterfall(self, allowed_watts: float) -> dict[str, float]:
    # 1. Collect throttle-eligible devices (throttle_enabled=True, online)
    # 2. Sort by throttle_order ascending (TO 1 first)
    # 3. Group by throttle_order (same TO = split equally)
    # 4. Walk groups: each group gets min(their_total_rated, remaining_budget)
    #    - If budget < group_rated: split budget equally within group
    #    - If budget >= group_rated: group runs at 100%, budget -= group_rated
    # 5. Convert each device's allowed watts to percentage of its rated_power
    # 6. Non-throttle-eligible devices get 100% (no limit sent)

    result = {}
    remaining = allowed_watts

    # Group by TO
    from itertools import groupby
    eligible = sorted(
        [ds for ds in self._device_states.values()
         if ds.entry.throttle_enabled and ds.is_online],
        key=lambda ds: ds.entry.throttle_order,
    )

    for to_num, group_iter in groupby(eligible, key=lambda ds: ds.entry.throttle_order):
        group = list(group_iter)
        group_rated = sum(ds.entry.rated_power for ds in group)

        if remaining >= group_rated:
            # This group runs at 100%
            for ds in group:
                result[ds.device_id] = 100.0
            remaining -= group_rated
        else:
            # This group gets throttled - split remaining equally
            for ds in group:
                share = (remaining / len(group))
                result[ds.device_id] = (share / ds.entry.rated_power) * 100.0 if ds.entry.rated_power > 0 else 0.0
            remaining = 0.0

        # After this group, if remaining is 0, subsequent groups get 0%
        if remaining <= 0:
            # All remaining eligible devices get 0%
            break

    # Any eligible device not yet assigned gets 0%
    for ds in self._device_states.values():
        if ds.device_id not in result and ds.entry.throttle_enabled and ds.is_online:
            result[ds.device_id] = 0.0

    return result
```

### Pattern 3: Dead-Time with Latest-Wins Buffering

**What:** Per-device dead-time suppresses rapid re-sends. During dead-time, the latest command is buffered and applied after expiry.

**Design:**
```python
async def _send_limit(self, device_id: str, limit_pct: float) -> None:
    ds = self._device_states[device_id]
    now = time.monotonic()
    elapsed = now - ds.last_write_ts

    if elapsed < ds.entry.throttle_dead_time_s:
        # Buffer (latest wins)
        ds.pending_limit_pct = limit_pct
        return

    # Actually send
    result = await ds.plugin.write_power_limit(True, limit_pct)
    if result.success:
        ds.current_limit_pct = limit_pct
        ds.last_write_ts = now
        ds.pending_limit_pct = None
    else:
        log.warning("limit_write_failed", device_id=device_id, error=result.error)
```

**Flushing buffered commands:** A periodic task (or check on next distribute call) should flush pending limits after dead-time expires.

### Pattern 4: Integration Point - Rewiring proxy.py

**What:** Replace the Phase 22 stub in `_handle_local_control_write` and `async_setValues` to call `PowerLimitDistributor.distribute()`.

**Current code (proxy.py line 135-145):**
```python
else:
    # No plugin available -- accept write locally but log warning
    # Power limit forwarding deferred to Phase 23 (PowerLimitDistributor)
    control_log.warning(
        "power_limit_forwarding_not_available_until_phase_23",
        ...
    )
    self._handle_local_control_write(abs_addr, values)
```

**New behavior:**
- `StalenessAwareSlaveContext.__init__` receives `distributor: PowerLimitDistributor | None` parameter
- `async_setValues` calls `_handle_local_control_write` (for ControlState update) then `distributor.distribute()`
- The existing `_handle_local_control_write` already correctly updates ControlState, clamp, persist -- keep it
- After local state update, call `await self._distributor.distribute(control.wmaxlimpct_float, control.is_enabled)`

### Anti-Patterns to Avoid
- **Moving dead-time logic into the distributor AND leaving it in OpenDTU plugin:** The OpenDTU plugin already has a 30s DEAD_TIME_S guard. The distributor's per-device `throttle_dead_time_s` (default 0s) is a DIFFERENT concept -- it's about the distributor holding back commands, not the plugin. For SolarEdge (instant), keep default 0s. For OpenDTU, the plugin's own dead-time still applies. Do NOT duplicate or conflict.
- **Calling write_power_limit on monitoring-only devices:** Skip entirely, do not send enable=False or 100%.
- **Forgetting to handle WMaxLim_Ena=0 (disable):** When Venus OS disables limiting, distributor must send 100% to all throttle-eligible devices.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Grouping by TO number | Manual nested loops | `itertools.groupby` on sorted list | Cleaner, handles edge cases |
| Periodic dead-time flush | Custom timer threads | `asyncio.create_task` with sleep loop | Fits project async pattern |
| Config field defaults | Manual default handling | Dataclass field defaults | Consistent with existing InverterEntry |

## Common Pitfalls

### Pitfall 1: Division by Zero on rated_power=0
**What goes wrong:** If an inverter has `rated_power=0` (unknown), waterfall math divides by zero.
**Why it happens:** New inverters default to `rated_power=0`.
**How to avoid:** Skip devices with `rated_power=0` from throttle eligibility. Log a warning that the device cannot be throttled until rated_power is configured.
**Warning signs:** ZeroDivisionError in waterfall calculation.

### Pitfall 2: Double Dead-Time Suppression
**What goes wrong:** Distributor dead-time (throttle_dead_time_s) AND OpenDTU plugin dead-time (DEAD_TIME_S=30s) both suppress writes, causing commands to be dropped silently for 60s.
**Why it happens:** Two independent dead-time guards stacking.
**How to avoid:** The distributor dead-time defaults to 0s, which is correct for both SolarEdge (instant) and OpenDTU (plugin handles its own). Only set distributor dead-time if there is a reason beyond what the plugin already handles. Document this clearly.
**Warning signs:** Limit commands taking much longer than expected to apply.

### Pitfall 3: Race Between distribute() and device add/remove
**What goes wrong:** DeviceRegistry adds/removes a device while distribute() is iterating over device states.
**Why it happens:** Both are async, no locking.
**How to avoid:** `sync_devices()` copies a snapshot of the device list at the start of distribute(). Use dict snapshot (`dict(self._device_states)`) for iteration.
**Warning signs:** KeyError during iteration.

### Pitfall 4: Stale Limit After Device Comes Back Online
**What goes wrong:** A device was offline, its share was redistributed. When it comes back online, it still runs at its pre-offline limit.
**Why it happens:** No re-distribution triggered on reconnection.
**How to avoid:** After `on_poll_success` detects a previously-offline device is back, call `distributor.redistribute()` to recalculate.
**Warning signs:** Total system power exceeding Venus OS limit after device recovery.

### Pitfall 5: SolarEdge 1% Minimum vs 0% Decision
**What goes wrong:** User decided 0% minimum (komplett aus), but SolarEdge plugin clamps to 1% (see solaredge.py line 166: `max(1, ...)`). Setting SE30K to 0% causes it to shut down with ~10s restart.
**Why it happens:** Hardware limitation documented in control.py comments.
**How to avoid:** Let the plugin handle its own minimum. The distributor sends 0%, and the SolarEdge plugin clamps to 1% internally. This preserves the user's "0% minimum" decision while respecting hardware limits.
**Warning signs:** SE30K shutdown/restart oscillation.

## Code Examples

### InverterEntry Config Changes
```python
# In config.py - add to InverterEntry dataclass
@dataclass
class InverterEntry:
    # ... existing fields ...
    throttle_order: int = 1           # TO 1 = first to throttle
    throttle_enabled: bool = True     # False = monitoring-only
    throttle_dead_time_s: float = 0.0 # Per-device dead-time (seconds)
```

### Distributor Initialization in __main__.py
```python
# After DeviceRegistry and AggregationLayer setup
from venus_os_fronius_proxy.distributor import PowerLimitDistributor

distributor = PowerLimitDistributor(app_ctx, config)

# Pass to StalenessAwareSlaveContext (modify run_modbus_server or post-init)
slave_ctx._distributor = distributor
```

### Wiring in proxy.py async_setValues
```python
# In async_setValues, replace the Phase 22 stub:
if self._control is not None and self._control.is_model_123_address(abs_addr, len(values)):
    self._handle_local_control_write(abs_addr, values)
    if self._distributor is not None:
        await self._distributor.distribute(
            self._control.wmaxlimpct_float,
            self._control.is_enabled,
        )
    return
```

### Percent-to-Watt-to-Per-Device Conversion
```python
# Venus OS sends: WMaxLimPct = 50 (50% of total rated power)
# Total rated: 31000W (SE30K=30000W + HM-800=800W + HM-800=800W)
# Allowed watts: 0.50 * 31000 = 15500W

# Waterfall with TO 1=SE30K, TO 2=HM-800-A, TO 2=HM-800-B:
# TO 1 (SE30K, 30000W): allowed=15500W < 30000W -> SE30K gets 15500W -> 51.67%
# TO 2: remaining=0W -> both HM-800 get 0% -> 0W
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single plugin power limit (proxy.py `_handle_control_write`) | Multi-device distribution via PowerLimitDistributor | Phase 23 | Enables multi-inverter ESS regulation |
| Hardcoded DEAD_TIME_S=30s in OpenDTU plugin | Per-device configurable `throttle_dead_time_s` at distributor level | Phase 23 | Flexible latency handling per device type |

## Open Questions

1. **edpc_refresh_loop compatibility**
   - What we know: `edpc_refresh_loop` in control.py periodically re-sends webapp-initiated limits to a single plugin. This was designed for single-plugin operation.
   - What's unclear: Should this loop be refactored to use the distributor, or is it only relevant for webapp source (which may not need multi-device distribution)?
   - Recommendation: Keep edpc_refresh_loop for webapp-source only. Venus OS manages its own refresh (writes every 5s). The distributor only needs to handle Venus OS writes. If webapp power control needs multi-device support later, refactor then.

2. **Offline detection mechanism**
   - What we know: `ConnectionManager` tracks connection state per device (connected/backoff/disconnected).
   - What's unclear: How does the distributor know a device went offline? There is no callback from DeviceRegistry on state change.
   - Recommendation: Distributor checks `conn_mgr.state` at distribution time (pull, not push). If a device is in `disconnected` or `backoff` state, treat as offline for distribution purposes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_distributor.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PWR-01 | Waterfall distributes by throttle_order | unit | `python -m pytest tests/test_distributor.py::test_waterfall_to_ordering -x` | Wave 0 |
| PWR-01 | Same TO number splits equally | unit | `python -m pytest tests/test_distributor.py::test_same_to_equal_split -x` | Wave 0 |
| PWR-02 | Monitoring-only devices excluded from limits | unit | `python -m pytest tests/test_distributor.py::test_monitoring_only_excluded -x` | Wave 0 |
| PWR-02 | Monitoring-only power still counted in aggregation | unit | `python -m pytest tests/test_distributor.py::test_monitoring_power_counted -x` | Wave 0 |
| PWR-03 | Dead-time buffers commands (latest wins) | unit | `python -m pytest tests/test_distributor.py::test_dead_time_buffering -x` | Wave 0 |
| PWR-04 | Global percent to per-device watts to per-device percent | unit | `python -m pytest tests/test_distributor.py::test_pct_watt_conversion -x` | Wave 0 |
| PWR-04 | Offline device share redistributed | unit | `python -m pytest tests/test_distributor.py::test_offline_redistribution -x` | Wave 0 |
| PWR-04 | Disable (ena=0) sends 100% to all | unit | `python -m pytest tests/test_distributor.py::test_disable_sends_100 -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_distributor.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_distributor.py` -- all PWR-* tests above
- [ ] `tests/test_config.py` -- add tests for new InverterEntry fields (throttle_order, throttle_enabled, throttle_dead_time_s)

## Sources

### Primary (HIGH confidence)
- `src/venus_os_fronius_proxy/control.py` -- ControlState, WMaxLimPct validation, clamp logic
- `src/venus_os_fronius_proxy/proxy.py` -- StalenessAwareSlaveContext write handling, Phase 22 stubs
- `src/venus_os_fronius_proxy/plugin.py` -- InverterPlugin ABC with write_power_limit interface
- `src/venus_os_fronius_proxy/device_registry.py` -- DeviceRegistry, ManagedDevice structure
- `src/venus_os_fronius_proxy/aggregation.py` -- AggregationLayer, total rated power calculation
- `src/venus_os_fronius_proxy/config.py` -- InverterEntry dataclass
- `src/venus_os_fronius_proxy/plugins/solaredge.py` -- SolarEdge write_power_limit (instant, min 1%)
- `src/venus_os_fronius_proxy/plugins/opendtu.py` -- OpenDTU write_power_limit (30s dead-time guard)
- `23-CONTEXT.md` -- All user decisions locked

### Secondary (MEDIUM confidence)
- OpenDTU dead-time (25-30s) estimated from GitHub issues -- validated in Phase 21

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all in-project
- Architecture: HIGH -- all integration points inspected, Phase 22 stubs clearly mark where to wire
- Pitfalls: HIGH -- identified from actual code inspection (SolarEdge 1% clamp, OpenDTU dead-time, rated_power=0)

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable domain, no external dependency changes expected)
