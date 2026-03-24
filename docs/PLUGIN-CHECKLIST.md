# New Inverter Plugin Checklist

When adding a new device type (like Shelly, OpenDTU, etc.), every item below must be addressed. This prevents the "forgot to wire X" bugs that happened during Shelly integration.

## Backend

- [ ] **Plugin class** — Implements `InverterPlugin` ABC (connect, poll, close, write_power_limit, get_model_120_registers, reconfigure)
- [ ] **Profile system** — If device has API variants (e.g. Gen1/Gen2), use strategy pattern with profile classes
- [ ] **Plugin factory** — Add `elif entry.type == "newtype":` branch in `plugins/__init__.py`
- [ ] **Config fields** — Add any device-specific fields to `InverterEntry` dataclass in `config.py`
- [ ] **SunSpec encoding** — `_encode_model_103()` with correct register offsets, `abs()` for power/current (devices may report negative for generation)
- [ ] **Discovery module** — If device supports network discovery (mDNS, HTTP scan, etc.)
- [ ] **Probe endpoint** — `POST /api/{type}/probe` for auto-detection before adding
- [ ] **Discovery endpoint** — `POST /api/{type}/discover` for LAN scanning
- [ ] **Control endpoint** — Device-specific control (e.g. `POST /api/devices/{id}/{type}/switch`)
- [ ] **Throttle default** — Set `throttle_enabled` default appropriately in `inverters_add_handler` (False for devices without power limiting)

## Frontend — Add Device Flow

- [ ] **Type card** — Third/fourth option in `showAddDeviceModal()` type picker
- [ ] **Add form** — Device-specific fields in `showAddForm()` (host, name, rated_power, etc.)
- [ ] **Probe on Add** — Auto-probe device before saving, show hint-card with result
- [ ] **Discovery button** — Type-filtered discovery (only scan for selected device type)
- [ ] **Discovery results** — Checkbox list with device name, IP, generation/model

## Frontend — Device Dashboard

- [ ] **AC Output card** — Single-phase devices use `buildDCChannelCard` (one-row table, no L1/L2/L3 labels). Three-phase devices use `buildPhaseCard`
- [ ] **DC section** — Hide if device has no DC data (check `dc_voltage_v || dc_current_a || dc_power_w`)
- [ ] **Connection card controls** — On/Off/Restart buttons matching device capabilities (OpenDTU: Power On/Off/Restart, Shelly: Switch On/Off)
- [ ] **Relay/status display** — Show device-specific status in connection card (relay state, producing, reachable, etc.)

## Frontend — Config Page

- [ ] **Config form fields** — Device-specific fields (host, generation badge, rated_power, gateway credentials, etc.)
- [ ] **Readonly fields** — Auto-detected values (generation) shown as readonly badge
- [ ] **Hide irrelevant fields** — No Port/UnitID for Shelly, no Gateway for SolarEdge

## API — Device List & Snapshot

- [ ] **`_build_device_list()`** — Include ALL config fields needed by config page: `rated_power`, `throttle_order`, `throttle_enabled`, plus device-specific fields (`shelly_gen`, `gateway_*`)
- [ ] **`device_snapshot_handler()`** — Include config fields in both the normal and "no data yet" response branches
- [ ] **Register viewer headers** — Dynamic column labels per device type in `buildRegisterViewer()` (not hardcoded "SE30K Source")

## Tests

- [ ] **Plugin unit tests** — ABC compliance, profile polling, SunSpec encoding, energy tracking, missing field handling
- [ ] **Control tests** — Switch/power handler route tests (success, not-found, wrong-type, invalid-body)
- [ ] **Discovery tests** — Probe handler (success, gen detection, unreachable), mDNS discovery mock
- [ ] **Config tests** — Throttle default, add handler with device-specific fields

## Deployment

- [ ] **All new files copied** — Plugin, profiles, discovery module, updated webapp, config, static files
- [ ] **File ownership** — Config dir writable by service user (`pv-proxy`)
- [ ] **Service restart** — Verify service starts cleanly with new plugin code
