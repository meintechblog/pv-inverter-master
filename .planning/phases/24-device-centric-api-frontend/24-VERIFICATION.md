---
phase: 24-device-centric-api-frontend
verified: 2026-03-21T12:00:00Z
status: gaps_found
score: 15/15 must-haves verified (goal achieved); 9 tests broken by phase changes
re_verification: false
gaps:
  - truth: "All existing and new tests pass"
    status: failed
    reason: "Phase 24 frontend restructure broke 8 tests that assert the old nav contract (data-page= attributes, shared_ctx WebSocket fixture). One additional pre-existing failure for Venus OS override 409 logic removed in a prior phase."
    artifacts:
      - path: "tests/test_theme.py"
        issue: "TestSidebarNavigation (4 tests) assert data-page= attributes that no longer exist after hash router replacement"
      - path: "tests/test_websocket.py"
        issue: "4 tests use shared_ctx fixture pattern; ws_handler now requires app_ctx (KeyError: 'app_ctx')"
      - path: "tests/test_webapp.py"
        issue: "test_power_limit_venus_override_rejection expects 409 response for Venus OS priority block that was intentionally removed before phase 24 (pre-existing)"
    missing:
      - "Update tests/test_theme.py::TestSidebarNavigation to assert new sidebar structure (device-sidebar, ve-sidebar-group) instead of data-page= attributes"
      - "Update tests/test_websocket.py fixture to use app_ctx (AppContext with devices dict) matching new ws_handler contract"
      - "Delete or rewrite test_power_limit_venus_override_rejection to match current intentional behavior (no priority block)"
human_verification:
  - test: "Open the app in a browser, verify sidebar shows INVERTERS / VENUS OS / VIRTUAL PV groups"
    expected: "Grouped device list renders; clicking an inverter navigates to #device/{id}/dashboard"
    why_human: "Visual rendering and navigation cannot be verified without a browser"
  - test: "Click Virtual PV -- verify stacked contribution bar renders with correct proportions"
    expected: "Each inverter segment width is proportional to its power_w share; legend shows names and kW values"
    why_human: "SVG/CSS proportional rendering requires visual inspection"
  - test: "Toggle a device disabled in Config sub-tab"
    expected: "Sidebar entry dims and shows 'Disabled' label; device dashboard shows overlay"
    why_human: "UI state transitions require manual interaction"
  - test: "Click '+' -- verify add modal opens with SolarEdge / OpenDTU type picker"
    expected: "Modal overlays page with type cards; selecting a type shows appropriate form fields"
    why_human: "Modal interaction flow requires browser"
  - test: "Delete a device and click Rueckgaengig within 5 seconds"
    expected: "Device is re-added via POST /api/devices and sidebar updates"
    why_human: "Time-bounded undo toast requires real interaction"
---

# Phase 24: Device-Centric API & Frontend Verification Report

**Phase Goal:** Each device (inverter, Venus OS, virtual PV) has its own sidebar entry, dashboard view, and management interface
**Verified:** 2026-03-21T12:00:00Z
**Status:** gaps_found (goal achieved, 9 tests broken by phase changes)
**Re-verification:** No -- initial verification

---

## Goal Achievement

The phase goal is substantively achieved. All device-centric API endpoints, WebSocket broadcasts, frontend renderers, hash routing, and management flows exist and are wired. The gaps are test suite hygiene failures: tests asserting the old navigation contract that was intentionally replaced.

### Observable Truths -- Plan 01 (API)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/devices returns list with metadata and status | VERIFIED | `devices_list_handler` at webapp.py:1219, registered at line 1485 |
| 2 | GET /api/devices/{id}/snapshot returns per-device data with device_id and type | VERIFIED | `device_snapshot_handler` at webapp.py:1268, registered at line 1487 |
| 3 | GET /api/devices/virtual/snapshot returns aggregated power + throttle info | VERIFIED | `virtual_snapshot_handler` at webapp.py:1296, registered at line 1486 |
| 4 | WebSocket broadcasts include device_id tag | VERIFIED | `broadcast_device_snapshot` at webapp.py:632, payload tagged with `"device_id": device_id` at line 641 |
| 5 | POST/PUT/DELETE /api/devices work as CRUD aliases | VERIFIED | Routes registered at webapp.py:1489-1491, delegating to existing inverter handlers |

**Score:** 5/5

### Observable Truths -- Plan 02 (Frontend)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Sidebar dynamically lists all devices grouped by type | VERIFIED | `renderSidebar` at app.js:65, called on init (line 1914) and on WS device_list (line 296) |
| 2 | Each sidebar entry shows Name + Status-Dot + Live-kW | VERIFIED | `updateSidebarPower` at app.js:355; sidebar entries built with dot + name + power in renderSidebar |
| 3 | Clicking a sidebar inverter shows Dashboard sub-tab | VERIFIED | `showDevicePage` at app.js:195; hashchange wired at line 58 |
| 4 | SolarEdge shows 3-phase AC table; OpenDTU shows DC channel table | VERIFIED | `renderInverterDashboard` at app.js:385, branches on deviceType at line 255 |
| 5 | Each inverter has Dashboard, Registers, Config sub-tabs | VERIFIED | `showDevicePage` renders sub-tabs, calls renderInverterDashboard/Registers/Config per tab |
| 6 | Venus OS has single page with MQTT status, ESS mode, Portal ID, and config | VERIFIED | `renderVenusPage` at app.js:836, 4 sections fully implemented |
| 7 | Virtual PV shows aggregated power + stacked bar + throttle table | VERIFIED | `renderVirtualPVPage` at app.js:1061, `buildVirtualPVPage` builds bar + throttle table |
| 8 | User can add device via + button with discover | VERIFIED | `deleteDeviceWithUndo` at app.js:1351; add modal in `renderAddModal`; POST /api/devices at line 1297 |
| 9 | Delete shows toast with 5s undo; disable greys out | VERIFIED | `deleteDeviceWithUndo` calls `showToast` with 5000ms; `ve-sidebar-device--disabled` class applied |
| 10 | Hash routing uses #device/{id}/dashboard pattern | VERIFIED | `parseRoute` at app.js:41; `navigateTo` sets `window.location.hash = 'device/' + deviceId + '/' + tab` at line 55 |

**Score:** 10/10

### Combined: 15/15 observable truths verified

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact | Status | Evidence |
|----------|--------|----------|
| `src/venus_os_fronius_proxy/webapp.py` | VERIFIED | `devices_list_handler`, `device_snapshot_handler`, `virtual_snapshot_handler`, `broadcast_device_snapshot`, `broadcast_virtual_snapshot`, `broadcast_device_list` all present and substantive |
| `src/venus_os_fronius_proxy/distributor.py` | VERIFIED | `get_device_limits()` at line 239, returns dict comprehension over `_device_states` |
| `tests/test_webapp.py` | VERIFIED | 6 device-specific tests pass (test_devices_list, test_devices_crud_aliases, etc.) |

### Plan 02 Artifacts

| Artifact | Status | Evidence |
|----------|--------|----------|
| `src/venus_os_fronius_proxy/static/app.js` | VERIFIED | Contains `parseRoute`, `renderSidebar`, `showDevicePage`, `renderInverterDashboard`, `renderInverterRegisters`, `renderInverterConfig`, `renderVenusPage`, `renderVirtualPVPage`, `updateVirtualPVPage`, `deleteDeviceWithUndo`, `updateSidebarPower`, `updateActiveDeviceDashboard` |
| `src/venus_os_fronius_proxy/static/style.css` | VERIFIED | Contains `ve-sidebar-group`, `ve-sidebar-device`, `ve-sidebar-device--active`, `ve-sidebar-device--disabled`, `ve-device-tabs`, `ve-device-tab`, `ve-contribution-bar`, `ve-device-disabled-overlay`, `ve-add-modal` |
| `src/venus_os_fronius_proxy/static/index.html` | VERIFIED | Minimal shell: `#device-sidebar` at line 37, `#device-content` at line 58, no static page divs |

---

## Key Link Verification

### Plan 01 Key Links

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `device_snapshot_handler` | `app_ctx.devices[id].collector.last_snapshot` | DeviceState lookup | WIRED | `app_ctx.devices.get(device_id)` at webapp.py:1283 |
| `virtual_snapshot_handler` | `distributor.get_device_limits()` | getattr fallback chain | WIRED | `getattr(getattr(app_ctx, "device_registry", None), "_distributor", None)` + `get_device_limits()` at lines 1305-1306 |
| `broadcast_device_snapshot` | `ws_clients` | tagged JSON with device_id field | WIRED | `payload = json.dumps({"type": "device_snapshot", "device_id": device_id, "data": snapshot})` at webapp.py:641 |
| `/api/devices CRUD aliases` | `inverters_add_handler, inverters_update_handler, inverters_delete_handler` | route registration | WIRED | `add_post("/api/devices", inverters_add_handler)` etc. at lines 1489-1491 |
| `AggregationLayer._broadcast_fn` | `broadcast_device_snapshot` in poll cycle | callback wired in `__main__.py` | WIRED | `_on_aggregation_broadcast` defined and assigned `aggregation._broadcast_fn` at __main__.py:159-168 |

### Plan 02 Key Links

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `renderSidebar` | `GET /api/devices` | fetch on init and WS device_list | WIRED | `fetch('/api/devices')` at app.js:1914; also on device_list WS message at line 296 |
| `ws.onmessage` | `renderDeviceDashboard` (via `updateActiveDeviceDashboard`) | device_snapshot type check with device_id routing | WIRED | `handleDeviceSnapshot(msg)` called for `device_snapshot` at app.js:294; routes via `_activeDeviceId` at line 325 |
| `navigateTo` | `window.location.hash` | #device/{id}/{tab} pattern | WIRED | `window.location.hash = 'device/' + deviceId + '/' + tab` at app.js:55 |
| `deleteDeviceWithUndo` | `DELETE /api/devices/{id}` | fetch + showToast with undo callback | WIRED | `fetch('/api/devices/' + deviceId, { method: 'DELETE' })` at app.js:1358; undo re-POSTs at line 1380 |

---

## Requirements Coverage

| Requirement | Plan | Description | Status | Evidence |
|-------------|------|-------------|--------|----------|
| API-01 | 24-01 | REST per-device snapshots and status | SATISFIED | GET /api/devices, /api/devices/{id}/snapshot implemented and returning correct JSON |
| API-02 | 24-01 | WebSocket broadcasts with device_id tag | SATISFIED | broadcast_device_snapshot/virtual_snapshot/device_list wired into poll cycle |
| API-03 | 24-01 | CRUD endpoints at /api/devices | SATISFIED | POST/PUT/DELETE /api/devices registered as aliases |
| UI-01 | 24-02 | Dynamic sidebar with all configured devices | SATISFIED | renderSidebar groups INVERTERS / VENUS OS / VIRTUAL PV with live power |
| UI-02 | 24-02 | Per-inverter dashboard/registers view | SATISFIED | renderInverterDashboard (type-specific), renderInverterRegisters, renderInverterConfig |
| UI-03 | 24-02 | Venus OS sidebar entry with ESS + MQTT + Portal ID | SATISFIED | renderVenusPage implements all 4 sections |
| UI-04 | 24-02 | Virtual PV view with contribution breakdown | SATISFIED | renderVirtualPVPage with stacked bar and throttle table |
| UI-05 | 24-02 | + button with discover for manual scan | SATISFIED | Add modal with type picker and POST /api/scanner/discover integration |
| UI-06 | 24-02 | Device data disappears on disable/delete | SATISFIED | disable: ve-sidebar-device--disabled + overlay; delete: navigates away, sidebar re-renders via WS |

All 9 requirement IDs accounted for. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `webapp.py` | 439 | `# TODO Phase 24: per-device register viewer` | Info | Legacy `/api/registers` still returns first device's data; the new `/api/devices/{id}/snapshot` is the correct per-device path. Not a stub -- endpoint works. |
| `webapp.py` | 497 | `# TODO Phase 24: aggregated virtual dashboard` | Info | Legacy `/api/dashboard` still returns first device collector. New `/api/devices/virtual/snapshot` is the correct endpoint. Not a stub -- endpoint works. |
| `app.js` | 875 | `// Section 2: ESS Settings (placeholder -- updated via WS)` | Info | Comment describes the data flow (ESS populated by WS events), not a stub. Full rendering code follows. |

No blocker or warning-level anti-patterns found in the phase deliverables.

---

## Test Suite Regressions (Gaps)

### Broken Tests: Navigation Contract

**4 tests in `tests/test_theme.py::TestSidebarNavigation`** fail because they assert old `data-page=` attributes (e.g. `data-page="dashboard"`, `data-page="config"`) that were part of the previous 3-tab navigation system. Phase 24 replaced this with a hash router (`#device/{id}/{tab}`). The assertions no longer match the new `index.html` minimal shell.

Fix needed: Update tests to assert new sidebar structure (`#device-sidebar`, `ve-sidebar-group`).

### Broken Tests: WebSocket Fixture

**4 tests in `tests/test_websocket.py`** fail because their fixture builds `app["shared_ctx"]` but `ws_handler` now reads `app["app_ctx"]` (typed `AppContext`). The fixture predates the typed context migration.

Fix needed: Rewrite fixture to provide `app["app_ctx"]` with a mock `AppContext` containing a `devices` dict with `DeviceState` entries.

### Pre-existing Failure (not introduced by phase 24)

**1 test `tests/test_webapp.py::test_power_limit_venus_override_rejection`** expected HTTP 409 for Venus OS priority blocking, but that behavior was intentionally removed in an earlier phase ("No Venus OS priority block -- manual limit is additive"). The comment at webapp.py:837 documents the intentional design change. This test was failing before phase 24 started.

Fix needed: Delete or rewrite this test to assert the current additive behavior (200 response).

---

## Human Verification Required

### 1. Sidebar Visual Rendering

**Test:** Open the app in browser; confirm sidebar shows INVERTERS, VENUS OS, VIRTUAL PV group headers with device entries under each.
**Expected:** Groups are collapsible; each inverter shows name + status dot + live kW value; active entry is highlighted blue.
**Why human:** CSS rendering and click interaction require browser.

### 2. Type-Specific Dashboard Layout

**Test:** Click a SolarEdge inverter -- verify 3-phase AC table appears. If OpenDTU configured, click it -- verify DC channel table appears.
**Expected:** Different layout per device type; gauge shows live power.
**Why human:** Visual differentiation between device types requires browser inspection.

### 3. Virtual PV Stacked Contribution Bar

**Test:** Click Virtual PV in sidebar. Verify contribution bar segments are proportional to each inverter's power share.
**Expected:** Bar fills full width; each segment color matches legend entry; total kW shown above bar.
**Why human:** Proportional CSS rendering requires visual inspection.

### 4. Add Device Modal

**Test:** Click "+" button in sidebar. Select "SolarEdge Inverter". Click "Discover".
**Expected:** Modal opens with type picker cards; selecting type reveals correct form fields; Discover triggers scan progress.
**Why human:** Modal interaction flow requires browser.

### 5. Delete with 5s Undo

**Test:** Open a device's Config tab. Click "Delete Device". Within 5 seconds, click "Rueckgaengig" in toast.
**Expected:** Device is re-added; sidebar updates; navigate to restored device's dashboard.
**Why human:** Time-bounded toast interaction requires real browser timing.

---

## Gaps Summary

The phase goal is fully achieved at the code level: all 15 observable truths are verified, all artifacts are substantive, all key links are wired, and all 9 requirements are satisfied.

The `gaps_found` status is driven entirely by the test suite:

1. **8 tests assert the old navigation contract** (4 for `data-page=` attributes, 4 for `shared_ctx` WebSocket fixture) that was intentionally replaced by the device-centric hash router. These tests need updating to match the new architecture.

2. **1 pre-existing test failure** (`test_power_limit_venus_override_rejection`) predates phase 24 and tests behavior intentionally removed in an earlier phase.

None of these failures indicate missing or broken functionality in the phase deliverables. The fix is test maintenance, not implementation work.

---

*Verified: 2026-03-21T12:00:00Z*
*Verifier: Claude (gsd-verifier)*
