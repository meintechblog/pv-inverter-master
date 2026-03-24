# Domain Pitfalls: Shelly Plugin Integration (v6.0)

**Domain:** Adding Shelly smart device support to multi-inverter PV aggregation proxy
**Researched:** 2026-03-24
**Applies to:** v6.0 milestone (Shelly smart plug/switch as third device type alongside SolarEdge and OpenDTU)
**Overall confidence:** HIGH (verified against official Shelly API docs, existing codebase analysis, and community reports)

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or broken aggregation.

### Pitfall 1: Treating a Switch/Meter as an Inverter

**What goes wrong:** The existing `InverterPlugin` ABC assumes all devices are inverters with percentage-based power limiting (`write_power_limit(enable, limit_pct)`). A Shelly Plug is a switch + power meter -- it can only turn on or off. Sending a 47% power limit to a Shelly makes no sense. If the `PowerLimitDistributor` includes Shelly devices in waterfall calculations, it will compute nonsensical per-device watt budgets that cannot be applied.

**Why it happens:** The codebase evolved around the inverter metaphor. The plugin ABC, the distributor, and the aggregation layer all assume "device = inverter that can be throttled."

**Consequences:**
- `PowerLimitDistributor._waterfall()` computes per-device watt budgets including Shelly `rated_power`, then tries to call `write_power_limit(True, 63.2)` on a device that only supports on/off
- Aggregated WRtg (Model 120 nameplate) includes Shelly rated power, inflating what Venus OS thinks the total system capacity is
- Venus OS sends a global limit percentage that gets distributed across Shelly devices, reducing the budget available for real inverters
- If Shelly `rated_power` is 0 (unset), the distributor's division-by-rated_power in `_waterfall()` causes division by zero

**Prevention:**
- Shelly devices MUST have `throttle_enabled: False` hardcoded. Do NOT allow users to enable throttling on Shelly devices. Enforce this in the config save handler.
- `write_power_limit()` should be a no-op returning `WriteResult(success=True)` -- not an error, since the distributor calls it on all eligible devices.
- Add a separate `switch_control(on: bool)` method that is Shelly-specific, exposed only in the Shelly dashboard UI, NOT through the Venus OS power limit path.
- Consider whether Shelly `rated_power` should be included in WRtg aggregation. If the Shelly monitors a micro-inverter (Balkonkraftwerk), YES -- the power is real PV generation. Store a `contributes_to_aggregation: bool` flag or similar. Default: True.

**Detection:** Venus OS shows higher total capacity than expected. Power limit distribution leaves real inverters with less budget than they should have.

**Phase:** Must be addressed in the very first phase (plugin skeleton). Getting this wrong poisons the aggregation layer.

---

### Pitfall 2: Gen1 vs Gen2/Gen3 API Incompatibility

**What goes wrong:** Gen1 and Gen2+ use completely different API paradigms. Treating them as minor variants leads to a fragile if/else mess, or worse, calling the wrong endpoints silently.

**Gen1 API (Legacy HTTP actions):**
- Status: `GET /status` -- returns flat JSON with `meters` array and `relays` array
- Relay control: `GET /relay/0?turn=on` (or `turn=off`, `turn=toggle`)
- Power data: `meters[0].power` (Watts), `meters[0].total` (**Watt-minutes**, not Wh)
- Temperature: top-level `temperature` field (Celsius, not all models)
- No frequency, no current, no voltage on basic Plug S
- Auth: HTTP Basic Auth; `/shelly` endpoint is auth-free
- Device info: `GET /shelly` returns `{"type": "SHPLG-S", "mac": "...", "auth": false}`

**Gen2/Gen3 API (RPC protocol):**
- Status: `GET /rpc/Switch.GetStatus?id=0` -- returns structured JSON
- Switch control: `GET /rpc/Switch.Set?id=0&on=true`
- Power data: `apower` (Watts), `voltage` (V), `current` (A), `aenergy.total` (**Watt-hours**)
- Frequency: `freq` (Hz), Power factor: `pf`
- Temperature: `temperature.tC` (Celsius), `temperature.tF` (Fahrenheit)
- Auth: Digest Auth (SHA-256), NOT Basic Auth
- Device info: `GET /rpc/Shelly.GetDeviceInfo` returns `{"gen": 2, ...}` or `GET /shelly` also works

**Consequences:**
- Calling `/relay/0` on a Gen2 device: HTTP 404
- Calling `/rpc/Switch.GetStatus` on a Gen1 device: HTTP 404
- Energy values off by 60x if Watt-minutes treated as Watt-hours (Gen1 total of 60000 Wm = 1000 Wh, not 60000 Wh)
- Auth fails silently or returns 401 if wrong auth scheme used

**Prevention:**
- Use a **profile/strategy pattern**: `ShellyGen1Profile` and `ShellyGen2Profile` classes with identical interfaces but different endpoint URLs, JSON parsing logic, energy unit conversion, and auth handling.
- Auto-detect generation at add-device time (see Pitfall 3), store `gen: 1` or `gen: 2` in InverterEntry config, never re-detect at runtime.
- Gen1 energy conversion at parse time: `total_wh = total_watt_minutes / 60.0`
- Gen2 energy: already in Wh, use directly.
- The OpenDTU plugin pattern (single class, single API) does NOT apply here. Two distinct API shapes need two distinct profile implementations.

**Detection:** Energy values 60x too high or too low. HTTP 404 errors in poll logs. Auth 401 errors.

**Phase:** Must be the first implementation decision. Profile pattern needs to be in the plugin skeleton.

---

### Pitfall 3: Unreliable Generation Auto-Detection

**What goes wrong:** The detection strategy of "try Gen2 endpoint, fall back to Gen1" has race conditions and unnecessary complexity. A simpler, universal approach exists.

**Key insight:** Both Gen1 and Gen2+ devices respond to `GET /shelly` (no auth required). The difference:
- Gen1 response: `{"type": "SHPLG-S", "mac": "AABBCCDDEEFF", "auth": false}` -- NO `gen` field
- Gen2 response: `{"id": "shellyplugsg3-AABBCCDDEEFF", "mac": "AABBCCDDEEFF", "gen": 2, "auth_en": false, "model": "S3PG-0011UW160EU", ...}` -- has explicit `gen` field

**Consequences of getting it wrong:**
- Misdetected generation means all subsequent API calls fail with 404
- During firmware OTA update (30-60s), both endpoints are unavailable -- detection at that moment fails entirely
- If detection has a long timeout and tries multiple endpoints sequentially, the add-device flow feels slow

**Prevention:**
- Detection algorithm: Call `GET /shelly` (single request, no auth). If response JSON contains `"gen"` field with value >= 2, it is Gen2+. If no `gen` field exists, it is Gen1.
- One endpoint, no fallback chain, no sequential probing.
- Use a 5-second timeout. If it times out, return "device unreachable" rather than guessing.
- Store detected generation in config (`gen: 1` or `gen: 2`) persistently. Never re-detect automatically.
- Allow manual override in config UI as escape hatch for edge cases.

**Detection:** Config shows wrong generation for a device. Poll errors showing wrong endpoint format.

**Phase:** Add-device flow phase. Detection logic must be solid before any polling begins.

---

### Pitfall 4: No DC Values from Shelly -- Aggregation Register Gaps

**What goes wrong:** Shelly devices measure AC power only (they sit between a wall socket and a load/micro-inverter). They have zero DC data (no DC voltage, DC current, DC power). The existing `AggregationLayer.recalculate()` averages DC voltage across ALL devices by dividing by `n` (total device count). Shelly contributing 0V DC drags down the average.

**Why it happens:** In `aggregation.py` line ~203, `avg_keys` includes `dc_voltage_v`. The average divides by `n = len(decoded_list)` which counts all devices, including those with zero DC.

**Consequences:**
- DC voltage average drops: with 1 SolarEdge at 600V DC and 1 Shelly at 0V DC, average becomes 300V -- wrong
- Venus OS dashboard shows misleading DC values
- If any code divides by DC voltage to compute efficiency, results are halved or worse
- DC current sum is also wrong if Shelly contributes 0 rather than "not applicable"

**Prevention:**
- Shelly plugin MUST set DC registers to SunSpec "not implemented" values (`0x8000` for int16, `0xFFFF` for uint16) rather than zero. The existing `decode_model_103_to_physical()` already converts `0x8000`/`0xFFFF` to 0.0, but the averaging must be fixed.
- Fix `AggregationLayer.recalculate()`: for DC voltage averaging, only count devices where `dc_power_w > 0`. This is a one-line fix but critical.
- Alternative: change DC voltage aggregation from simple average to power-weighted average (which naturally excludes zero-power devices). This is already how OpenDTU computes its own DC voltage.

**Detection:** Venus OS shows lower-than-expected DC voltage after adding a Shelly device.

**Phase:** Plugin implementation phase (register encoding) + aggregation fix in the same phase.

---

## Moderate Pitfalls

### Pitfall 5: Watt-Minute Energy Counter Overflow and Reset

**What goes wrong:** Gen1 Shelly energy counter (`meters[0].total`) is in Watt-minutes and is a cumulative counter that resets to 0 on device reboot/power cycle. Gen2 `aenergy.total` is in Watt-hours and also resets on reboot. If the proxy uses the raw counter value for aggregated `energy_total_wh`, a Shelly reboot causes the aggregated energy total to jump backward, which Venus OS may interpret as negative production.

**Prevention:**
- Track `_last_energy_raw` per-device. If new value < last value, a reset occurred. Maintain an offset: `corrected = current + accumulated_offset`.
- Convert Gen1 Watt-minutes to Wh immediately at parse time: `energy_wh = total_wm / 60.0`
- Gen2: use `aenergy.total` directly (already Wh).
- The proxy uses in-memory tracking only (no persistent DB), so a proxy restart also loses the offset. This is acceptable -- the existing OpenDTU plugin has the same behavior. Document as a known limitation.

### Pitfall 6: Shelly Auth Differences Break Connection

**What goes wrong:** Gen1 uses HTTP Basic Auth. Gen2 uses Digest Auth with SHA-256. Using the wrong auth scheme causes silent 401 failures.

**Prevention:**
- Gen1 profile: `aiohttp.BasicAuth(user, password)` on the session (already used by OpenDTU plugin)
- Gen2 profile: `aiohttp` does NOT natively support Digest Auth. Options:
  1. Use `aiohttp-digestauth` package (adds a dependency)
  2. Skip auth entirely if `auth_en: false` (detectable from `/shelly` response at detection time)
- **Pragmatic approach:** Most Shelly devices in a home LAN have auth disabled by default. Store `auth_enabled: bool` in config during detection. If auth is disabled, skip it entirely. Only implement auth support if a user actually needs it -- and document this limitation.
- For MVP: support auth-disabled Shelly devices only. This covers the vast majority of home setups.

### Pitfall 7: Firmware OTA Update Makes Device Disappear

**What goes wrong:** Shelly auto-update is ON by default. When firmware updates, the device reboots and is unreachable for 30-60 seconds. The proxy's `ConnectionManager` triggers backoff, poll failures accumulate, and the device may be marked as offline in the UI for several minutes.

**Prevention:**
- The existing `ConnectionManager` backoff pattern already handles transient failures. No special case needed.
- Do NOT trigger alarming UI states (red dot, error toast) for short outages. The existing connection state machine (CONNECTING -> CONNECTED -> DISCONNECTED) handles this naturally -- the dot goes orange during backoff.
- Poll failures during OTA should log at DEBUG level for the first 90 seconds, WARNING only after that. The ConnectionManager's exponential backoff already spaces out retries.
- Do NOT try to detect OTA state via API -- it adds complexity for marginal benefit. The device will come back on its own.

### Pitfall 8: Shelly Has No Night Mode Equivalent

**What goes wrong:** Real inverters go offline at night (no solar production, device enters sleep mode). The proxy has a Night Mode state machine that detects prolonged poll failures and serves synthetic zero-power registers. A Shelly Plug monitoring a micro-inverter stays powered 24/7 -- it successfully reports 0W at night but never goes "offline." If night mode logic checks whether ALL devices have consecutive failures, the always-online Shelly prevents night mode from triggering.

**Prevention:**
- Night mode should NOT count Shelly poll failures/successes. Night mode is about inverter sleep state, not power meter availability.
- The Shelly correctly reports 0W at night. The aggregated power becomes 0W. This is the desired behavior -- no special handling needed.
- If night mode is triggered by consecutive poll failures (not by power level), exclude Shelly-type devices from the failure count. Only SolarEdge and OpenDTU devices should trigger night mode.
- Simplest fix: night mode checks `entry.type` and ignores non-inverter types.

### Pitfall 9: Switch State Feedback Lag

**What goes wrong:** After sending `Switch.Set?id=0&on=false` (Gen2) or `relay/0?turn=off` (Gen1), the next poll may still show the old state. Mechanical relay delay is ~10-20ms, but the HTTP round-trip plus the next poll interval (5s) means the UI shows stale state for up to 5 seconds after a switch command.

**Prevention:**
- After a switch command, set an optimistic local state immediately in the UI (JavaScript side).
- On the backend, set a `_switch_pending` flag with timestamp. During the pending window (5 seconds), override the polled relay state with the commanded state in the snapshot.
- Clear the pending flag once the polled state matches the commanded state.
- This mirrors the dead-time guard pattern already used in `OpenDTUPlugin.write_power_limit()`.

### Pitfall 10: Shelly Plug with No Power Monitoring

**What goes wrong:** Not all Shelly models have power metering. Shelly 1 (no PM variant) is a pure relay -- no power, no energy, no temperature data. If a user adds a Shelly 1 (non-PM), the plugin tries to parse power fields that do not exist, and the aggregation layer receives zeroes that dilute the average.

**Prevention:**
- During auto-detection, check the device type/model. Gen1 `type` field: `SHPLG-S` (Plug S, has PM), `SHSW-1` (Shelly 1, no PM), `SHSW-PM` (Shelly 1PM, has PM). Gen2 model field identifies PM variants.
- If the device has no power metering, either reject it at add-device time with a clear message ("This Shelly model does not have power metering and cannot be used as a PV monitor"), or allow it but mark it as relay-only in the UI.
- For MVP: only support PM-capable models. Reject non-PM devices at detection with a helpful error message listing supported models.

---

## Minor Pitfalls

### Pitfall 11: Temperature Field Availability Varies by Model

**What goes wrong:** Not all Shelly models report temperature. Shelly Plug S (Gen1) reports internal temperature. Shelly Plus Plug S (Gen2) reports `temperature.tC`. Some models have no temperature sensor at all. Assuming all Shellys have temperature leads to KeyError or None propagation.

**Prevention:**
- Always use `.get()` with defaults: `data.get("temperature", {}).get("tC", 0.0)` for Gen2.
- For Gen1: temperature may be a top-level field `temperature` or absent. Default to 0.0.
- Never crash on missing fields. The OpenDTU plugin already follows this defensive pattern -- copy it.

### Pitfall 12: Multiple Switch Channels on Pro Devices

**What goes wrong:** Shelly Pro 4PM has 4 independent relay channels, each with its own power meter. Shelly Plus 2PM has 2 channels. If the plugin assumes `switch_id=0`, it only reads one channel.

**Prevention:**
- Store `switch_id` (default: 0) in InverterEntry config for Shelly devices.
- For multi-channel devices, each channel should be a separate device entry (one InverterEntry per channel, same host but different `switch_id`).
- MVP: support single-channel devices only (Plug S, 1PM). Document multi-channel as future enhancement. The add-device flow should detect channel count and warn if >1 channel is found.

### Pitfall 13: Shelly Discovery Collision with Existing Modbus Scanner

**What goes wrong:** The existing scanner probes ports 502/1502 for SunSpec Modbus. Shelly devices do not speak Modbus. Trying to unify Shelly HTTP discovery with Modbus scanning creates unnecessary complexity.

**Prevention:**
- Shelly discovery is a completely separate flow from the Modbus scanner. Do NOT try to merge them.
- The "Add Device" dialog should offer "Shelly" as a third option alongside SolarEdge/OpenDTU.
- Shelly add-flow: user enters IP -> proxy calls `GET /shelly` -> auto-detects generation -> shows device info (model, MAC, firmware) for confirmation -> saves to config.
- mDNS discovery (`_http._tcp` with `shelly*` hostname filter) is nice-to-have but NOT required for MVP. Manual IP entry is sufficient.

### Pitfall 14: Polling Interval Too Aggressive for Embedded Devices

**What goes wrong:** SolarEdge Modbus polls at 1-second intervals. Applying the same interval to Shelly HTTP API causes connection exhaustion on the embedded device (Gen1 devices have limited RAM/CPU) and excessive network traffic for minimal data freshness benefit.

**Prevention:**
- Default poll interval for Shelly: 5 seconds (matches OpenDTU default).
- Gen1 devices: consider 10 seconds to be safe. Gen2+ can handle 5 seconds.
- Use `aiohttp.ClientTimeout(total=8)` to avoid hanging connections on slow responses.
- Reuse the `aiohttp.ClientSession` across polls (already done in OpenDTU plugin -- follow the same pattern).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Plugin skeleton + profile pattern | Pitfall 1 (switch vs inverter), Pitfall 2 (Gen1/Gen2 API split) | Profile pattern from day one, `throttle_enabled=False` hardcoded, no-op `write_power_limit` |
| Generation detection | Pitfall 3 (unreliable detection), Pitfall 10 (non-PM models) | Use `/shelly` only, check for PM capability, persist result |
| Polling implementation | Pitfall 4 (no DC values), Pitfall 11 (missing fields), Pitfall 14 (poll interval) | SunSpec "not implemented" markers, defensive `.get()`, 5s interval |
| Energy tracking | Pitfall 5 (Watt-minute conversion, counter reset) | Immediate unit conversion at parse, offset tracking for resets |
| Aggregation integration | Pitfall 4 (DC averaging fix), Pitfall 8 (night mode) | Fix DC voltage averaging to exclude zero-DC devices, exclude Shelly from night mode |
| Switch control UI | Pitfall 9 (feedback lag) | Optimistic UI state with pending flag |
| Add-device flow | Pitfall 3 (detection), Pitfall 12 (multi-channel), Pitfall 13 (scanner collision) | Separate Shelly discovery, detect channel count, manual IP for MVP |
| Auth handling | Pitfall 6 (Basic vs Digest) | Check `auth_en` at detection, skip auth if disabled, defer Digest Auth to post-MVP |
| Firmware updates | Pitfall 7 (OTA reboot) | Rely on existing ConnectionManager backoff, no special handling |

## Sources

- [Shelly Gen1 API Documentation](https://shelly-api-docs.shelly.cloud/gen1/)
- [Shelly Gen2 API Documentation](https://shelly-api-docs.shelly.cloud/gen2/)
- [Shelly Gen2 Switch Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/)
- [Shelly Gen1/Gen2/Gen3/Gen4 Comparison](https://support.shelly.cloud/en/support/solutions/articles/103000316073-comparison-of-shelly-gen1-gen2-gen3-and-gen4-devices)
- [Shelly Negative Power / Measurement Direction](https://support.shelly.cloud/en/support/solutions/articles/103000316350-which-shelly-devices-can-measure-negative-power-for-returned-energy-)
- [Shelly Power Meter Accuracy Discussion](https://community.home-assistant.io/t/accuracy-of-shelly-devices/778134)
- [Shelly Gen1 vs Gen2 API Differences (Forum)](https://shelly-forum.com/thread/17721-difference-in-gen1-api-and-gen2/)
- [Shelly Troubleshooting Inaccurate Measurements](https://support.shelly.cloud/en/support/solutions/articles/103000359876-troubleshooting-inaccurate-measurements-on-shelly-em-3em-devices)
- Existing codebase: `plugin.py` (ABC), `plugins/opendtu.py` (REST plugin pattern), `aggregation.py` (DC averaging bug), `distributor.py` (waterfall + throttle_enabled), `config.py` (InverterEntry fields), `plugins/__init__.py` (plugin_factory)
