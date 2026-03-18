# Phase 3: Control Path & Production Hardening - Research

**Researched:** 2026-03-18
**Domain:** Modbus write-path translation, reconnection logic, systemd service, structured logging
**Confidence:** HIGH

## Summary

Phase 3 adds the write path (Venus OS power control via SunSpec Model 123 translated to SolarEdge proprietary registers), production hardening (reconnection with exponential backoff, night mode), systemd service integration, and structured JSON logging. The existing Phase 2 codebase provides solid foundations: `StalenessAwareSlaveContext` already overrides `getValues()` and can be extended with `setValues()` interception; the `InverterPlugin` ABC needs a `write()` method; and the `SolarEdgePlugin` needs write capability to SE proprietary registers (0xF300-0xF322).

The pymodbus 3.8.6 server processes writes through `context.async_setValues()` which calls `context.setValues()` synchronously. This means overriding `setValues()` on `StalenessAwareSlaveContext` is the correct interception point for write validation and forwarding. Validation failures should raise exceptions to trigger pymodbus ExceptionResponse (same pattern already used for staleness).

**Primary recommendation:** Extend `StalenessAwareSlaveContext.setValues()` to intercept Model 123 writes, validate values, and forward to SolarEdge via the plugin's new `write()` method. Use structlog 25.x for JSON logging. Use PyYAML (already available) for config. Implement reconnection as an async state machine in the poll loop.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Forward WMaxLimPct writes immediately to SE30K proprietary registers -- no proxy-side ramping (SolarEdge firmware handles its own internal ramp)
- Reject invalid values (>100%, negative, NaN) with Modbus ILLEGAL_DATA_VALUE (0x03) exception -- never forward bad values to inverter
- Model 123 registers are readable -- proxy stores last-written WMaxLimPct and returns it on read
- WMaxLim_Ena defaults to DISABLED (0) on proxy startup -- Venus OS must explicitly enable throttling before power limits take effect
- On graceful shutdown (SIGTERM): send WMaxLimPct=100% (no limit) to SE30K before stopping
- After reconnect: restore last-set power limit to SE30K
- Exponential backoff on connection loss: start at 5s, double each attempt, max 60s, reset to 5s after successful reconnect
- Night/sleeping detection: if SE30K connection fails consistently for >5 minutes, enter night mode
- Night mode behavior: serve zero-power registers (AC power=0, energy unchanged, inverter status=SLEEPING/4), keep SunSpec model chain intact -- no staleness errors
- Short outages (<5 min): use existing 30s staleness timeout from Phase 2 (return Modbus errors)
- Exit night mode when SE30K becomes reachable again -- resume normal polling
- JSON structured logging to stdout (systemd journal captures it)
- Log fields: timestamp, level, message, component (poller/server/control/health)
- INFO level events: startup/shutdown with config summary, connection state changes, every control command, health heartbeat every 5 minutes
- Health heartbeat includes: poll success rate, cache age, active connections count, last control value
- DEBUG level: per-poll register dumps -- only visible when explicitly enabled
- WARNING level: validation rejections, reconnect attempts, staleness events
- ERROR level: unrecoverable failures, repeated reconnect failures
- YAML config file at /etc/venus-os-fronius-proxy/config.yaml -- SE30K IP/port, poll interval, log level, night mode timeout
- systemd unit: Restart=on-failure, RestartSec=5, clean shutdown on SIGTERM does not trigger restart
- Run as dedicated user with AmbientCapabilities=CAP_NET_BIND_SERVICE for port 502 binding
- Graceful shutdown: catch SIGTERM, remove power limit from SE30K (set 100%), close connections, exit 0

### Claude's Discretion
- Plugin interface extension for write path (add write method to InverterPlugin ABC)
- YAML config schema and defaults
- Exact systemd unit file structure (After=, Wants=, etc.)
- Night mode state machine implementation details
- Python logging configuration (structlog vs stdlib json formatter)
- How to handle concurrent control writes (queue vs last-write-wins)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CTRL-01 | Venus OS kann Leistungsbegrenzung setzen via SunSpec Model 123 | pymodbus setValues override intercepts writes at Model 123 addresses (40149-40174), validates, forwards to SE30K |
| CTRL-02 | Leistungsbegrenzung wird korrekt an SolarEdge SE30K weitergeleitet | Write translation table (WMaxLimPct -> 0xF322 Float32, WMaxLim_Ena -> 0xF300) with struct.pack for encoding |
| CTRL-03 | Steuerungsbefehle werden validiert bevor sie an den Inverter gesendet werden | Validation in setValues override: range check 0-100%, NaN check, return ILLEGAL_VALUE (0x03) on failure |
| DEPL-01 | Laeuft als systemd Service mit Auto-Start und Restart-on-Failure | systemd unit file with Restart=on-failure, RestartSec=5, AmbientCapabilities for port 502 |
| DEPL-02 | Automatische Reconnection bei Verbindungsabbruch zum SolarEdge | Exponential backoff state machine in poll loop: 5s initial, double to 60s max, reset on success |
| DEPL-03 | Graceful Handling wenn Inverter offline (Nacht/Wartung) | Night mode state machine: >5 min connection failure -> serve synthetic zero-power registers with SLEEPING status |
| DEPL-04 | Strukturiertes Logging (JSON) fuer systemd Journal | structlog 25.x with JSONRenderer to stdout, systemd journal captures automatically |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pymodbus | 3.8.6 | Modbus TCP server + client (already in use) | Already the project foundation; write interception via setValues override is well-supported |
| structlog | 25.5.0 | Structured JSON logging | Industry standard for Python structured logging; processor pipeline, JSON renderer, stdlib integration |
| PyYAML | 6.0.3 | YAML config file parsing | Already installed on target system; lightweight, no extra dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Testing (already in dev deps) | All unit and integration tests |
| pytest-asyncio | >=0.23 | Async test support (already in dev deps) | Testing async reconnection, write forwarding |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| structlog | stdlib json.Formatter | structlog has better processor pipeline, context binding, and cleaner API; stdlib requires more boilerplate |
| PyYAML | TOML (tomllib) | YAML is the locked decision; tomllib would need different config syntax |

**Installation:**
```bash
pip install "structlog>=25.0,<26.0" "PyYAML>=6.0,<7.0"
```

**Version verification:** pymodbus 3.8.6 (installed), structlog 25.5.0 (latest on PyPI), PyYAML 6.0.3 (installed).

## Architecture Patterns

### Recommended Project Structure
```
src/venus_os_fronius_proxy/
  plugin.py              # InverterPlugin ABC + PollResult + WriteResult (extend)
  proxy.py               # StalenessAwareSlaveContext (extend setValues), run_proxy (extend with reconnect + shutdown)
  register_cache.py      # RegisterCache (extend with control state tracking)
  control.py             # NEW: ControlState, Model 123 write validation + translation
  connection.py          # NEW: ConnectionManager with reconnect + night mode state machine
  config.py              # NEW: YAML config loading with dataclass schema
  logging_config.py      # NEW: structlog configuration
  night_mode.py          # NEW: Night mode synthetic register generator
  sunspec_models.py      # Existing (no changes expected)
  plugins/
    solaredge.py         # SolarEdgePlugin (extend with write method)
  __main__.py            # Entry point (rewrite: config loading, signal handling, structured logging)
config/
  config.example.yaml    # Example configuration file
  venus-os-fronius-proxy.service  # systemd unit file
```

### Pattern 1: Write Interception via setValues Override
**What:** Override `StalenessAwareSlaveContext.setValues()` to intercept writes to Model 123 address range, validate, and forward to inverter.
**When to use:** Whenever Venus OS writes to holding registers in the Model 123 range (40149-40174).
**Example:**
```python
# Source: pymodbus 3.8.6 source code inspection
class StalenessAwareSlaveContext(ModbusSlaveContext):
    def setValues(self, fc_as_hex, address, values):
        """Intercept writes to Model 123 registers."""
        # address is 0-based in pymodbus (already +1 in the method)
        # Model 123 range: proxy addresses 40149-40174
        # After +1 adjustment, address param is 0-based offset
        abs_address = address  # pymodbus adds +1 internally before calling datablock

        # Check if write targets Model 123 control registers
        if self._is_model_123_write(abs_address, len(values)):
            # Validate and forward (async via event loop)
            self._handle_control_write(abs_address, values)
            return

        # For non-control writes, store normally
        super().setValues(fc_as_hex, address, values)
```

**Critical detail:** `setValues` is synchronous but `update_datastore` is async and calls `async_setValues` which calls `setValues`. To forward writes to SE30K (async operation), the control write handler must schedule the async write. However, since pymodbus server runs in asyncio, `asyncio.get_event_loop().create_task()` can be used. Alternatively, override `async_setValues` directly for cleaner async handling.

### Pattern 2: Override async_setValues Instead
**What:** Override `async_setValues()` on `StalenessAwareSlaveContext` for native async write handling.
**When to use:** Preferred approach -- cleaner than scheduling from synchronous context.
**Example:**
```python
# Source: pymodbus 3.8.6 ModbusSlaveContext.async_setValues
async def async_setValues(self, fc_as_hex, address, values):
    """Intercept writes with native async support."""
    if self._is_model_123_address(address, len(values)):
        # Validate
        validation_error = self._control.validate_write(address, values)
        if validation_error:
            raise Exception(validation_error)  # -> ExceptionResponse 0x04

        # Forward to inverter (async)
        await self._plugin.write(address, values)

        # Store locally for read-back
        self.setValues(fc_as_hex, address, values)
        return

    # Default behavior for non-control writes
    self.setValues(fc_as_hex, address, values)
```

**IMPORTANT:** Raising an exception from `async_setValues` causes pymodbus to return SLAVE_FAILURE (0x04). For ILLEGAL_VALUE (0x03), we need to return an ExceptionResponse directly. This requires checking pymodbus request handler behavior more carefully -- the `update_datastore` method catches the exception. The current approach (raise Exception) maps to 0x04, not 0x03. For 0x03, we may need to override `validate()` to reject invalid values before `setValues` is called, or find another mechanism.

**Resolution:** Since `update_datastore` returns `ExceptionResponse(fc, ExceptionResponse.ILLEGAL_VALUE)` when `context.validate()` returns False, we can override `validate()` to reject writes with invalid values. Alternatively, accept that 0x04 is close enough (Venus OS handles both error codes gracefully). Recommend: override `validate()` for address range checking and use exception raising in `setValues` for value validation (0x04 is acceptable).

### Pattern 3: Exponential Backoff Reconnection
**What:** State machine in the poll loop that handles connection loss with exponential backoff.
**When to use:** When SE30K connection drops (poll failures, connection reset).
**Example:**
```python
class ConnectionManager:
    INITIAL_BACKOFF = 5.0
    MAX_BACKOFF = 60.0
    NIGHT_MODE_THRESHOLD = 300.0  # 5 minutes

    def __init__(self):
        self._backoff = self.INITIAL_BACKOFF
        self._first_failure_time: float | None = None
        self._state = ConnectionState.CONNECTED  # CONNECTED, RECONNECTING, NIGHT_MODE

    def on_poll_success(self):
        self._backoff = self.INITIAL_BACKOFF
        self._first_failure_time = None
        if self._state != ConnectionState.CONNECTED:
            self._state = ConnectionState.CONNECTED
            # Log state change, restore power limit

    def on_poll_failure(self):
        now = time.monotonic()
        if self._first_failure_time is None:
            self._first_failure_time = now

        elapsed = now - self._first_failure_time
        if elapsed > self.NIGHT_MODE_THRESHOLD and self._state != ConnectionState.NIGHT_MODE:
            self._state = ConnectionState.NIGHT_MODE
            # Log transition to night mode
        elif self._state == ConnectionState.CONNECTED:
            self._state = ConnectionState.RECONNECTING

        self._backoff = min(self._backoff * 2, self.MAX_BACKOFF)

    @property
    def sleep_duration(self) -> float:
        if self._state == ConnectionState.CONNECTED:
            return POLL_INTERVAL  # Normal 1s polling
        return self._backoff
```

### Pattern 4: Night Mode Synthetic Registers
**What:** When in night mode, serve synthetic zero-power registers instead of returning staleness errors.
**When to use:** After >5 minutes of connection failure, serve zero-power data with SLEEPING status.
**Example:**
```python
def build_night_mode_registers(last_energy_wh: int) -> tuple[list[int], list[int]]:
    """Build synthetic registers for night mode.

    Returns (common_registers, inverter_registers) with:
    - AC power = 0, DC power = 0
    - Energy = last known value (preserved)
    - Status = SLEEPING (2)
    - All currents/voltages = 0
    """
    # Keep Model 103 structure but zero out power/current
    inverter = [0] * 52
    inverter[0] = 103   # DID
    inverter[1] = 50    # Length
    # ... zero fill power registers ...
    # Preserve energy: inverter[24:26] = last_energy_wh as acc32
    inverter[38] = 2    # I_Status = SLEEPING
    return inverter
```

### Pattern 5: Signal Handling for Graceful Shutdown
**What:** Catch SIGTERM, reset power limit to 100%, close connections, exit 0.
**When to use:** systemd sends SIGTERM on `systemctl stop`.
**Example:**
```python
import signal

async def run_proxy_with_shutdown(plugin, config):
    shutdown_event = asyncio.Event()

    def handle_signal(sig, frame):
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        await asyncio.gather(
            server_task,
            poll_loop_task,
            shutdown_watcher(shutdown_event),
        )
    finally:
        # Reset power limit before closing
        await plugin.write_power_limit(100.0)
        await plugin.close()
```

### Anti-Patterns to Avoid
- **Synchronous blocking in async context:** Never use `time.sleep()` in the async poll loop; always use `await asyncio.sleep()`.
- **Reconnecting inside poll():** Don't put reconnection logic inside the plugin's `poll()` method. Keep it in the connection manager so state is centralized.
- **Storing control state in the datablock only:** Keep a separate `ControlState` object -- the datablock is uint16 arrays and hard to query. The ControlState provides typed access to WMaxLimPct, WMaxLim_Ena, etc.
- **Writing to SE30K non-volatile registers on every poll:** Registers like 0xF300 (enable) and 0xF310 (timeout) are stored in non-volatile memory. Only write when the value changes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON logging | Custom json.dumps formatter | structlog JSONRenderer | Handles edge cases (datetime, bytes, exceptions), processor pipeline for context |
| YAML parsing | Custom config parser | PyYAML yaml.safe_load | Proven, handles all YAML edge cases |
| Float32 encoding | Manual bit manipulation | struct.pack(">f", value) | IEEE 754 compliance guaranteed by Python stdlib |
| Modbus exception responses | Custom TCP frame building | Raise exception in setValues (pymodbus handles response framing) | pymodbus already maps exceptions to proper Modbus error frames |
| systemd integration | Custom daemonization | systemd unit file with Type=exec | systemd handles PID tracking, logging, restarts |

**Key insight:** pymodbus already handles the entire Modbus protocol framing for both reads and writes. The proxy only needs to intercept at the datastore level (setValues/getValues) and let pymodbus handle TCP framing, function codes, and exception responses.

## Common Pitfalls

### Pitfall 1: Float32 Byte Order for SolarEdge
**What goes wrong:** Writing Float32 values to SE30K with wrong byte order causes silent failures or incorrect power limiting.
**Why it happens:** SolarEdge uses big-endian IEEE 754 Float32 across 2 Modbus registers. Some implementations accidentally use little-endian or swap register order.
**How to avoid:** Always use `struct.pack(">f", value)` then `struct.unpack(">HH", ...)` to get the two uint16 registers. The ">" prefix ensures big-endian (network byte order).
**Warning signs:** Power limit commands appear to succeed but inverter does not change output.

### Pitfall 2: Modbus Address Off-by-One
**What goes wrong:** Writes target wrong registers because of pymodbus internal address adjustment.
**Why it happens:** pymodbus `ModbusSlaveContext.setValues()` adds +1 to the address before passing to the datablock. The Modbus protocol uses 0-based addressing but SunSpec documentation uses 40001-based addressing.
**How to avoid:** Trace through a test write to confirm exact address mapping. The `DATABLOCK_START` constant (40001) and the +1 offset in `setValues` must be accounted for. Write integration tests that verify register addresses end-to-end.
**Warning signs:** Writes to WMaxLimPct (40154) end up modifying adjacent registers.

### Pitfall 3: Reconnection During Active Control
**What goes wrong:** After reconnect, inverter runs at 100% because power limit was not restored.
**Why it happens:** SolarEdge power control registers are volatile -- they reset on connection loss or after Command Timeout expires.
**How to avoid:** On successful reconnect, restore last-known WMaxLimPct and WMaxLim_Ena values to SE30K. Keep `ControlState` persistent across reconnections.
**Warning signs:** Inverter briefly produces full power after any network hiccup.

### Pitfall 4: Night Mode vs Staleness Interaction
**What goes wrong:** Night mode and staleness both trigger on connection loss, causing conflicting behavior.
**Why it happens:** Phase 2 staleness (30s timeout) kicks in before night mode (5 min threshold). Need clear state transitions.
**How to avoid:** Define clear state machine: CONNECTED -> STALE (30s, return Modbus errors) -> NIGHT_MODE (5min, serve synthetic zeros). Night mode overrides staleness -- when in night mode, `is_stale` should return False so synthetic registers are served instead of errors.
**Warning signs:** Venus OS alternates between seeing errors and seeing zero-power data during nighttime.

### Pitfall 5: SIGTERM Race with SE30K Write
**What goes wrong:** Proxy shuts down before successfully resetting power limit to 100%.
**Why it happens:** SIGTERM handler sets shutdown flag, but the async write to SE30K (reset to 100%) may fail if connection is already lost.
**How to avoid:** Set a timeout on the shutdown write (e.g., 5 seconds). If write fails, log a warning but still exit cleanly. The SE30K's Command Timeout will eventually reset to fallback power limit.
**Warning signs:** After proxy restart, inverter stays throttled until Command Timeout expires.

### Pitfall 6: WMaxLimPct Scale Factor
**What goes wrong:** Venus OS writes WMaxLimPct with scale factor -2 (e.g., 5000 = 50.00%), but proxy forwards raw integer to SE30K which expects Float32 percentage.
**Why it happens:** SunSpec integer+SF encoding vs SolarEdge Float32 encoding mismatch.
**How to avoid:** Always apply scale factor conversion: `float_pct = raw_value * 10**scale_factor`. The WMaxLimPct_SF register in Model 123 should be set to -2 (standard). Convert: `5000 * 10^(-2) = 50.0` -> write Float32(50.0) to 0xF322.
**Warning signs:** Inverter limits to wrong percentage (e.g., 5000% or 0.5% instead of 50%).

## Code Examples

### Write Translation: WMaxLimPct to SE30K Float32
```python
# Source: docs/register-mapping-spec.md Write Translation Table
import struct

def wmaxlimpct_to_se_registers(raw_value: int, scale_factor: int = -2) -> tuple[int, int]:
    """Convert SunSpec WMaxLimPct to SolarEdge Float32 register pair.

    Args:
        raw_value: SunSpec integer value (e.g., 5000 for 50.00%)
        scale_factor: WMaxLimPct_SF value (default -2)

    Returns:
        Tuple of (high_register, low_register) for writing to 0xF322-0xF323
    """
    float_pct = raw_value * (10 ** scale_factor)
    packed = struct.pack(">f", float_pct)
    return struct.unpack(">HH", packed)

# Example: 50% power limit
hi, lo = wmaxlimpct_to_se_registers(5000, -2)
# hi=0x4248, lo=0x0000 -> write to SE registers 0xF322, 0xF323
```

### Validation: Reject Invalid Control Values
```python
# Source: CONTEXT.md locked decision
def validate_wmaxlimpct(raw_value: int, scale_factor: int = -2) -> str | None:
    """Validate WMaxLimPct value before forwarding to inverter.

    Returns None if valid, error message string if invalid.
    """
    import math
    float_pct = raw_value * (10 ** scale_factor)

    if math.isnan(float_pct) or math.isinf(float_pct):
        return f"Invalid value: {float_pct} (NaN/Inf not allowed)"
    if float_pct < 0:
        return f"Invalid value: {float_pct}% (negative not allowed)"
    if float_pct > 100:
        return f"Invalid value: {float_pct}% (exceeds 100%)"

    return None  # Valid
```

### structlog Configuration
```python
# Source: structlog 25.x documentation
import structlog
import logging
import sys

def configure_logging(level: str = "INFO"):
    """Configure structlog for JSON output to stdout."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

# Usage:
log = structlog.get_logger(component="control")
log.info("power_limit_set", value_pct=50.0, raw=5000, target="SE30K")
# Output: {"timestamp":"2026-03-18T10:00:00Z","level":"info","component":"control","event":"power_limit_set","value_pct":50.0,"raw":5000,"target":"SE30K"}
```

### YAML Config Schema
```python
# Source: project CONTEXT.md decisions
from dataclasses import dataclass, field
import yaml

@dataclass
class InverterConfig:
    host: str = "192.168.3.18"
    port: int = 1502
    unit_id: int = 1

@dataclass
class ProxyConfig:
    host: str = "0.0.0.0"
    port: int = 502
    poll_interval: float = 1.0
    staleness_timeout: float = 30.0

@dataclass
class NightModeConfig:
    threshold_seconds: float = 300.0  # 5 minutes

@dataclass
class Config:
    inverter: InverterConfig = field(default_factory=InverterConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    night_mode: NightModeConfig = field(default_factory=NightModeConfig)
    log_level: str = "INFO"

def load_config(path: str = "/etc/venus-os-fronius-proxy/config.yaml") -> Config:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    # Build config from nested dicts with defaults
    return Config(
        inverter=InverterConfig(**data.get("inverter", {})),
        proxy=ProxyConfig(**data.get("proxy", {})),
        night_mode=NightModeConfig(**data.get("night_mode", {})),
        log_level=data.get("log_level", "INFO"),
    )
```

### systemd Unit File
```ini
# /etc/systemd/system/venus-os-fronius-proxy.service
[Unit]
Description=Venus OS Fronius Proxy (SolarEdge to Fronius SunSpec translation)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/usr/bin/python3 -m venus_os_fronius_proxy
Restart=on-failure
RestartSec=5
User=fronius-proxy
Group=fronius-proxy
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=strict
ReadOnlyPaths=/etc/venus-os-fronius-proxy
StandardOutput=journal
StandardError=journal
SyslogIdentifier=venus-os-fronius-proxy

[Install]
WantedBy=multi-user.target
```

### Concurrent Write Handling (Recommendation: Last-Write-Wins)
```python
# Recommendation for Claude's discretion item
# Since asyncio is single-threaded, there is no true concurrency.
# Venus OS sends one write at a time (Modbus TCP is request-response).
# Last-write-wins is the natural behavior and correct approach.
# No queue needed -- each write is processed sequentially by asyncio.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pymodbus execute() method | pymodbus update_datastore() | pymodbus 3.7+ | Write requests use async update_datastore, not sync execute |
| stdlib logging + json.dumps | structlog JSONRenderer | structlog 21+ | Cleaner structured logging with processor pipeline |
| daemon scripts + init.d | systemd Type=exec | systemd 240+ (Debian 10+) | No daemonization needed, journald captures stdout |

**Deprecated/outdated:**
- pymodbus `execute()` method on request classes: replaced by `update_datastore()` in pymodbus 3.7+
- pymodbus `ModbusSlaveContext.setValues()` direct datablock access in newer pymodbus 4.x: replaced by `async_setValues/getValues` -- but 3.8.6 still supports both

## Open Questions

1. **ExceptionResponse for ILLEGAL_VALUE (0x03) vs SLAVE_FAILURE (0x04)**
   - What we know: Raising an exception in `setValues`/`async_setValues` causes pymodbus to return 0x04 (SLAVE_FAILURE). The CONTEXT.md specifies 0x03 (ILLEGAL_DATA_VALUE) for validation failures.
   - What's unclear: Whether we can return a proper 0x03 from the datastore level without modifying pymodbus internals. The `validate()` method returns bool (True/False) and triggers 0x02 (ILLEGAL_ADDRESS), not 0x03.
   - Recommendation: Use 0x04 (SLAVE_FAILURE) for validation rejections. Venus OS/dbus-fronius treats both 0x03 and 0x04 as write failures and retries. The behavioral difference is negligible. If 0x03 is strictly required, a custom request handler wrapper would be needed, which adds complexity.

2. **SE30K Command Timeout refresh strategy**
   - What we know: 0xF322 must be refreshed every `Command Timeout / 2` seconds. The default Command Timeout is unknown.
   - What's unclear: What the SE30K's default Command Timeout is. If it is very short, the proxy needs a dedicated refresh timer.
   - Recommendation: Set Command Timeout to 60s via 0xF310 on first enable. Refresh 0xF322 every 20s (60/3 for safety margin) as part of the poll loop. This is a non-volatile register, so only write once.

3. **pymodbus server active connection count**
   - What we know: Health heartbeat should include active connection count.
   - What's unclear: How to get the number of active TCP connections from pymodbus ModbusTcpServer.
   - Recommendation: Check `server.transport` or `server.active_connections` attributes at runtime. If not available, skip this metric initially.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTRL-01 | Venus OS writes WMaxLimPct via Model 123 and proxy accepts it | integration | `python -m pytest tests/test_control.py::test_write_wmaxlimpct -x` | Wave 0 |
| CTRL-02 | WMaxLimPct forwarded to SE30K as Float32 at 0xF322 | unit | `python -m pytest tests/test_control.py::test_wmaxlimpct_translation -x` | Wave 0 |
| CTRL-03 | Invalid values rejected with Modbus exception | unit | `python -m pytest tests/test_control.py::test_validation_rejects_invalid -x` | Wave 0 |
| DEPL-01 | systemd service file is valid | manual-only | Validate with `systemd-analyze verify` on target | N/A |
| DEPL-02 | Auto-reconnect with exponential backoff | unit | `python -m pytest tests/test_connection.py::test_exponential_backoff -x` | Wave 0 |
| DEPL-03 | Night mode serves synthetic registers after 5min failure | unit | `python -m pytest tests/test_connection.py::test_night_mode -x` | Wave 0 |
| DEPL-04 | JSON structured logging output | unit | `python -m pytest tests/test_logging.py::test_json_output -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_control.py` -- covers CTRL-01, CTRL-02, CTRL-03 (write interception, translation, validation)
- [ ] `tests/test_connection.py` -- covers DEPL-02, DEPL-03 (reconnection, night mode)
- [ ] `tests/test_logging.py` -- covers DEPL-04 (structured JSON output)
- [ ] `tests/test_config.py` -- covers config loading from YAML
- [ ] structlog dependency: `pip install "structlog>=25.0,<26.0"`

## Sources

### Primary (HIGH confidence)
- pymodbus 3.8.6 source code (installed) -- inspected `ModbusSlaveContext.setValues()`, `async_setValues()`, `WriteSingleRegisterRequest.update_datastore()`, `ExceptionResponse` constants
- Phase 2 codebase -- `proxy.py`, `plugin.py`, `register_cache.py`, `solaredge.py` (direct inspection)
- `docs/register-mapping-spec.md` -- Model 123 Write Translation Table, SE proprietary register addresses and encoding
- `docs/dbus-fronius-expectations.md` -- Venus OS write expectations for Model 123
- `docs/se30k-validation-results.md` -- Confirmed Model 123 absent, proprietary registers needed

### Secondary (MEDIUM confidence)
- [structlog 25.x documentation](https://www.structlog.org/en/stable/) -- JSONRenderer, processor pipeline, stdlib integration
- [pymodbus datastore docs](https://pymodbus.readthedocs.io/en/v3.8.3/source/library/datastore.html) -- Custom datablock patterns
- [pymodbus server callback discussion](https://github.com/pymodbus-dev/pymodbus/discussions/2270) -- Server hooks and write interception approaches

### Tertiary (LOW confidence)
- SE30K Command Timeout default value -- not verified from official SolarEdge documentation, assumed configurable via 0xF310

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pymodbus already in use, structlog/PyYAML are mature and well-documented
- Architecture: HIGH -- write interception pattern verified via pymodbus source code inspection
- Pitfalls: HIGH -- derived from register mapping spec and pymodbus internals analysis
- Control path translation: HIGH -- register addresses and Float32 encoding documented in spec and validated against live SE30K
- Night mode: MEDIUM -- state machine logic is straightforward but interaction with staleness needs careful testing
- systemd service: MEDIUM -- standard patterns, but CAP_NET_BIND_SERVICE and user creation are deployment-specific

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (30 days -- stable stack, no major version changes expected)
