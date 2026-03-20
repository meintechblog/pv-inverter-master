---
phase: 21-data-model-opendtu-plugin
verified: 2026-03-20T20:00:00Z
status: passed
score: 11/11 must-haves verified
---

# Phase 21: Data Model & OpenDTU Plugin Verification Report

**Phase Goal:** The system supports typed device configurations and can poll Hoymiles inverters via OpenDTU REST API
**Verified:** 2026-03-20
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Config with type:'solaredge' and type:'opendtu' entries loads into typed InverterEntry objects | VERIFIED | `InverterEntry.type` field exists with default "solaredge"; load_config parses both types via `__dataclass_fields__` filter |
| 2 | Config with gateways: section loads GatewayConfig objects with host, user, password, poll_interval | VERIFIED | `GatewayConfig` dataclass at config.py:47; load_config parses gateways dict at config.py:129-140 |
| 3 | AppContext dataclass replaces shared_ctx dict in all 5 consumer files | VERIFIED | Zero `shared_ctx` hits in src/ (only comment text in context.py docstrings); app_ctx used 18+ times in __main__.py, 33+ in proxy.py, 37+ in webapp.py |
| 4 | Existing SolarEdge polling and dashboard still work identically after refactor | VERIFIED | 29 config+context tests pass; 25 OpenDTU tests pass; plugin_factory(InverterEntry(type='solaredge')) returns SolarEdgePlugin |
| 5 | Old v3.1 inverter: migration code is removed (fresh config only) | VERIFIED | No migration block in load_config; docstring explicitly states "Old single-inverter inverter: format is ignored"; CONTEXT.md decision: "KEINE Migration" |
| 6 | OpenDTU plugin polls /api/livedata/status and returns PollResult with SunSpec-encoded registers | VERIFIED | opendtu.py:65-151; poll() calls GET /api/livedata/status, encodes to 52-register Model 103 array |
| 7 | Plugin filters by serial number so each Hoymiles inverter is a separate device | VERIFIED | `_find_inverter()` at opendtu.py:153-158 matches by serial; test_poll_serial_filter covers multi-inverter gateways |
| 8 | Plugin sends power limit via POST /api/limit/config with Basic Auth from GatewayConfig | VERIFIED | write_power_limit() at opendtu.py:273-321; BasicAuth created from GatewayConfig in connect(); POST to /api/limit/config with JSON payload |
| 9 | Dead-time guard suppresses re-sends for 30s after a power limit command | VERIFIED | DEAD_TIME_S = 30.0 at opendtu.py:29; guard check at opendtu.py:283; test_dead_time_guard and test_dead_time_guard_expired both pass |
| 10 | Plugin implements all 7 InverterPlugin ABC methods | VERIFIED | connect, poll, get_static_common_overrides, get_model_120_registers, write_power_limit, reconfigure, close — all present; ABC compliance test passes |
| 11 | Shared aiohttp.ClientSession per plugin instance, properly closed on shutdown | VERIFIED | `self._session` created in connect(); closed in close() with `not self._session.closed` guard; test_close_cleans_session passes |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/venus_os_fronius_proxy/config.py` | InverterEntry with type/name/gateway_host, GatewayConfig, load_config parsing gateways | VERIFIED | All fields present; GatewayConfig at line 47; gateways parsing at lines 129-140; get_gateway_for_inverter helper at line 171 |
| `src/venus_os_fronius_proxy/context.py` | AppContext and DeviceState dataclasses | VERIFIED | 89 lines; DeviceState at line 14; AppContext at line 24; all compat property accessors present |
| `src/venus_os_fronius_proxy/__main__.py` | AppContext instantiation replacing shared_ctx dict | VERIFIED | Imports AppContext, DeviceState, plugin_factory; AppContext() instantiated at line 64; plugin_factory called at line 59 |
| `src/venus_os_fronius_proxy/plugins/__init__.py` | plugin_factory function dispatching by type | VERIFIED | plugin_factory at line 7; solaredge branch at line 24; opendtu branch at line 27 (fully wired, no longer raises NotImplementedError) |
| `src/venus_os_fronius_proxy/plugins/opendtu.py` | OpenDTUPlugin implementing InverterPlugin ABC | VERIFIED | 340 lines (min_lines: 150 exceeded); class OpenDTUPlugin(InverterPlugin) at line 32 |
| `tests/test_opendtu_plugin.py` | Unit tests for all DTU requirements | VERIFIED | 509 lines (min_lines: 100 exceeded); 25 test functions; all pass |
| `src/venus_os_fronius_proxy/proxy.py` | app_ctx parameter throughout | VERIFIED | 33 app_ctx references; run_proxy and _poll_loop signatures updated |
| `src/venus_os_fronius_proxy/webapp.py` | app_ctx replacing shared_ctx | VERIFIED | 37 app_ctx references; create_webapp and all handlers updated |
| `src/venus_os_fronius_proxy/venus_reader.py` | app_ctx parameter in venus_mqtt_loop | VERIFIED | venus_mqtt_loop(app_ctx, ...) at line 139; all shared_ctx keys replaced |
| `src/venus_os_fronius_proxy/dashboard.py` | app_ctx parameter | VERIFIED | collect() accepts app_ctx; all shared_ctx references removed |
| `tests/test_config.py` | New typed config tests | VERIFIED | 29 tests pass (includes 7 new tests for typed config) |
| `tests/test_context.py` | AppContext and DeviceState tests | VERIFIED | 5 tests; all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `__main__.py` | `context.py` | `from venus_os_fronius_proxy.context import AppContext` | WIRED | Import at line 19; AppContext() instantiated at line 64 |
| `proxy.py` | `context.py` | `app_ctx: AppContext` parameter | WIRED | `app_ctx` used 33+ times; run_proxy, _poll_loop, StalenessAwareSlaveContext all updated |
| `webapp.py` | `context.py` | `app_ctx: AppContext` parameter | WIRED | `app_ctx` used 37+ times; create_webapp and all handlers updated |
| `opendtu.py` | `plugin.py` | `class OpenDTUPlugin(InverterPlugin)` | WIRED | Inheritance confirmed; ABC compliance test passes |
| `plugins/__init__.py` | `opendtu.py` | `from venus_os_fronius_proxy.plugins.opendtu import OpenDTUPlugin` | WIRED | Lazy import inside opendtu branch at __init__.py:28; plugin created with gateway_config, serial, name |
| `opendtu.py` | `config.py` | `GatewayConfig` for auth credentials | WIRED | `from venus_os_fronius_proxy.config import GatewayConfig` at opendtu.py:14; constructor takes `gateway_config: GatewayConfig` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 21-01 | Config supports typed device entries (type: solaredge or opendtu) | SATISFIED | InverterEntry.type field; load_config parses both types; 29 config tests pass |
| DATA-02 | 21-01 | Typed AppContext replaces flat shared_ctx dict | SATISFIED | Zero shared_ctx in src/; AppContext used across all 5 consumer files |
| DATA-03 | 21-01 | Existing v3.1 configs auto-migrated (type: solaredge as default) | SATISFIED (reinterpreted) | Per CONTEXT.md decision, no migration code was written — a deliberate "clean cut". InverterEntry.type defaults to "solaredge" so any new entry without explicit type is treated as SolarEdge. REQUIREMENTS.md already marks this as complete. |
| DTU-01 | 21-02 | System polls OpenDTU /api/livedata/status for AC Power, Voltage, Current, YieldDay, DC data | SATISFIED | poll() at opendtu.py:65-151; extracts all required fields; 8 register encoding tests pass |
| DTU-02 | 21-02 | Each Hoymiles inverter behind an OpenDTU gateway treated as separate device (serial-based) | SATISFIED | _find_inverter() matches by serial; test_poll_serial_filter confirms only target serial's data is used |
| DTU-03 | 21-02 | System can set power limit via POST /api/limit/config with Basic Auth | SATISFIED | write_power_limit() POSTs to /api/limit/config; BasicAuth from GatewayConfig; test_write_power_limit_success passes |
| DTU-04 | 21-02 | OpenDTU plugin implements InverterPlugin ABC (poll, write_power_limit, reconfigure, close) | SATISFIED | All 7 ABC methods implemented; issubclass(OpenDTUPlugin, InverterPlugin) confirmed |
| DTU-05 | 21-02 | System handles 18-25s Hoymiles power limit latency with dead-time guard | SATISFIED | DEAD_TIME_S = 30.0; guard at opendtu.py:283; test_dead_time_guard and test_dead_time_guard_expired both pass |

---

## Anti-Patterns Found

None detected. No TODOs or stubs remain in phase artifacts. The previous `NotImplementedError` in plugin_factory for the opendtu branch was replaced with the full OpenDTUPlugin in Plan 02. No `console.log`-only handlers, empty returns, or placeholder comments.

---

## Human Verification Required

None. All truths are verifiable from code inspection and automated tests. The phase does not involve visual UI changes or external service integration that cannot be mocked.

---

## Gaps Summary

No gaps. All 11 truths verified, all artifacts pass all three levels (exists, substantive, wired), all 8 requirement IDs satisfied.

**Note on DATA-03:** The requirement text says "auto-migrated" but the implementation deliberately omits migration code per the planning decision documented in CONTEXT.md ("KEINE Migration von v3.1 Config"). The requirement is effectively reinterpreted by the planning decision — the `type` field defaulting to "solaredge" satisfies the intent. REQUIREMENTS.md marks DATA-03 as complete and Phase 21 as the responsible phase, confirming the project owner accepted this interpretation.

---

_Verified: 2026-03-20_
_Verifier: Claude (gsd-verifier)_
