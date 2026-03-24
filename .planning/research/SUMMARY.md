# Research Summary: Shelly Plugin Integration (v6.0)

**Domain:** Shelly smart device integration as third InverterPlugin
**Researched:** 2026-03-24
**Overall confidence:** HIGH

## Executive Summary

Shelly devices expose a straightforward local HTTP/JSON API for reading power data and controlling relays. The API varies by generation: Gen1 uses simple REST endpoints (`/status`, `/relay/0`), while Gen2 and Gen3 use JSON-RPC 2.0 over HTTP (`/rpc/Switch.GetStatus`, `/rpc/Switch.Set`). Critically, Gen3 uses the exact same API as Gen2 -- there is no Gen3-specific protocol. All generations share a common `/shelly` endpoint for device identification, which returns a `gen` field (Gen2+) or omits it (Gen1), providing a clean auto-detection mechanism.

No new Python dependencies are needed. The existing `aiohttp` client used by the OpenDTU plugin handles all Shelly HTTP communication. The `aioshelly` library (Home Assistant's Shelly client) was evaluated and rejected -- it pulls in CoAP, Bluetooth, and WebSocket dependencies we do not need for simple HTTP polling. The Shelly plugin follows the same pattern as OpenDTU: `aiohttp.ClientSession` GET requests, JSON response parsing, SunSpec register encoding.

The key architectural decision is a profile-based abstraction: a dict maps generation strings ("gen1", "gen2") to endpoint URLs and field extraction functions. The ShellyPlugin auto-detects the generation on first connect via `/shelly`, selects the appropriate profile, and persists the detected generation to config. This avoids a class hierarchy while cleanly separating the Gen1/Gen2 API differences.

Shelly devices do not support percentage-based power limiting (unlike SolarEdge Modbus or OpenDTU API). They only support on/off switching. The `write_power_limit()` ABC method will be a no-op returning success, and a new `send_switch_command(on: bool)` method provides relay control via the webapp -- same pattern as OpenDTU's `send_power_command()`.

## Key Findings

**Stack:** Zero new dependencies -- reuse existing `aiohttp` for all Shelly HTTP communication.
**Architecture:** Profile-based Gen1/Gen2 abstraction with auto-detection via `/shelly` endpoint.
**Critical pitfall:** Gen1 `/status` response structure varies by device model (meters vs emeters, temperature presence) -- must handle missing fields gracefully.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **ShellyPlugin core + profiles** - Implement plugin with gen1/gen2 profiles, auto-detection, polling, SunSpec encoding
   - Addresses: Polling for power/voltage/current/energy/temperature
   - Avoids: Over-engineering (no class hierarchy, dict profiles suffice)

2. **Switch control + config** - Add on/off relay control, extend InverterEntry with `shelly_gen` field, wire into plugin_factory
   - Addresses: Switch-Steuerung On/Off, config persistence
   - Avoids: Trying to implement power limiting (Shelly does not support it)

3. **Add-device flow** - Shelly as third option in add-device UI, auto-detection of generation on IP entry
   - Addresses: Add-Device Flow, auto-detection requirement
   - Avoids: mDNS discovery scope creep (manual IP entry first)

4. **Device dashboard** - Gauge, AC values, connection card with on/off toggle (not power slider)
   - Addresses: Device-Dashboard with on/off toggle
   - Avoids: Replicating power control slider (irrelevant for Shelly)

5. **Aggregation integration** - Shelly data flows into virtual PV inverter
   - Addresses: Aggregation requirement
   - Avoids: Should be mostly automatic if SunSpec encoding is correct

**Phase ordering rationale:**
- Plugin core must exist before any UI or aggregation work
- Switch control is tightly coupled to the plugin (same HTTP session)
- Add-device flow needs the plugin factory wired first
- Dashboard needs working poll data to display
- Aggregation is the final validation that everything works end-to-end

**Research flags for phases:**
- Phase 1: Standard pattern (mirrors OpenDTU plugin), unlikely to need research
- Phase 3: May need research on how to validate a Shelly device (is it reachable? is it the right type?)
- Phase 4: Standard pattern (follow existing device dashboard), unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new deps. aiohttp is proven by OpenDTU. Verified against official Shelly docs + evcc implementation. |
| Features | HIGH | Shelly API well-documented. On/off is the only control. Power data fields verified. |
| Architecture | HIGH | Profile pattern proven by evcc (Go). InverterPlugin ABC fits naturally. |
| Pitfalls | HIGH | Gen1/Gen2 differences well-understood. Missing field handling is the main risk. |

## Gaps to Address

- Exact Shelly device models the user has (Plug S? 1PM? Plus 1PM?) -- affects which fields are available
- Whether auth is enabled on the user's Shelly devices (research assumes no auth per PROJECT.md)
- Temperature field availability varies by model -- must handle gracefully with defaults
- Gen1 `meters[0].total` unit may be Watt-minutes on some firmware versions (most report Wh) -- verify against actual device

## Sources

- [Shelly Gen1 API Reference](https://shelly-api-docs.shelly.cloud/gen1/) -- HIGH confidence
- [Shelly Gen2 API Reference](https://shelly-api-docs.shelly.cloud/gen2/) -- HIGH confidence
- [Shelly Gen2 Switch Component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/) -- HIGH confidence
- [Shelly Gen2 Shelly.GetDeviceInfo](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Shelly/) -- HIGH confidence
- [evcc Shelly meter (Go)](https://pkg.go.dev/github.com/evcc-io/evcc/meter/shelly) -- HIGH confidence

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
