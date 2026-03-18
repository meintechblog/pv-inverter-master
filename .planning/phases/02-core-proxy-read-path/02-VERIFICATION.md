---
phase: 02-core-proxy-read-path
verified: 2026-03-18T07:44:35Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 2: Core Proxy Read Path Verification Report

**Phase Goal:** Venus OS discovers the proxy as a Fronius inverter and displays live monitoring data from the SolarEdge SE30K
**Verified:** 2026-03-18T07:44:35Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All truths are sourced from the two plan must_haves sections (02-01-PLAN.md and 02-02-PLAN.md).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | InverterPlugin ABC defines the contract all brand plugins must implement | VERIFIED | `plugin.py` — ABC with 5 abstract methods: connect, poll, get_static_common_overrides, get_model_120_registers, close |
| 2 | build_initial_registers() produces exactly 177 uint16 values with correct SunSpec header, Common Model, Model 103 placeholder, Model 120 synthesis, Model 123 placeholder, and End marker | VERIFIED | `sunspec_models.py` lines 50-112; runtime-verified: 177 registers, header 0x5375/0x6E53, DIDs [1,103,120,123,0xFFFF] correct |
| 3 | RegisterCache tracks staleness and serves last-known values until timeout | VERIFIED | `register_cache.py` — `is_stale` property using `time.monotonic()`, default 30s, starts stale before first update |
| 4 | Existing 27 register mapping tests still pass | VERIFIED | Full test suite: 101 tests pass (includes all prior test files) |
| 5 | SolarEdge plugin polls SE30K registers and returns PollResult with translated data | VERIFIED | `plugins/solaredge.py` — two `read_holding_registers` calls (67 at 40002, 52 at 40069), returns PollResult |
| 6 | Proxy server accepts Modbus TCP connections on port 502 unit ID 126 | VERIFIED | `proxy.py` run_proxy binds to 0.0.0.0:502, `ModbusServerContext(slaves={126: slave_ctx}, single=False)`; integration test `test_server_accepts_connection` passes |
| 7 | Venus OS reads from the register cache, not passthrough to SE30K | VERIFIED | `StalenessAwareSlaveContext.getValues()` reads from datablock in `ModbusSlaveContext`; `_poll_loop` updates via `cache.update()`; `test_serves_from_cache` passes |
| 8 | Poller runs asynchronously at 1-second intervals independent of Venus OS requests | VERIFIED | `_poll_loop` runs as concurrent asyncio task in `asyncio.gather()`; `POLL_INTERVAL = 1.0`; configurable for tests |
| 9 | Server serves correct SunSpec model chain that Venus OS can walk for discovery | VERIFIED | `test_sunspec_discovery_flow` walks full chain: Header -> 1 -> 103 -> 120 -> 123 -> 0xFFFF, all DIDs/Lengths confirmed correct |
| 10 | After 30s without a successful poll, server returns Modbus exception 0x04 (SLAVE_DEVICE_FAILURE) to Venus OS | VERIFIED | `StalenessAwareSlaveContext.getValues()` raises exception when `cache.is_stale`; pymodbus converts to ExceptionResponse; `test_returns_error_when_stale` passes |

**Score:** 10/10 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/venus_os_fronius_proxy/__init__.py` | Package marker | VERIFIED | Exists |
| `src/venus_os_fronius_proxy/plugin.py` | InverterPlugin ABC and PollResult dataclass | VERIFIED | Substantive: 60 lines, 5 abstract methods, PollResult with 4 fields. Wired: imported by solaredge.py and proxy.py |
| `src/venus_os_fronius_proxy/sunspec_models.py` | Static SunSpec model chain builder | VERIFIED | Substantive: 138 lines, exports build_initial_registers, apply_common_translation, encode_string, DATABLOCK_START, TOTAL_REGISTERS. Wired: imported by register_cache.py, proxy.py, solaredge.py, test_proxy.py |
| `src/venus_os_fronius_proxy/register_cache.py` | Cache wrapper with staleness tracking | VERIFIED | Substantive: 50 lines, RegisterCache class with update(), is_stale property, time.monotonic(). Wired: imported by proxy.py |
| `src/venus_os_fronius_proxy/plugins/__init__.py` | Plugin subpackage marker | VERIFIED | Exists |
| `src/venus_os_fronius_proxy/plugins/solaredge.py` | SolarEdge SE30K plugin implementing InverterPlugin | VERIFIED | Substantive: 144 lines, SolarEdgePlugin(InverterPlugin), two read_holding_registers calls. Wired: imported by __main__.py and test_proxy.py fixture |
| `src/venus_os_fronius_proxy/proxy.py` | Proxy orchestration: server + poller wiring | VERIFIED | Substantive: 181 lines, StalenessAwareSlaveContext, run_proxy, _poll_loop, _start_server. Wired: imported by __main__.py and test_proxy.py |
| `src/venus_os_fronius_proxy/__main__.py` | Entry point for python -m venus_os_fronius_proxy | VERIFIED | Substantive: 34 lines, creates SolarEdgePlugin, calls asyncio.run(run_proxy(...)) |
| `tests/test_sunspec_models.py` | Tests for model chain builder | VERIFIED | 28 tests covering all register positions, encoding, translation, negative int16 |
| `tests/test_register_cache.py` | Tests for cache staleness behavior | VERIFIED | 8 tests covering starts_stale, not_stale_after_update, becomes_stale_after_timeout, writes_to_datablock |
| `tests/test_solaredge_plugin.py` | SolarEdge plugin unit tests | VERIFIED | 17 tests, mock AsyncModbusTcpClient, covers all methods |
| `tests/test_proxy.py` | Proxy integration tests including staleness error behavior | VERIFIED | 9 integration tests on real pymodbus server: discovery, cache serving, Fronius manufacturer, staleness error, unit ID filtering |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `plugins/solaredge.py` | `plugin.py` | `class SolarEdgePlugin(InverterPlugin)` | WIRED | Line 37: `class SolarEdgePlugin(InverterPlugin)` — confirmed |
| `proxy.py` | `register_cache.py` | `cache.update` and `cache.is_stale` | WIRED | Lines 92-93: `cache.update(COMMON_CACHE_ADDR, ...)` and `cache.update(INVERTER_CACHE_ADDR, ...)`; line 68: `if self._cache.is_stale` |
| `proxy.py` | `sunspec_models.py` | `build_initial_registers()` | WIRED | Line 141: `initial_values = build_initial_registers()` — confirmed |
| `proxy.py` | pymodbus ModbusTcpServer | unit ID 126 context | WIRED | Lines 154-157: `ModbusServerContext(slaves={PROXY_UNIT_ID: slave_ctx}, single=False)` with PROXY_UNIT_ID=126 |
| `sunspec_models.py` | register-mapping-spec.md | implements register layout | WIRED | All register positions (DIDs, Lengths, addresses) match the spec exactly — verified by runtime check |
| `register_cache.py` | pymodbus ModbusSequentialDataBlock | `datablock.setValues` | WIRED | Line 37: `self.datablock.setValues(address, values)` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROXY-01 | 02-02 | Modbus TCP Server laeuft und akzeptiert Verbindungen von Venus OS | SATISFIED | `proxy.py` run_proxy creates ModbusTcpServer on port 502; `test_server_accepts_connection` passes |
| PROXY-02 | 02-01 | SunSpec Common Model (Model 1) korrekt bereitgestellt mit Fronius-Manufacturer-String | SATISFIED | `sunspec_models.py` builds Common Model DID=1, Length=65, manufacturer="Fronius"; `test_common_model_has_fronius_manufacturer` passes |
| PROXY-03 | 02-02 | SunSpec Inverter Model 103 korrekt bereitgestellt mit Live-Daten vom SE30K | SATISFIED | SolarEdgePlugin polls 52 registers at 40069, proxy updates cache; `test_inverter_registers_from_cache` verifies live value (440) visible after poll |
| PROXY-04 | 02-01 | SunSpec Nameplate Model (Model 120) korrekt bereitgestellt | SATISFIED | `sunspec_models.py` synthesizes Model 120 (DID=120, Length=26, DERTyp=4, WRtg=30000); `test_sunspec_discovery_flow` confirms DID/Length at 40121 |
| PROXY-05 | 02-01 | SunSpec Model Chain korrekt aufgebaut (Header -> Common -> Inverter -> Nameplate -> End) | SATISFIED | `build_initial_registers()` constructs full chain; `test_sunspec_discovery_flow` walks Header -> 1 -> 103 -> 120 -> 123 -> 0xFFFF |
| PROXY-06 | 02-02 | SolarEdge Register werden per Modbus TCP Client async gepollt | SATISFIED | `SolarEdgePlugin.poll()` uses `AsyncModbusTcpClient`; `_poll_loop` runs as asyncio task |
| PROXY-07 | 02-01 | Venus OS wird aus Register-Cache bedient (nicht synchron durch-proxied) | SATISFIED | `StalenessAwareSlaveContext` reads from `ModbusSlaveContext` datablock (cache); poller writes to cache independently; `test_serves_from_cache` confirms decoupled serving |
| PROXY-08 | 02-01 | Scale Factors korrekt uebersetzt zwischen SolarEdge und Fronius SunSpec-Profil | SATISFIED | Per register-mapping-spec.md, all Model 103 SFs are PASSTHROUGH (same SunSpec format both sides); Model 120 SFs synthesized correctly (WRtg_SF=0, PFRtg_SF=-2 as uint16); `test_model_120_pf_rtg_sf_negative` confirms negative SF encoding |
| PROXY-09 | 02-02 | Venus OS erkennt und zeigt den Proxy als Fronius Inverter an | NEEDS HUMAN | Full SunSpec chain is correct and Fronius manufacturer is in registers; actual Venus OS discovery cannot be tested without hardware |
| ARCH-01 | 02-01 | Plugin-Interface definiert fuer Inverter-Marken (SolarEdge als erstes Plugin) | SATISFIED | `InverterPlugin` ABC in plugin.py; `SolarEdgePlugin` in plugins/solaredge.py is first implementation |
| ARCH-02 | 02-01 | Register-Mapping als austauschbares Modul (nicht hardcoded) | SATISFIED | `sunspec_models.py` is a standalone module; plugin owns brand-specific mappings (Model 120, Common overrides); proxy core is brand-agnostic |

---

## Anti-Patterns Found

No blockers or warnings found in production source files.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_plugin.py` | 53, 56 | `return {}` and `return []` in DummyPlugin | Info | Test helper only — concrete test fixture implementing ABC for instantiation tests; not production stub |
| `proxy.py` | 72 | `raise Exception(...)` instead of `ModbusIOException(exception_code=0x04)` | Info | Intentional deviation: pymodbus 3.8.6 does not accept `exception_code` kwarg; any raised exception produces ExceptionResponse(SLAVE_FAILURE=0x04). Documented in 02-02-SUMMARY.md. Behavior is correct. |

---

## Human Verification Required

### 1. Venus OS Discovery and Recognition (PROXY-09)

**Test:** Connect the proxy host to the Venus OS network. Start `python3 -m venus_os_fronius_proxy` on the LXC. On Venus OS, navigate to Settings > Devices or check the device list. Look for the proxy appearing as a Fronius inverter with the IP of the LXC.

**Expected:** Venus OS dbus-fronius service discovers the proxy at port 502, unit ID 126. The device appears in the Venus OS UI labeled as a Fronius inverter. Live power data (W, V, A) from the SE30K is displayed and updates approximately every second.

**Why human:** Venus OS dbus-fronius discovery, dbus registration, and UI rendering cannot be tested programmatically from the development machine. The full SunSpec chain is code-verified correct, but the actual discovery handshake requires the real Venus OS software stack running.

---

## Summary

Phase 2 goal is achieved in code. All 10 observable truths are verified. All 11 requirement IDs from the plan frontmatter are either satisfied by code evidence or require human hardware testing (PROXY-09). The full test suite of 101 tests passes in 26.6 seconds with zero failures.

The proxy:
- Serves the correct SunSpec model chain (Header -> 1 -> 103 -> 120 -> 123 -> 0xFFFF) readable at standard addresses
- Presents "Fronius" as manufacturer in Common Model after each poll
- Decouples Venus OS reads from SolarEdge polling via the RegisterCache
- Returns Modbus exception 0x04 after 30 seconds without a successful poll
- Is executable via `python3 -m venus_os_fronius_proxy`

One item requires live hardware testing to confirm full goal achievement: PROXY-09 (Venus OS actually recognizes and displays the device). All automated indicators for this are green.

---

_Verified: 2026-03-18T07:44:35Z_
_Verifier: Claude (gsd-verifier)_
