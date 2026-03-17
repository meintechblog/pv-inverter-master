# Domain Pitfalls

**Domain:** Modbus TCP proxy / Solar inverter protocol translation (SolarEdge to Fronius SunSpec for Venus OS)
**Researched:** 2026-03-17
**Overall Confidence:** MEDIUM (based on training data -- web search/fetch unavailable for live verification)

## Critical Pitfalls

Mistakes that cause rewrites, hardware miscommunication, or Venus OS rejection.

### Pitfall 1: SunSpec Model Discovery Sequence Must Be Exact

**What goes wrong:** Venus OS (via `dbus-fronius`) does not just read arbitrary Modbus registers. It performs SunSpec model discovery: it reads the "SunS" marker at register 40000 (or 0), then walks the model chain (Common Model 1 -> Inverter Model 101/102/103 -> etc.) by reading each model's ID and length to find the next. If the model chain is malformed, has wrong lengths, or is missing expected models, Venus OS will not recognize the device at all.

**Why it happens:** Developers focus on getting individual register values right but neglect the discovery walk. SunSpec model discovery is a linked-list-like structure where each model header declares its length, and the next model starts at `offset + length + 2`. Off-by-one errors in model lengths break the entire chain.

**Consequences:** Venus OS silently ignores the device. No error in proxy logs because the proxy served data -- it just served a broken model chain. Debugging is painful because you don't know which model header broke the walk.

**Prevention:**
- Implement the SunSpec model chain as a first-class data structure, not ad-hoc register mapping
- The chain MUST start with `0x53756e53` ("SunS") at the base register (typically 40000 or 40001 depending on convention)
- Common Model (ID 1, length 65 or 66) must be first after the marker
- Inverter model (101 for single-phase, 103 for three-phase) must follow
- End-of-models marker (model ID 0xFFFF, length 0) must terminate the chain
- Write a validator that walks your own model chain and verifies the math before serving it

**Detection:** Use `mbpoll` or a SunSpec validation tool to walk the model chain from the proxy's TCP port. If the walk breaks, fix the lengths before testing with Venus OS.

**Phase:** Must be correct in the very first phase (core proxy). This is day-one architecture, not a later refinement.

---

### Pitfall 2: Venus OS dbus-fronius Expects Fronius-Specific Behavior, Not Just Generic SunSpec

**What goes wrong:** Developers assume "if I serve valid SunSpec, Venus OS will accept it." Venus OS's `dbus-fronius` driver is not a generic SunSpec client. It has Fronius-specific expectations: particular manufacturer string matching, specific SunSpec model IDs, possibly Fronius-proprietary register extensions for power limiting, and specific discovery behavior (it scans for Fronius devices via Fronius Solar API on port 80 OR Modbus TCP, depending on version).

**Why it happens:** The SunSpec standard is well-documented, but `dbus-fronius` is Victron's proprietary integration code. Its exact matching logic for manufacturer strings, model names, and supported feature set is only documented in its source code.

**Consequences:** The proxy serves perfectly valid SunSpec but Venus OS still refuses to recognize it, or recognizes it but cannot control it. Power limiting commands may use Fronius-specific mechanisms (e.g., Fronius Solar API HTTP endpoints rather than SunSpec Model 123/124 for power control).

**Prevention:**
- Read the `dbus-fronius` source code on GitHub (victronenergy/dbus-fronius) before writing a single line of proxy code. This is the actual specification.
- Pay particular attention to: manufacturer string matching (must contain "Fronius"), model string expectations, which SunSpec models are queried, and how power limiting commands are sent
- Venus OS may also use the Fronius Solar API (HTTP JSON on port 80) for some operations, not just Modbus. If so, the proxy may need an HTTP endpoint too.
- Test against the actual Venus OS version you're running, not assumptions

**Detection:** Enable verbose logging on Venus OS (`dbus-fronius` logs) and watch what it queries. Compare against what your proxy serves.

**Phase:** Research phase -- must be understood before any code is written. The entire register mapping depends on this.

---

### Pitfall 3: Modbus TCP Unit ID / Slave ID Confusion

**What goes wrong:** The proxy binds to a TCP port and serves Modbus responses, but uses the wrong Unit ID (also called Slave ID in Modbus RTU heritage). Venus OS queries a specific Unit ID (often 1 for Fronius, but could be configurable). If the proxy responds to the wrong Unit ID or responds to ALL Unit IDs indiscriminately, Venus OS may either not get responses or get confused by multiple "devices."

**Why it happens:** Modbus TCP carries a Unit ID in every request frame (MBAP header byte 6). Many simple Modbus implementations ignore it and respond to everything. SolarEdge uses Unit ID 1 for the inverter and Unit ID 2 for the meter -- these must NOT be mixed up. The proxy must route Unit IDs correctly: Venus OS queries Unit ID X -> proxy responds as Unit ID X but internally queries SolarEdge on the correct Unit ID.

**Consequences:** Wrong data served (meter data instead of inverter data), Venus OS sees phantom devices, or complete communication failure.

**Prevention:**
- Explicitly handle the Unit ID in the MBAP header of every Modbus TCP request
- Map: Venus OS queries Unit ID N on proxy -> proxy queries SolarEdge Unit ID 1 (inverter) -> proxy responds with Unit ID N
- Never use a "respond to any Unit ID" shortcut
- SolarEdge convention: Unit ID 1 = inverter, Unit ID 2 = meter. Verify for SE30K.

**Detection:** Capture Modbus TCP frames with Wireshark between Venus OS and proxy, verify Unit IDs match expectations.

**Phase:** Core proxy implementation. Must be correct from the start.

---

### Pitfall 4: Endianness and Register Word Order Mismatch

**What goes wrong:** SolarEdge and Fronius may use different byte/word ordering for multi-register values (32-bit integers, floats). SunSpec specifies big-endian for 16-bit registers, and for 32-bit values the high word comes first (registers N, N+1 = high, low). But SolarEdge has been known to deviate, particularly with their proprietary extensions. A proxy that does a naive register-copy without byte-swapping will produce garbage values (e.g., power reading of 1,966,080 W instead of 30,000 W).

**Why it happens:** SunSpec says big-endian, most implementations follow it, but some SolarEdge firmware versions have had byte-order inconsistencies in certain registers. Developers test with small values that happen to look correct in either byte order, then deploy and get wrong readings at higher values.

**Consequences:** Wildly incorrect power/energy readings in Venus OS. Can cause incorrect grid feed-in limiting (Venus OS tells inverter to limit to wrong power level), which can have real electrical consequences.

**Prevention:**
- Read the SolarEdge SunSpec Implementation Technical Note for the exact byte order of each register type
- Test with known values: read a register when the inverter reports a known power output and verify the decoded value matches
- Implement explicit conversion functions for each data type (int16, uint16, int32, uint32, float32, string, scale-factor-adjusted values)
- Never assume two manufacturers use the same byte order without verifying

**Detection:** Compare proxy-decoded values against the SolarEdge monitoring portal or the inverter's own display. If they diverge, byte order is wrong.

**Phase:** Core register mapping. Must be tested with real values early.

---

### Pitfall 5: SunSpec Scale Factor Mishandling

**What goes wrong:** SunSpec encodes many values with separate scale factor registers. For example, AC Power might be in register 40084 with a scale factor in register 40085. The actual value is `raw_value * 10^scale_factor`. The scale factor is a signed int16, typically negative (e.g., -2 means divide by 100). Developers either forget scale factors entirely, apply them in the wrong direction, or apply the SolarEdge scale factors when they should be presenting Fronius-expected scale factors.

**Why it happens:** The proxy must do a double translation: (1) read SolarEdge raw value + SolarEdge scale factor -> compute real value, (2) encode real value into Fronius raw value + Fronius scale factor. If Fronius uses different scale factors than SolarEdge for the same measurement, a naive register copy produces values that are off by factors of 10, 100, or 1000.

**Consequences:** Venus OS displays power as 30 W instead of 30,000 W, or energy as 100,000 kWh instead of 100 kWh. Power limiting calculations go catastrophically wrong.

**Prevention:**
- Always decode SolarEdge values to real physical units (Watts, Volts, Amps, Wh) as an intermediate step
- Then re-encode to Fronius's expected scale factors
- Document the expected scale factor for every register in the Fronius profile
- Unit test every conversion with boundary values

**Detection:** Display proxy's decoded intermediate values in the web UI. Compare against inverter display. If they match, the decode is correct; then verify the re-encode by checking Venus OS displays.

**Phase:** Core register mapping, same phase as the Modbus proxy itself.

---

### Pitfall 6: Connection Management -- Single Modbus TCP Client Limitation

**What goes wrong:** SolarEdge inverters typically allow only ONE concurrent Modbus TCP connection (some firmware allows 2-3). If the proxy holds a persistent connection, and a user also tries to connect with a monitoring tool or SetApp, either the proxy or the other client gets disconnected. Worse: if the proxy's connection drops and it doesn't reconnect cleanly, Venus OS shows stale data indefinitely.

**Why it happens:** Modbus TCP on inverters is a secondary interface, not designed for multi-client access. SolarEdge's Modbus TCP implementation is particularly restrictive. Developers build the proxy assuming reliable persistent connections, then discover connections drop after firmware updates, Wi-Fi hiccups, or inverter sleep cycles (nighttime).

**Consequences:** Proxy serves stale data (last-known values from hours ago), Venus OS makes control decisions based on stale data, or the proxy blocks other tools from accessing the inverter.

**Prevention:**
- Implement robust reconnection logic with exponential backoff
- Use short-lived connections (connect, read, disconnect) if the inverter supports it, or keep-alive with heartbeat polling
- Mark data as stale after a configurable timeout (e.g., 30 seconds without fresh data) and serve error responses to Venus OS rather than stale values
- The proxy should be the ONLY Modbus TCP client to the SolarEdge -- document this requirement
- Handle the SolarEdge inverter going to sleep at night (no solar production -> inverter may close Modbus TCP or return zero/error)

**Detection:** Monitor connection state in the web UI. Log every disconnect/reconnect event. Alert if data age exceeds threshold.

**Phase:** Core proxy implementation. Reconnection logic must be built in from the start, not bolted on.

---

### Pitfall 7: Venus OS Power Limiting Uses Non-SunSpec Fronius Mechanisms

**What goes wrong:** Developers assume Venus OS sends power limit commands via SunSpec Model 123 (Immediate Controls) or Model 124 (Storage). In reality, Venus OS may control Fronius inverters via the Fronius Solar API (HTTP REST) rather than Modbus write commands. If the proxy only implements Modbus and Venus OS expects to send HTTP commands to a Fronius API endpoint, power limiting will silently fail.

**Why it happens:** Fronius has a dual-interface design: Modbus for monitoring, HTTP Solar API for control. Venus OS's `dbus-fronius` implementation may use different interfaces for different operations. This is not documented in SunSpec -- it's a Fronius/Victron-specific integration detail.

**Consequences:** Monitoring works perfectly but power limiting does nothing. The user thinks the system is working but feed-in limiting is not active, potentially causing grid compliance issues.

**Prevention:**
- Read `dbus-fronius` source to determine exactly how power limiting commands are sent
- If HTTP Solar API is required, the proxy must also implement relevant Fronius HTTP API endpoints (typically `/solar_api/v1/SetPowerFlowRealtimeData` or similar)
- This could significantly expand scope -- identify it early
- If SunSpec Model 123 write commands ARE used, verify which registers Venus OS writes and map those writes to SolarEdge's power limiting mechanism (which may also be non-standard)

**Detection:** Attempt a power limit command from Venus OS and capture all network traffic (Modbus AND HTTP) between Venus OS and the proxy.

**Phase:** Must be researched before architecture is finalized. This determines whether the proxy is Modbus-only or Modbus+HTTP.

---

## Moderate Pitfalls

### Pitfall 8: SolarEdge Nighttime Behavior / Sleep Mode

**What goes wrong:** SolarEdge inverters enter a sleep state when there is no solar production (typically at night). In this state, they may close the Modbus TCP port entirely, return all-zero registers, or return error codes. The proxy must handle all three scenarios gracefully.

**Prevention:**
- Detect inverter sleep state and serve appropriate values to Venus OS (zero power, but maintain the device presence so Venus OS doesn't "lose" the inverter)
- Do NOT serve Modbus errors to Venus OS during inverter sleep -- serve zero-power readings instead
- Implement a "last known good" state for static values (serial number, model, ratings) that don't change during sleep
- Test at night, not just during the day

**Detection:** Run the proxy overnight and check Venus OS in the morning. If the inverter "disappeared" from Venus OS, sleep handling is broken.

**Phase:** Should be addressed in the core proxy phase, but can be refined later. At minimum, the proxy must not crash when the inverter sleeps.

---

### Pitfall 9: Modbus TCP Transaction ID Mismatch

**What goes wrong:** Modbus TCP uses transaction IDs in the MBAP header to match requests to responses. The proxy receives a request from Venus OS with transaction ID X, queries SolarEdge (which assigns its own transaction ID Y), gets a response, and must respond to Venus OS with the original transaction ID X. If the proxy naively forwards SolarEdge's transaction ID back to Venus OS, the responses get mismatched.

**Prevention:**
- Maintain a mapping of Venus OS transaction IDs to SolarEdge transaction IDs
- Or better: use independent Modbus TCP sessions. The proxy decodes the Venus OS request, makes its own request to SolarEdge (with its own transaction ID management), decodes the response, and builds a fresh response for Venus OS
- Never forward raw Modbus TCP frames between the two sides

**Detection:** Wireshark capture showing transaction ID mismatches will manifest as Venus OS receiving "wrong" data or timeout errors.

**Phase:** Core proxy implementation.

---

### Pitfall 10: Register Address Offset Conventions (0-based vs 1-based)

**What goes wrong:** Modbus has a long-standing confusion between register addresses and register numbers. Register number 40001 is actually protocol address 0 in Holding Registers (function code 3). SunSpec documentation uses 40001-based numbering. The Modbus TCP wire protocol uses 0-based addressing. SolarEdge documentation may use either convention. If the proxy is off by one, every single register read returns the wrong value.

**Prevention:**
- Choose one convention internally and document it explicitly
- Use 0-based addressing on the wire and SunSpec 40001-based in configuration/documentation
- Conversion: wire_address = sunspec_register - 40001
- Test by reading the "SunS" marker: if you read register 40000 (SunSpec) = wire address 39999 (or 40000 depending on convention) and get 0x53756e53, your addressing is correct
- Be aware that some Modbus libraries auto-convert and some don't

**Detection:** If the SunS marker read fails, addressing is wrong. This should be the first thing tested.

**Phase:** Core proxy, first thing to validate.

---

### Pitfall 11: Polling Rate and Venus OS Timeout Expectations

**What goes wrong:** Venus OS expects responses within a certain timeout. If the proxy has to query SolarEdge, translate, and respond, the total latency might exceed Venus OS's expectations. Also, if Venus OS polls frequently (every 1-2 seconds) and the proxy polls SolarEdge at the same rate, you can overwhelm SolarEdge's Modbus TCP implementation.

**Prevention:**
- Cache SolarEdge register values in the proxy. Serve Venus OS from cache, update cache asynchronously
- Cache TTL should be short (1-5 seconds for power values, longer for static values like serial number)
- Respond to Venus OS immediately from cache, never synchronously proxy each request to SolarEdge
- Monitor round-trip times and log warnings if they approach timeout thresholds

**Detection:** Venus OS logs showing communication timeouts or stale data indicators.

**Phase:** Core proxy architecture. The caching layer is a fundamental design decision, not an optimization.

---

### Pitfall 12: Three-Phase vs Single-Phase Model Confusion

**What goes wrong:** The SE30K is a three-phase inverter. The proxy must serve SunSpec Model 103 (three-phase inverter), not Model 101 (single-phase). Venus OS will read phase-specific registers (L1/L2/L3 voltage, current, power). If the wrong model is served, Venus OS either gets no per-phase data or reads garbage from wrong register offsets.

**Prevention:**
- Verify SE30K serves SunSpec Model 103 (or 113 for float variant)
- The Fronius profile must also be three-phase (Model 103/113)
- Map all three phases correctly -- SolarEdge and Fronius may order the per-phase registers differently
- Test with actual three-phase readings, not just total power

**Detection:** Check if Venus OS shows per-phase data. If it shows single-phase or garbled phase data, the model ID or per-phase register mapping is wrong.

**Phase:** Core register mapping.

---

## Minor Pitfalls

### Pitfall 13: String Register Encoding

**What goes wrong:** SunSpec string fields (manufacturer, model, serial number) are encoded as fixed-length ASCII in Modbus registers (2 characters per register, big-endian). Incorrect padding, wrong byte order within registers, or truncation causes Venus OS to display garbled device names.

**Prevention:**
- Encode strings as SunSpec specifies: each register holds 2 ASCII characters, padded with null bytes, big-endian within each register
- The manufacturer string must read "Fronius" (padded to the field length) for Venus OS to recognize it
- Test string fields specifically -- they're easy to get wrong and painful to debug

**Phase:** Register mapping, but lower priority than numeric values.

---

### Pitfall 14: Systemd Service Restart Behavior

**What goes wrong:** The proxy crashes (OOM, unhandled exception, SolarEdge firmware update restarts Modbus) and systemd restarts it. If the proxy doesn't cleanly re-establish its Modbus TCP listener and SolarEdge connection on restart, Venus OS may hold a stale TCP connection to the proxy's old port and fail to reconnect.

**Prevention:**
- Use `SO_REUSEADDR` on the listening socket
- Implement graceful shutdown (close connections, release ports)
- systemd unit file: `Restart=always`, `RestartSec=5`, `WatchdogSec=30`
- The proxy should log its startup state clearly (listening port, SolarEdge connection status)

**Phase:** Deployment/service configuration phase.

---

### Pitfall 15: SolarEdge Firmware Update Changes Register Map

**What goes wrong:** SolarEdge occasionally changes Modbus register behavior with firmware updates. Registers that worked on one firmware version may return different values or errors on another. The proxy breaks after an inverter firmware update with no changes to proxy code.

**Prevention:**
- Log the SolarEdge firmware version (available via Modbus register) at startup
- Document tested firmware versions
- Make the register mapping configurable or at least easy to update
- Monitor for unexpected errors or value range changes after firmware updates

**Detection:** Sudden value errors or communication failures after a firmware update.

**Phase:** Plugin architecture design -- making register maps easily updatable is part of the maintainability story.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Research / Requirements | Not reading `dbus-fronius` source code | Read the source before designing anything. It IS the spec. |
| Research / Requirements | Assuming Modbus-only (missing HTTP Solar API) | Capture traffic from a real Fronius + Venus OS setup if possible, or read dbus-fronius source |
| Core Proxy (Modbus TCP server) | Unit ID mishandling, transaction ID forwarding, address off-by-one | Validate with `mbpoll` tool before connecting Venus OS |
| Register Mapping | Scale factor errors, byte order issues, wrong SunSpec model | Test with known values from inverter display; unit test all conversions |
| Venus OS Integration | SunSpec model chain broken, manufacturer string wrong | Walk the model chain with a SunSpec validator before Venus OS testing |
| Power Control | Wrong mechanism (Modbus vs HTTP), wrong SolarEdge write registers | Research dbus-fronius control path first; test with low limit values |
| Reliability | Connection drops at night, no reconnection, stale data served | Test overnight; implement staleness detection from day one |
| Plugin Architecture | Over-engineering abstractions before first integration works | Get SolarEdge -> Fronius working end-to-end FIRST, then extract plugin interface |

## Key Research Gaps (could not verify online)

These items need validation with current documentation:

1. **Venus OS Fronius discovery mechanism** -- Does current Venus OS use Fronius Solar API HTTP scanning, Modbus TCP port scanning, or mDNS/SSDP? This fundamentally affects what the proxy must implement. LOW confidence on training data alone.
2. **Venus OS power limiting mechanism** -- HTTP Solar API vs SunSpec Model 123 Modbus writes? Must be verified from `dbus-fronius` source. MEDIUM confidence that HTTP Solar API is involved.
3. **SolarEdge SE30K concurrent Modbus TCP connection limit** -- Training data says 1-3 connections. Must verify for specific model/firmware. LOW confidence.
4. **SolarEdge SE30K power limiting via Modbus** -- Whether SolarEdge supports active power limiting via Modbus TCP writes, and which registers. MEDIUM confidence it's possible but register addresses need verification.

## Sources

- SunSpec Alliance Modbus specification (training data, published standard)
- SolarEdge SunSpec Implementation Technical Note (training data reference -- should be re-fetched)
- Victron Energy `dbus-fronius` repository (GitHub -- should be read directly)
- Modbus TCP/IP specification (Modbus Organization, well-established standard)
- Training data from community forums (Victron Community, SolarEdge forums) -- LOW confidence, needs verification

**Note:** Web search and web fetch tools were unavailable during this research session. All findings are based on training data (cutoff ~May 2025). Critical items flagged above should be verified against current documentation before implementation begins.
