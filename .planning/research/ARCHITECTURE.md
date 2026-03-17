# Architecture Patterns

**Domain:** Modbus TCP Proxy (SolarEdge to Fronius/SunSpec emulation for Venus OS)
**Researched:** 2026-03-17
**Overall confidence:** MEDIUM (based on training data; web verification was unavailable)

## Recommended Architecture

### High-Level Overview

```
                         LAN (192.168.3.0/24)

  Venus OS (GX)          Proxy (LXC)              SolarEdge SE30K
  192.168.3.146          192.168.3.191             192.168.3.18:1502
  ┌──────────┐          ┌──────────────────┐      ┌──────────────┐
  │          │  Modbus  │ Fronius SunSpec   │      │              │
  │dbus-     │  TCP     │ Emulator (Server) │      │ SolarEdge    │
  │fronius   │◄────────►│ Port 502          │      │ Modbus TCP   │
  │          │          │                    │      │ Server       │
  │          │          │   Register         │      │              │
  │          │          │   Translation      │      │              │
  │          │          │   Engine           │      │              │
  │          │          │                    │      │              │
  │          │          │ SolarEdge Plugin   │ Modbus│              │
  │          │          │ (Client)           │ TCP  │              │
  │          │          │                    │◄────►│              │
  │          │          ├────────────────────┤      │              │
  │          │          │ Config Webapp      │      │              │
  │          │          │ Port 8080          │      │              │
  └──────────┘          └──────────────────┘      └──────────────┘
                              ▲
                              │ HTTP
                              │
                         Browser (Admin)
```

### How Venus OS Discovers Fronius Inverters

Venus OS uses `dbus-fronius`, which discovers Fronius inverters via two mechanisms:

1. **mDNS/DNS-SD (primary):** Fronius inverters advertise `_http._tcp` or `_modbus._tcp` services via mDNS. Venus OS scans for these. **However**, many Venus OS setups also support manual IP configuration for Fronius Modbus TCP.

2. **Manual IP entry (our approach):** Venus OS allows adding PV inverters by IP address in the Remote Console under Settings > PV Inverters. When an IP is added, `dbus-fronius` connects via Modbus TCP (port 502 by default) and reads SunSpec register blocks to identify the device.

**MEDIUM confidence** -- based on Venus OS community knowledge and Victron documentation patterns. The exact discovery flow should be verified against `dbus-fronius` source code during implementation.

### What dbus-fronius Expects (SunSpec Compliance)

When `dbus-fronius` connects to a Modbus TCP endpoint, it expects a standard SunSpec-compliant device. The connection flow:

1. **SunSpec Header:** Read register 40000 (or 0 in some implementations) -- expects magic bytes `0x53756e53` ("SunS").
2. **Common Model (Model 1):** Immediately after header. Contains manufacturer name ("Fronius"), device model, serial number, SunSpec version. **Critical:** The manufacturer string likely needs to say "Fronius" for `dbus-fronius` to recognize it.
3. **Inverter Model (Model 101/102/103):** Single-phase (101), split-phase (102), or three-phase (103) inverter data. Contains AC power, voltage, current, frequency, energy counters, operating state.
4. **Nameplate Model (Model 120):** Rated power, voltage, current limits.
5. **Immediate Controls (Model 123):** Power limit control -- this is how Venus OS sends curtailment commands (WMaxLimPct, WMaxLim_Ena).
6. **End Marker:** Model ID 0xFFFF signals end of SunSpec model list.

**MEDIUM confidence** -- SunSpec models 1, 101/103, 120, 123 are standard. The exact set that `dbus-fronius` requires needs verification.

### Key Architectural Insight: This is NOT a Simple Pass-Through Proxy

A naive approach would be to forward Modbus requests. That will not work because:

- **Venus OS speaks "Fronius SunSpec"** (standard SunSpec register layout starting at 40000)
- **SolarEdge speaks "SolarEdge SunSpec"** (SunSpec-compatible but with proprietary extensions, different register offsets, and additional SolarEdge-specific registers)
- The register addresses, scaling factors, and data representations may differ

The proxy must maintain its own register map (Fronius-compatible) and actively poll the SolarEdge inverter to populate it. It is a **translation layer**, not a relay.

## Component Boundaries

| Component | Responsibility | Communicates With | Protocol |
|-----------|---------------|-------------------|----------|
| **SunSpec Server** | Serve Fronius-compatible SunSpec registers to Venus OS | Venus OS (inbound Modbus TCP) | Modbus TCP server on port 502 |
| **Register Store** | Hold current translated register values in memory | SunSpec Server reads; Translation Engine writes | Internal (shared memory/object) |
| **Translation Engine** | Map SolarEdge register values to Fronius SunSpec registers | Register Store, Inverter Plugin | Internal function calls |
| **Inverter Plugin (SolarEdge)** | Poll SolarEdge inverter, return raw register data; forward write commands | SolarEdge inverter (outbound Modbus TCP) | Modbus TCP client to 192.168.3.18:1502 |
| **Plugin Manager** | Load/manage inverter plugins, route to active plugin | Inverter Plugins, Config Store | Internal |
| **Config Store** | Persist configuration (inverter IP, port, plugin selection) | All components read; Webapp writes | File (JSON/YAML) |
| **Config Webapp** | Web UI for configuration and status monitoring | Config Store, Register Store (read-only), Plugin Manager | HTTP REST API |
| **Health Monitor** | Track connection status, error rates, last successful poll | Inverter Plugin, Webapp | Internal events |

## Data Flow

### Read Flow (Venus OS reads inverter data)

```
1. Venus OS (dbus-fronius) opens Modbus TCP connection to proxy:502
2. Venus OS sends ReadHoldingRegisters request (e.g., registers 40069-40084 for Model 103)
3. SunSpec Server receives request
4. SunSpec Server reads from Register Store (pre-populated, in-memory)
5. SunSpec Server returns Modbus response with register values
```

The Register Store is populated asynchronously:

```
A. Polling Loop (every 1-5 seconds):
   1. Translation Engine triggers Inverter Plugin to poll
   2. SolarEdge Plugin reads SolarEdge registers via Modbus TCP client
   3. Plugin returns raw SolarEdge data to Translation Engine
   4. Translation Engine maps values to Fronius SunSpec register layout
   5. Translation Engine updates Register Store
```

### Write Flow (Venus OS sends control commands)

```
1. Venus OS sends WriteMultipleRegisters to proxy:502 (e.g., Model 123 power limit)
2. SunSpec Server receives write request
3. SunSpec Server passes to Translation Engine
4. Translation Engine translates Fronius SunSpec register addresses to SolarEdge equivalents
5. Translation Engine calls Inverter Plugin write method
6. SolarEdge Plugin writes translated registers to SolarEdge inverter
7. Success/failure propagated back as Modbus response
```

### Why Async Polling (Not Pass-Through)

- **Latency:** Venus OS polls frequently. Chaining two Modbus TCP calls per request doubles latency and risks timeouts.
- **Register layout mismatch:** SolarEdge and Fronius SunSpec register addresses are different. A single Venus OS read spanning multiple registers may require multiple SolarEdge reads.
- **Resilience:** If SolarEdge is temporarily unreachable, the proxy can serve stale data with a warning rather than failing every Venus OS request.
- **Write coalescing:** Multiple rapid writes can be batched.

## Patterns to Follow

### Pattern 1: Plugin Interface for Inverter Brands

The inverter plugin defines a clear interface that any brand must implement:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class InverterData:
    """Normalized inverter data -- brand-agnostic."""
    ac_power_w: float          # Current AC power output
    ac_voltage_v: float        # AC voltage (phase avg or per-phase)
    ac_current_a: float        # AC current
    ac_frequency_hz: float     # Grid frequency
    dc_power_w: float          # DC input power
    dc_voltage_v: float        # DC voltage
    dc_current_a: float        # DC current
    energy_total_wh: float     # Lifetime energy production
    energy_today_wh: float     # Today's energy (if available)
    operating_state: int       # SunSpec operating state code
    error_code: int            # Vendor error code (0 = no error)
    temperature_c: Optional[float] = None
    rated_power_w: Optional[float] = None

class InverterPlugin(ABC):
    """Interface every inverter brand plugin must implement."""

    @abstractmethod
    async def connect(self, host: str, port: int, unit_id: int) -> bool:
        """Establish connection to physical inverter."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection."""
        ...

    @abstractmethod
    async def poll(self) -> InverterData:
        """Read current inverter state. Called every poll interval."""
        ...

    @abstractmethod
    async def set_power_limit(self, percent: float) -> bool:
        """Set active power limit as percentage of rated power."""
        ...

    @abstractmethod
    async def clear_power_limit(self) -> bool:
        """Remove active power limit (return to 100%)."""
        ...

    @abstractmethod
    def manufacturer(self) -> str:
        """Return manufacturer name for logging/UI."""
        ...

    @abstractmethod
    def model(self) -> str:
        """Return model identifier."""
        ...
```

**Why this interface:** It captures exactly what the translation engine needs. The plugin handles brand-specific Modbus register reading; the translation engine handles mapping to Fronius SunSpec. New brands only need to implement this interface.

### Pattern 2: Register Store as Single Source of Truth

```python
class RegisterStore:
    """Thread-safe SunSpec register map.

    Holds the complete Fronius-compatible SunSpec register image.
    Written by Translation Engine, read by SunSpec Server.
    """
    def __init__(self):
        self._registers: dict[int, int] = {}  # address -> 16-bit value
        self._lock = asyncio.Lock()
        self._last_update: float = 0

    async def bulk_update(self, updates: dict[int, int]) -> None:
        """Update multiple registers atomically."""
        async with self._lock:
            self._registers.update(updates)
            self._last_update = time.time()

    def read_registers(self, start: int, count: int) -> list[int]:
        """Read a contiguous range. No lock needed for reads (dict is thread-safe for reads)."""
        return [self._registers.get(start + i, 0) for i in range(count)]

    @property
    def age_seconds(self) -> float:
        return time.time() - self._last_update
```

### Pattern 3: SunSpec Model Builder

Rather than hardcoding register addresses, build the SunSpec model layout programmatically:

```python
SUNSPEC_BASE = 40000

# Model layout: (model_id, length, description)
MODELS = [
    # SunSpec header at 40000-40001 ("SunS" magic)
    (1, 66, "Common"),           # 40002-40069
    (103, 50, "Three Phase Inverter"),  # 40070-40121
    (120, 26, "Nameplate"),      # 40122-40149
    (123, 24, "Immediate Controls"),    # 40150-40175
    (0xFFFF, 0, "End Marker"),   # 40176
]
```

This makes the register layout explicit and easy to adjust if `dbus-fronius` expects a different model order.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Transparent Modbus Relay
**What:** Forward every Modbus request from Venus OS directly to SolarEdge.
**Why bad:** Register addresses differ between Fronius SunSpec and SolarEdge SunSpec. Venus OS will read garbage values. Power limit writes will target wrong registers.
**Instead:** Maintain a translated register store, poll asynchronously.

### Anti-Pattern 2: Hardcoded Register Mapping in Server Code
**What:** Embedding register addresses and translation logic directly in the Modbus server handler.
**Why bad:** Impossible to add new inverter brands. Mixing protocol handling with business logic.
**Instead:** Separate the SunSpec server (protocol), translation engine (mapping), and inverter plugin (brand-specific reads).

### Anti-Pattern 3: Synchronous Modbus Operations
**What:** Using blocking Modbus calls in the server request handler.
**Why bad:** Venus OS polls multiple register blocks. If one SolarEdge read blocks, all Venus OS requests queue up and timeout.
**Instead:** Use async I/O (asyncio). Poll SolarEdge in background task, serve from register store.

### Anti-Pattern 4: Faking the Manufacturer String as "Fronius"
**What:** Setting the SunSpec Common Model manufacturer to "Fronius" to trick Venus OS.
**Why bad:** Potentially fragile and misleading. However, this may actually be necessary -- `dbus-fronius` may filter on manufacturer string.
**Mitigation:** Make the manufacturer string configurable. Start with "Fronius" for compatibility, test if Venus OS also accepts generic SunSpec devices. **This needs verification during implementation.**

## Suggested Build Order

The dependency graph dictates this order:

### Phase 1: Foundation (no external dependencies)
1. **Config Store** -- JSON config file read/write. Needed by everything.
2. **Register Store** -- In-memory register map with read/write. Needed by server and engine.
3. **SunSpec Server** -- Modbus TCP server serving from Register Store. Can test with static data.

**Milestone:** Venus OS can connect to proxy, sees a "frozen" SunSpec device with hardcoded values.

### Phase 2: SolarEdge Integration
4. **Plugin Interface** -- Define the abstract InverterPlugin.
5. **SolarEdge Plugin** -- Implement Modbus TCP client for SE30K. Read real data.
6. **Translation Engine** -- Map SolarEdge data to Fronius SunSpec registers. Wire up polling loop.

**Milestone:** Venus OS sees live SolarEdge data through the proxy.

### Phase 3: Control Path
7. **Write handling in SunSpec Server** -- Accept WriteMultipleRegisters for Model 123.
8. **Reverse translation** -- Map Fronius power limit registers to SolarEdge equivalents.
9. **SolarEdge write path** -- Plugin sends power limit commands to inverter.

**Milestone:** Venus OS can curtail SolarEdge output through the proxy.

### Phase 4: Operational
10. **Health Monitor** -- Connection state tracking, stale data detection.
11. **Config Webapp** -- HTTP server with status page and configuration forms.
12. **systemd Service** -- Unit file, auto-restart, logging to journald.

**Milestone:** Production-ready with monitoring and configuration UI.

### Phase 5: Extensibility
13. **Plugin discovery** -- Dynamic loading of inverter plugins from a directory.
14. **Documentation** -- Plugin development guide for future brands.

## Technology Notes for Architecture

### Modbus TCP Server (SunSpec Emulation)
Use **pymodbus** (Python) as the Modbus TCP server. pymodbus supports:
- Async server (asyncio) via `StartAsyncTcpServer`
- Custom request handlers / datastore callbacks
- Both server and client in one library (proxy needs both)

**MEDIUM confidence** -- pymodbus is the standard Python Modbus library. Verify current async API during implementation.

### Concurrency Model
- **asyncio** event loop for all I/O (Modbus server, Modbus client, HTTP server)
- Single process, single thread (adequate for this workload)
- Polling interval configurable (default 2 seconds)
- Register Store uses asyncio.Lock for write atomicity

### Why Single Process
- Only one SolarEdge inverter (initially)
- Only one Venus OS client (or very few)
- Modbus TCP is low-bandwidth (kilobytes/second)
- No CPU-intensive computation
- Simpler deployment, debugging, and resource usage in LXC

## Scalability Considerations

| Concern | Current (1 inverter) | Future (5 inverters) | Future (10+ inverters) |
|---------|---------------------|---------------------|----------------------|
| Polling load | 1 poll/2s, trivial | 5 polls/2s, still trivial | Consider staggered polling |
| Register Store | Single dict | Dict per plugin instance | Same, no issue |
| Venus OS connections | 1 GX device | 1 GX device | Still 1 GX, no change |
| Memory | < 10MB | < 20MB | < 50MB |
| CPU | Negligible | Negligible | Negligible |

Modbus TCP proxy workloads are inherently lightweight. Scaling concerns are architectural (adding brands), not performance.

## Key Architectural Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| dbus-fronius checks manufacturer="Fronius" | Proxy rejected by Venus OS | Make manufacturer string configurable; test early |
| dbus-fronius expects specific SunSpec model order | Proxy rejected | Study dbus-fronius source code to determine exact expectations |
| SolarEdge register map differs from documentation | Wrong data displayed | Verify registers by reading actual SE30K and comparing to SolarEdge Modbus docs |
| Venus OS uses Fronius Solar API (HTTP) instead of/alongside Modbus | Proxy incomplete | Check if dbus-fronius uses HTTP API for discovery; may need HTTP endpoint too |
| Power limit writes use different SolarEdge register semantics | Curtailment fails | Test write path separately; SolarEdge may need specific enable registers |

## Critical Unknown: Does dbus-fronius Use HTTP API?

Some Fronius integrations in Venus OS use the **Fronius Solar API** (HTTP/JSON) for discovery and data, not Modbus TCP. The dbus-fronius driver may:

- **Use Modbus TCP only** -- our proxy approach works directly
- **Use HTTP Solar API for discovery, Modbus for data** -- we need a minimal HTTP endpoint
- **Use HTTP Solar API for everything** -- we need to emulate the Solar API instead

**This is the single most important thing to verify before writing code.** Check the `dbus-fronius` source on GitHub. If it uses the Solar API, the architecture needs an additional HTTP endpoint component.

**LOW confidence** -- I cannot verify this without web access. This must be researched as the first task in Phase 1.

## Sources

- SunSpec Alliance Modbus specifications (training data, MEDIUM confidence)
- pymodbus library documentation (training data, MEDIUM confidence)
- Victron Venus OS integration documentation (training data, MEDIUM confidence)
- SolarEdge Modbus register documentation (training data, MEDIUM confidence)

**Note:** Web search and web fetch tools were unavailable during this research session. All findings are based on training data (cutoff ~May 2025). Key claims -- especially around dbus-fronius discovery protocol and exact SunSpec model requirements -- should be verified against current source code before implementation.
