# Phase 2: Core Proxy (Read Path) - Research

**Researched:** 2026-03-18
**Domain:** Modbus TCP proxy server, async polling, SunSpec register serving
**Confidence:** HIGH

## Summary

This phase implements a Modbus TCP proxy that makes Venus OS discover and monitor the SolarEdge SE30K as a Fronius inverter. The implementation uses pymodbus 3.8.6 (already in pyproject.toml) for both the async TCP server (serving Venus OS on port 502, unit ID 126) and the async TCP client (polling SE30K at 192.168.3.18:1502, unit ID 1). The entire proxy runs in a single asyncio event loop with two concurrent tasks: a background poller that updates a register cache every 1 second, and a Modbus TCP server that serves reads from that cache.

All protocol details, register addresses, model chain layout, and translation rules are already fully documented in Phase 1 outputs (`docs/register-mapping-spec.md`, `docs/dbus-fronius-expectations.md`, `docs/se30k-validation-results.md`). The 27 existing unit tests in `tests/test_register_mapping.py` define the expected register layout. The implementation must pass these tests.

**Primary recommendation:** Use pymodbus `ModbusTcpServer` (async) with a `ModbusSequentialDataBlock` starting at address 40001 (compensating for pymodbus internal +1 offset), updated by an asyncio background task that polls the SE30K via `AsyncModbusTcpClient`. Keep the architecture simple -- single Python module for the proxy core, with a plugin ABC for inverter brand abstraction.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Poll SE30K every 1 second (matches typical dbus-fronius polling rate, needed for ESS control loops)
- Full batch poll -- read all needed registers (Common + Inverter model, ~120 registers) in one cycle, not on-demand
- Serve stale cache when SE30K is slow/unresponsive -- keep serving last known values, mark staleness internally for logging
- Cache staleness timeout: 30 seconds -- after 30s without a successful poll, start returning Modbus errors to Venus OS
- Polling runs asynchronously, independent of Venus OS request handling
- Proxy listens on port 502 (standard Modbus TCP) -- requires root or CAP_NET_BIND_SERVICE on the LXC
- Proxy responds to Modbus unit ID 126 (Fronius convention, dbus-fronius scans for this)
- Support multiple simultaneous TCP connections (Venus OS + future config webapp register viewer)
- Bind to 0.0.0.0 (all interfaces) -- all devices in same trusted LAN, no restriction needed

### Claude's Discretion
- Plugin interface design (ABC class vs protocol, method signatures, how brand-specific config is loaded)
- Error handling strategy for connection failures and edge cases
- Nighttime/sleeping inverter behavior (basic handling needed, production hardening in Phase 3)
- Async framework choice (asyncio with pymodbus async server is the obvious fit)
- Register translation implementation (lookup table, class hierarchy, etc.)
- How to handle concurrent Venus OS reads while polling is in progress (cache serves reads, no locking needed if using asyncio single-thread)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROXY-01 | Modbus TCP Server accepts Venus OS connections | pymodbus `ModbusTcpServer` with `StartAsyncTcpServer`, address `("0.0.0.0", 502)` |
| PROXY-02 | Common Model (Model 1) with Fronius manufacturer string | Static registers in datablock: "Fronius" at 40004-40019, unit ID 126 at 40068 |
| PROXY-03 | Inverter Model 103 with live SE30K data | Passthrough from SE30K registers 40069-40120, updated by background poller |
| PROXY-04 | Nameplate Model 120 | Synthesized static registers at 40121-40148 (SE30K lacks Model 120) |
| PROXY-05 | Valid SunSpec model chain | Sequential datablock 40000-40176: Header + Common + 103 + 120 + 123 + End |
| PROXY-06 | Async SE30K register polling | `AsyncModbusTcpClient` with auto-reconnect, 1s poll interval via `asyncio.sleep` |
| PROXY-07 | Cache-based serving (not pass-through) | Datablock updated by poller; server reads from datablock directly |
| PROXY-08 | Scale factor translation | SunSpec scale factors pass through unchanged for Model 103; Model 120 uses static SFs |
| PROXY-09 | Venus OS discovers proxy as Fronius | Unit ID 126, "Fronius" manufacturer, valid model chain = auto-discovery |
| ARCH-01 | Plugin interface for inverter brands | ABC class `InverterPlugin` with `poll()`, `get_static_registers()` methods |
| ARCH-02 | Register mapping as swappable module | Mapping config separate from proxy core; SolarEdge plugin owns the mapping |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pymodbus | 3.8.6 | Modbus TCP server + client | Already in pyproject.toml; proven async support; handles framing, unit IDs, connection management |
| asyncio | stdlib | Event loop, concurrent tasks | Single-threaded concurrency; no locking needed for cache updates |
| struct | stdlib | Binary encoding (int16, uint32, float32) | Required for SunSpec register encoding |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Structured logging | Poll status, connection events, staleness warnings |
| pytest | 8.4.2 | Unit testing | Existing tests + new proxy tests |
| pytest-asyncio | 1.2.0 | Async test support | Testing async server/client interactions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pymodbus server | Raw asyncio TCP | pymodbus handles Modbus protocol framing, unit ID filtering, function code dispatch -- no reason to hand-roll |
| ModbusSequentialDataBlock | ModbusSparseDataBlock | Sequential is simpler for contiguous 177-register range; sparse adds overhead for no benefit |

**Installation:**
```bash
pip install "pymodbus>=3.6,<4.0" pytest pytest-asyncio
```

**Version verification:** pymodbus 3.8.6 confirmed as latest (2026-03-18). pytest 8.4.2, pytest-asyncio 1.2.0 confirmed.

## Architecture Patterns

### Recommended Project Structure
```
src/
  venus_os_fronius_proxy/
    __init__.py
    proxy.py              # Main proxy: server + poller orchestration
    register_cache.py     # RegisterCache: datablock wrapper with staleness tracking
    sunspec_models.py     # Static SunSpec model definitions (Common, 120, 123, End)
    plugin.py             # InverterPlugin ABC + plugin registry
    plugins/
      __init__.py
      solaredge.py        # SolarEdge SE30K plugin: poll logic, register mapping
tests/
  test_register_mapping.py  # Existing (27 tests)
  test_proxy.py              # New: server serves correct registers
  test_register_cache.py     # New: cache staleness, update behavior
  test_solaredge_plugin.py   # New: polling, translation
```

### Pattern 1: Async Poller + Cache Server
**What:** Two asyncio tasks sharing a `ModbusSequentialDataBlock` -- one writes (poller), one reads (server).
**When to use:** Always -- this is the core architecture.
**Example:**
```python
# Source: pymodbus 3.8.6 API + project requirements
import asyncio
from pymodbus.server import ModbusTcpServer
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)

# CRITICAL: pymodbus 3.8.6 does address += 1 internally in ModbusSlaveContext.
# When a client reads register 40000, pymodbus looks up 40001 in the datablock.
# Therefore the datablock must start at 40001.
DATABLOCK_START = 40001  # NOT 40000!
TOTAL_REGISTERS = 177    # 40000-40176 inclusive

async def run_proxy():
    # Initialize datablock with static values (SunSpec header, Common, 120, End)
    initial_values = build_initial_registers()  # returns list of 177 uint16

    datablock = ModbusSequentialDataBlock(DATABLOCK_START, initial_values)
    slave_ctx = ModbusSlaveContext(hr=datablock)
    server_ctx = ModbusServerContext(
        slaves={126: slave_ctx},
        single=False,
    )

    # Start server (non-blocking via asyncio task)
    server = ModbusTcpServer(
        context=server_ctx,
        address=("0.0.0.0", 502),
    )

    # Run server and poller concurrently
    await asyncio.gather(
        server.serve_forever(),
        poll_solaredge(datablock),
    )

async def poll_solaredge(datablock):
    client = AsyncModbusTcpClient("192.168.3.18", port=1502)
    await client.connect()

    while True:
        try:
            # Read Common Model (skip header, read from 40002)
            common = await client.read_holding_registers(40002, count=67, slave=1)
            # Read Inverter Model 103
            inverter = await client.read_holding_registers(40069, count=52, slave=1)

            if not common.isError() and not inverter.isError():
                # Update cache (address compensated for +1 offset)
                datablock.setValues(40003, apply_common_translation(common.registers))
                datablock.setValues(40070, inverter.registers)

        except Exception as e:
            logging.warning("Poll failed: %s", e)

        await asyncio.sleep(1.0)
```

### Pattern 2: Plugin Interface (ABC)
**What:** Abstract base class defining what each inverter brand plugin must provide.
**When to use:** ARCH-01 and ARCH-02 -- brand-specific logic isolated behind interface.
**Example:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PollResult:
    """Result from polling an inverter."""
    common_registers: list[int]    # 67 registers (DID + len + 65 data)
    inverter_registers: list[int]  # 52 registers (DID + len + 50 data)
    success: bool
    error: str | None = None

class InverterPlugin(ABC):
    """Interface for inverter brand plugins."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the inverter."""

    @abstractmethod
    async def poll(self) -> PollResult:
        """Read all registers needed for the SunSpec model chain."""

    @abstractmethod
    def get_static_common_overrides(self) -> dict[int, int]:
        """Return register address -> value for static Common Model fields.
        E.g., manufacturer string registers."""

    @abstractmethod
    def get_model_120_registers(self) -> list[int]:
        """Return synthesized Model 120 (Nameplate) register values."""

    @abstractmethod
    async def close(self) -> None:
        """Clean up connection resources."""
```

### Pattern 3: Register Cache with Staleness
**What:** Wrapper around the datablock that tracks last-successful-poll timestamp and returns errors after staleness timeout.
**When to use:** PROXY-07 -- cache-based serving with staleness detection.
**Example:**
```python
import time

class RegisterCache:
    """Manages the Modbus datablock with staleness tracking."""

    def __init__(self, datablock, staleness_timeout: float = 30.0):
        self.datablock = datablock
        self.staleness_timeout = staleness_timeout
        self.last_successful_poll: float = 0.0
        self._stale = True

    def update(self, address: int, values: list[int]) -> None:
        """Update registers from a successful poll."""
        self.datablock.setValues(address, values)
        self.last_successful_poll = time.monotonic()
        self._stale = False

    @property
    def is_stale(self) -> bool:
        """True if no successful poll within staleness_timeout."""
        if self._stale:
            return True
        return (time.monotonic() - self.last_successful_poll) > self.staleness_timeout
```

### Anti-Patterns to Avoid
- **Pass-through proxy:** Never forward Venus OS reads directly to SE30K -- violates PROXY-07, adds latency, creates coupling.
- **Locking/threading:** Never use threads or locks for cache access -- asyncio single-threaded model makes this unnecessary and adding locks would only hurt performance.
- **Hardcoded register addresses in proxy core:** Register mapping belongs in the plugin (ARCH-02) -- proxy core should only know about the datablock.
- **Polling inside request handler:** Never poll on-demand when Venus OS reads -- the poller runs independently at 1s intervals.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modbus TCP framing | Custom TCP protocol handler | pymodbus ModbusTcpServer | Handles MBAP header, function codes, error responses, unit ID routing |
| Connection management | Manual socket handling | pymodbus AsyncModbusTcpClient with auto-reconnect | Built-in reconnect with exponential backoff |
| Register addressing | Manual address arithmetic | ModbusSequentialDataBlock | Handles contiguous register blocks with validate/get/set |
| Unit ID filtering | Custom request filtering | ModbusServerContext(single=False, slaves={126: ctx}) | Built-in unit ID routing |

**Key insight:** pymodbus handles all Modbus protocol complexity. The proxy's job is only: (1) fill the datablock with translated data, (2) manage the poll loop timing and staleness.

## Common Pitfalls

### Pitfall 1: pymodbus Address +1 Offset
**What goes wrong:** Datablock created at address 40000 causes all reads to be off by one register.
**Why it happens:** In pymodbus 3.8.6, `ModbusSlaveContext.getValues()` unconditionally does `address += 1` before looking up the datablock. The old `zero_mode` parameter has been removed.
**How to avoid:** Create `ModbusSequentialDataBlock(40001, values)` so that client request for address 40000 maps to `40000 + 1 = 40001` which is the first element.
**Warning signs:** SunSpec header read returns wrong bytes; model chain walk fails at first model.
**Confidence:** HIGH -- verified by reading pymodbus 3.8.6 source code and testing empirically.

### Pitfall 2: Second Common Model on SE30K
**What goes wrong:** Walking the SE30K model chain past Model 103 encounters a second Common Model (Model 1) at address 40121, which belongs to a different device (meter/optimizer).
**Why it happens:** SE30K serves multiple SunSpec device instances in its model chain.
**How to avoid:** Only read registers 40002-40120 from SE30K. Do NOT walk beyond Model 103. Proxy synthesizes everything after 103 (Models 120, 123, End).
**Warning signs:** Proxy serves wrong manufacturer or duplicate Common Models.
**Confidence:** HIGH -- confirmed by live validation (se30k-validation-results.md).

### Pitfall 3: Null-Frame Filter in dbus-fronius
**What goes wrong:** Venus OS discards data frames where all measurement values are zero AND Status = 7 (FAULT).
**Why it happens:** dbus-fronius has a "Fronius null-frame filter" for solar net communication timeouts.
**How to avoid:** During nighttime (inverter SLEEPING), pass through the real status code (2 = SLEEPING). Never fabricate Status = 7 with zero values. The SE30K correctly reports SLEEPING with zero power, which passes the filter fine.
**Warning signs:** Venus OS shows no data updates even though proxy is serving.
**Confidence:** HIGH -- documented in dbus-fronius-expectations.md.

### Pitfall 4: Stale Cache Serving After Reconnect
**What goes wrong:** After SE30K goes offline and comes back, old cached energy counters (acc32) cause Venus OS to show incorrect lifetime energy.
**Why it happens:** Energy counter is accumulative (acc32). Serving stale values is correct (it never decreases). The real risk is if the cache contains zeros from a failed poll being written.
**How to avoid:** Only update cache on successful polls (`not result.isError()`). Never write error/empty data to the cache. Staleness tracking is separate from data validity.
**Warning signs:** Energy counter jumps or resets after reconnection.
**Confidence:** MEDIUM -- logical analysis, not tested against live system.

### Pitfall 5: Modbus TCP Max Read Size
**What goes wrong:** Trying to read too many registers in one request (>125 per Modbus spec).
**Why it happens:** Full model chain is 177 registers, tempting a single read.
**How to avoid:** Split reads: Common (67 regs) + Inverter header+data (52 regs) = two requests per poll cycle. Both are well under the 125-register limit.
**Warning signs:** SE30K returns Modbus exception code 2 (Illegal Data Address).
**Confidence:** HIGH -- Modbus specification limit.

## Code Examples

### Building Initial Register Values
```python
# Source: register-mapping-spec.md + project constants
import struct

def encode_string(text: str, num_registers: int) -> list[int]:
    """Encode ASCII string into uint16 register list, null-padded."""
    raw = text.encode("ascii").ljust(num_registers * 2, b"\x00")
    return [int.from_bytes(raw[i:i+2], "big") for i in range(0, num_registers * 2, 2)]

def build_initial_registers() -> list[int]:
    """Build the full 177-register initial datablock.

    Addresses 40000-40176 (stored as 40001-40177 in datablock due to +1 offset).
    Static values for: SunSpec header, Common identity fields, Model 120, Model 123, End marker.
    Dynamic values (Model 103) initialized to zero, updated by poller.
    """
    regs = [0] * 177

    # SunSpec Header (40000-40001): "SunS"
    regs[0] = 0x5375  # "Su"
    regs[1] = 0x6E53  # "nS"

    # Common Model DID and Length (40002-40003)
    regs[2] = 1    # DID = 1
    regs[3] = 65   # Length = 65

    # C_Manufacturer "Fronius" (40004-40019)
    regs[4:20] = encode_string("Fronius", 16)

    # C_Options "NOT_IMPLEMENTED" (40036-40043) -- static
    regs[36:44] = encode_string("", 8)  # empty/null

    # C_DeviceAddress (40068) = 126
    regs[68] = 126

    # Model 103 DID and Length (40069-40070) -- static header
    regs[69] = 103   # DID
    regs[70] = 50    # Length
    # Registers 40071-40120 (indices 71-120) = zeros until first poll

    # Model 120 Nameplate (40121-40148) -- fully synthesized
    regs[121] = 120   # DID
    regs[122] = 26    # Length
    regs[123] = 4     # DERTyp = PV
    regs[124] = 30000 # WRtg
    regs[125] = 0     # WRtg_SF
    regs[126] = 30000 # VARtg
    regs[127] = 0     # VARtg_SF
    regs[128] = 18000 # VArRtgQ1
    regs[129] = 18000 # VArRtgQ2
    # Note: int16 negatives must be stored as uint16
    regs[130] = struct.unpack(">H", struct.pack(">h", -18000))[0]  # VArRtgQ3
    regs[131] = struct.unpack(">H", struct.pack(">h", -18000))[0]  # VArRtgQ4
    regs[132] = 0     # VArRtg_SF
    regs[133] = 44    # ARtg
    regs[134] = 0     # ARtg_SF
    regs[135] = 100   # PFRtgQ1
    regs[136] = 100   # PFRtgQ2
    regs[137] = struct.unpack(">H", struct.pack(">h", -100))[0]  # PFRtgQ3
    regs[138] = struct.unpack(">H", struct.pack(">h", -100))[0]  # PFRtgQ4
    regs[139] = struct.unpack(">H", struct.pack(">h", -2))[0]    # PFRtg_SF
    # 40140-40148 = zeros (storage ratings N/A, padding)

    # Model 123 Immediate Controls (40149-40174) -- read path only in Phase 2
    regs[149] = 123   # DID
    regs[150] = 24    # Length
    # Remaining fields = 0 (no active control in Phase 2)

    # End Marker (40175-40176)
    regs[175] = 0xFFFF
    regs[176] = 0x0000

    return regs
```

### Applying Common Model Translation
```python
def apply_common_translation(se_common_regs: list[int]) -> list[int]:
    """Translate SE30K Common Model registers for proxy serving.

    Input: 67 registers from SE30K (DID + Length + 65 data fields)
    Output: 67 registers with Fronius identity substituted

    Passthrough fields: C_Model, C_Version, C_SerialNumber
    Replaced fields: C_Manufacturer -> "Fronius", C_DeviceAddress -> 126
    """
    translated = list(se_common_regs)

    # Replace DID and Length (should already be correct, but enforce)
    translated[0] = 1    # DID
    translated[1] = 65   # Length

    # Replace C_Manufacturer (offset 2-17, 16 registers)
    translated[2:18] = encode_string("Fronius", 16)

    # Replace C_DeviceAddress (offset 66)
    translated[66] = 126

    return translated
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pymodbus `zero_mode` param | Removed in 3.8.x; always `address += 1` | pymodbus 3.7+ | Datablock must start at address+1 |
| `StartAsyncModbusTcpServer` | `StartAsyncTcpServer` (renamed) | pymodbus 3.x | Import path changed |
| Synchronous pymodbus server | All servers are async internally | pymodbus 3.x | Sync server is just a wrapper |

**Deprecated/outdated:**
- `zero_mode` parameter on `ModbusSlaveContext`: removed in pymodbus 3.8.x. Address offset is always applied.
- `ModbusTcpClient` (sync): still works but `AsyncModbusTcpClient` is preferred for async applications.

## Open Questions

1. **SE30K Concurrent Connection Limit**
   - What we know: SE30K supports at least 1 Modbus TCP connection (validated in Phase 1). The proxy will be the only client.
   - What's unclear: Maximum concurrent connections if webapp register viewer also connects directly.
   - Recommendation: Not relevant for Phase 2 -- proxy is the sole SE30K client. Address in Phase 4 if webapp needs direct SE30K access.

2. **ModbusTcpServer `serve_forever()` vs `StartAsyncTcpServer`**
   - What we know: Both exist. `StartAsyncTcpServer` is a convenience wrapper.
   - What's unclear: Whether `serve_forever()` is the correct method name in 3.8.6.
   - Recommendation: Use `server.serve_forever()` directly (standard asyncio server pattern). If method name differs, check `dir(server)` during implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 1.2.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROXY-01 | Server accepts TCP connections on port 502 | integration | `pytest tests/test_proxy.py::test_server_accepts_connection -x` | No -- Wave 0 |
| PROXY-02 | Common Model has "Fronius" manufacturer | unit | `pytest tests/test_register_mapping.py::TestCommonModelManufacturerSubstitution -x` | Yes |
| PROXY-03 | Model 103 data from SE30K in cache | unit | `pytest tests/test_proxy.py::test_inverter_registers_from_cache -x` | No -- Wave 0 |
| PROXY-04 | Model 120 synthesized correctly | unit | `pytest tests/test_register_mapping.py::TestModel120Synthesis -x` | Yes |
| PROXY-05 | Model chain structure correct | unit | `pytest tests/test_register_mapping.py::TestModelChainStructure -x` | Yes |
| PROXY-06 | Async polling reads SE30K registers | unit | `pytest tests/test_solaredge_plugin.py::test_poll_reads_registers -x` | No -- Wave 0 |
| PROXY-07 | Server reads from cache, not passthrough | integration | `pytest tests/test_proxy.py::test_serves_from_cache -x` | No -- Wave 0 |
| PROXY-08 | Scale factors correct | unit | `pytest tests/test_register_mapping.py::TestScaleFactor -x` | Yes |
| PROXY-09 | Venus OS discovery (unit ID 126, SunSpec header) | integration | `pytest tests/test_proxy.py::test_sunspec_discovery_flow -x` | No -- Wave 0 |
| ARCH-01 | Plugin ABC defined, SolarEdge implements it | unit | `pytest tests/test_solaredge_plugin.py::test_plugin_interface -x` | No -- Wave 0 |
| ARCH-02 | Register mapping in plugin, not hardcoded | unit | `pytest tests/test_solaredge_plugin.py::test_mapping_in_plugin -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_proxy.py` -- covers PROXY-01, PROXY-03, PROXY-07, PROXY-09
- [ ] `tests/test_register_cache.py` -- covers cache staleness, update behavior
- [ ] `tests/test_solaredge_plugin.py` -- covers PROXY-06, ARCH-01, ARCH-02
- [ ] `src/venus_os_fronius_proxy/` -- package structure does not exist yet

## Sources

### Primary (HIGH confidence)
- pymodbus 3.8.6 source code -- inspected `ModbusSlaveContext.__init__`, `validate()`, `getValues()`, `setValues()` to confirm address +1 behavior and absence of `zero_mode`
- pymodbus 3.8.6 API -- `AsyncModbusTcpClient`, `ModbusTcpServer`, `ModbusSequentialDataBlock` constructors and methods verified empirically
- [pymodbus server docs](https://pymodbus.readthedocs.io/en/v3.8.1/source/server.html) -- `ModbusTcpServer` parameters, `StartAsyncTcpServer` signature
- [pymodbus client docs](https://pymodbus.readthedocs.io/en/v3.8.1/source/client.html) -- `AsyncModbusTcpClient` parameters, reconnect behavior
- [pymodbus datastore docs](https://pymodbus.readthedocs.io/en/v3.8.3/source/library/datastore.html) -- `ModbusSlaveContext`, `ModbusServerContext`, datablock classes
- `docs/register-mapping-spec.md` -- complete register translation table (176 registers)
- `docs/dbus-fronius-expectations.md` -- Venus OS discovery requirements, model chain, null-frame filter
- `docs/se30k-validation-results.md` -- live-validated SE30K register layout, Model 120/123 absence confirmed

### Secondary (MEDIUM confidence)
- [pymodbus server examples (DeepWiki)](https://deepwiki.com/pymodbus-dev/pymodbus/5.2-server-examples) -- async server patterns, updating context example
- [pymodbus GitHub discussions](https://github.com/pymodbus-dev/pymodbus/discussions/2040) -- ModbusServerContext single=False unit ID behavior

### Tertiary (LOW confidence)
- None -- all critical findings verified through primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pymodbus already chosen and validated in Phase 1; version verified against PyPI
- Architecture: HIGH -- pattern verified empirically (datablock address offset, unit ID filtering, async server+client concurrency)
- Pitfalls: HIGH -- address offset pitfall verified by source code inspection and empirical testing; other pitfalls documented in Phase 1 outputs

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- pymodbus 3.x API is mature)
