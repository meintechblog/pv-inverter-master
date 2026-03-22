# Project Research Summary

**Project:** PV Inverter Proxy — MQTT Data Publishing (v5.0)
**Domain:** Async Python MQTT publishing, Home Assistant integration, mDNS broker discovery
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

The v5.0 milestone adds outbound MQTT publishing to an existing, production-grade asyncio proxy that already reads from SolarEdge and OpenDTU inverters, aggregates data, and exposes it via WebSocket and Modbus. The core challenge is not MQTT itself — that protocol is simple — but correctly integrating a new I/O-bound subsystem into a latency-sensitive poll loop without disrupting Venus OS Modbus communication or WebSocket dashboard updates. Research is unambiguous: use `aiomqtt` (native asyncio, wraps paho-mqtt) for the publisher, leave the existing hand-rolled Venus OS MQTT subscriber (`venus_reader.py`) untouched, and decouple publishing from the poll chain via an `asyncio.Queue`.

The recommended implementation has two new Python modules (`mqtt_publisher.py` and `mdns_discovery.py`), one shared refactored module (`mqtt_protocol.py` extracted from `venus_reader.py`), and targeted modifications to `config.py`, `context.py`, `__main__.py`, `webapp.py`, and the frontend. The single most valuable differentiator — Home Assistant MQTT Auto-Discovery — should be built into the initial architecture (retained config payloads with `unique_id`, `device`, availability topics, and correct `state_class`/`device_class` values) rather than bolted on later, because HA discovery payloads are structural and touch every published entity.

The main risk is event loop blocking: any synchronous I/O (DNS resolution, socket send without executor) in an `async def` will cause poll loop jitter and stale Modbus data to Venus OS. The architecture must enforce non-blocking MQTT I/O from the start. A secondary risk is Home Assistant discovery payload correctness — HA silently ignores malformed discovery messages, so testing requires `mosquitto_sub -t "homeassistant/#"` verification before claiming HA integration is complete.

## Key Findings

### Recommended Stack

The existing codebase has zero external MQTT dependencies; `venus_reader.py` implements a hand-rolled MQTT 3.1.1 client over raw sockets. This is adequate for the Venus OS subscriber (read-only, single broker, QoS 0) but inadequate for a publisher that needs QoS 1, LWT (Last Will and Testament), retain flags, and reconnect with session persistence. Adding those capabilities to the raw socket client would recreate paho-mqtt poorly.

Two new dependencies are warranted. `aiomqtt>=2.3,<3.0` provides a native asyncio MQTT client (async context manager, `await client.publish()`, built-in reconnect, LWT) built on battle-tested paho-mqtt. `zeroconf>=0.140,<1.0` provides `AsyncZeroconf`/`AsyncServiceBrowser` for discovering `_mqtt._tcp.local.` services without subprocess calls. Both are actively maintained, used by Home Assistant, and compatible with the project's Python 3.12 + asyncio architecture. No other new dependencies are needed: JSON serialization uses stdlib `json`, scheduling uses `asyncio.sleep`, topic strings use f-strings, and config uses the established dataclass pattern.

Note: ARCHITECTURE.md recommends staying with raw sockets for the publisher (consistent with `venus_reader.py`), while STACK.md and PITFALLS.md both recommend `aiomqtt`. The pitfalls analysis is decisive here — raw sockets lack QoS 1 PUBACK tracking, LWT support, and proper reconnect, and extending the hand-rolled client duplicates paho-mqtt poorly. **Use aiomqtt.**

**Core technologies:**
- `aiomqtt>=2.3,<3.0`: Async MQTT publisher — native asyncio, no threading, QoS 0/1, LWT, auto-reconnect; v2.4.0 released May 2025, actively maintained.
- `zeroconf>=0.140,<1.0`: mDNS broker autodiscovery — `AsyncServiceBrowser` for `_mqtt._tcp.local.`; v0.148.0 released Oct 2025, used by Home Assistant.
- stdlib `json`, `asyncio`, `dataclasses`: No new dependencies for config, serialization, or scheduling.

### Expected Features

The MQTT publishing ecosystem (SolarAssistant, deye-inverter-mqtt, growatt2mqtt) sets clear user expectations. Per-device JSON topics, configurable broker, configurable publish interval, an availability topic, and a status indicator in the webapp are all table stakes. Home Assistant MQTT Auto-Discovery is the high-value differentiator that turns this from "another MQTT publisher" into "zero-config HA integration."

**Must have (table stakes):**
- Per-device MQTT topics with JSON payloads (physical units from DashboardCollector snapshots)
- Virtual aggregated device topic (mirrors the existing virtual PV plant in the proxy)
- Configurable broker host/port, topic prefix, publish interval (default 5s)
- Availability topic with LWT (`pv-proxy/status` online/offline, `retain=True`)
- Enable/disable toggle — opt-in, not forced on existing deployments
- Broker connection status dot in webapp (reuse `ve-dot` component)

**Should have (differentiators):**
- Home Assistant MQTT Auto-Discovery with correct `device_class`, `state_class`, `unique_id`, `device` grouping, and Energy Dashboard-ready sensors (`total_increasing` for energy)
- mDNS broker autodiscovery (`_mqtt._tcp.local.`) as a first-setup UX aid, falling back to manual hostname entry
- Per-device availability topics alongside the global availability topic

**Defer (v2+):**
- Publish-on-change with max-staleness interval (good optimization, adds snapshot diff complexity)
- Per-device publish enable/disable (all enabled devices publish in v5.0)
- TLS/authentication (explicitly out of scope: same-LAN, no internet exposure per PROJECT.md)
- Historical data replay (MQTT is real-time; history is the consumer's job)
- QoS 2 (exactly-once delivery): massive overhead for telemetry that refreshes every few seconds

### Architecture Approach

The MQTT publisher integrates at the `_on_aggregation_broadcast` callback — the same point where WebSocket broadcasts originate — rather than inside the poll loop or as an independent timer. This gives it access to already-decoded snapshot dicts, correct timing (fires after aggregation, not mid-poll), and both per-device and virtual data. Publishing is decoupled from the broadcast chain via an `asyncio.Queue` (bounded, `maxsize=100`) so that a slow or unreachable broker never stalls the poll pipeline. A separate asyncio Task drains the queue and manages the aiomqtt connection lifecycle independently.

**Major components:**
1. `mqtt_protocol.py` (NEW, refactored from `venus_reader.py`) — shared raw MQTT socket helpers; eliminates duplication and gives venus_reader.py a stable foundation to import from
2. `mqtt_publisher.py` (NEW) — `MqttPublisher` class using aiomqtt: connection lifecycle, `asyncio.Queue` drain loop, payload formatting, rate limiting via per-device timestamp gating, HA discovery emission on connect
3. `mdns_discovery.py` (NEW, optional) — `AsyncZeroconf`-based `_mqtt._tcp.local.` browser; invoked as a one-time config aid, not a runtime dependency
4. `MqttPublishConfig` dataclass in `config.py` (MODIFIED) — `enabled`, `host`, `port`, `topic_prefix`, `interval`, `client_id`, `autodiscovery`, `qos`
5. `__main__.py` (MODIFIED) — wire publisher lifecycle (start/stop alongside Venus task), extend `_on_aggregation_broadcast` to push snapshots to queue
6. `webapp.py` + frontend (MODIFIED) — config panel (broker, port, interval, enable), connection status dot, hot-reload on config save

**Topic hierarchy (finalize before writing any publish code):**
```
pv-proxy/status                              -> "online" / "offline" (LWT, retain=True)
pv-proxy/device/{device_id}/state            -> JSON telemetry payload (no retain)
pv-proxy/device/{device_id}/availability     -> "online" / "offline"
pv-proxy/virtual/state                       -> aggregated virtual inverter JSON
pv-proxy/virtual/availability                -> "online" / "offline"
homeassistant/sensor/{node_id}/{object_id}/config  -> HA discovery (retain=True)
```

### Critical Pitfalls

1. **Extending the raw socket client for publishing** — The hand-rolled MQTT in `venus_reader.py` lacks QoS 1 PUBACK tracking, retain flag support, and LWT. Extending it creates duplicated, unmaintainable code. Use `aiomqtt` for the publisher as a completely independent module; do not refactor `venus_reader.py` in this milestone.

2. **Publishing synchronously in the poll-loop broadcast chain** — Adding `await mqtt_client.publish()` directly in `_on_aggregation_broadcast` means a slow or unreachable broker stalls all inverter polling. Decouple via `asyncio.Queue`: broadcast chain pushes to queue, publisher task drains independently.

3. **Blocking the event loop with DNS or socket I/O** — `socket.getaddrinfo("mqtt-master.local", 1883)` can take 2-5 seconds and blocks the entire event loop. Use `loop.run_in_executor()` for DNS resolution, or resolve once at startup. `aiomqtt` handles MQTT socket I/O non-blocking by design.

4. **Home Assistant discovery payload mistakes** — HA silently ignores malformed discovery messages. Required: `unique_id` (stable, based on `InverterEntry.id`), `device` block with consistent `identifiers`, `state_topic` matching actual publish topic, `retain=True` on all config payloads. Wrong `state_class` silently breaks Energy Dashboard. Test with `mosquitto_sub -t "homeassistant/#"` before claiming HA integration works.

5. **No graceful shutdown for the publisher** — Without explicit inclusion in `run_with_shutdown()`, the publisher task may hang or skip sending the "offline" availability message. Publish `offline` before disconnecting on shutdown; use LWT as crash fallback. Cancel and `await` the publisher task in the shutdown sequence before stopping the device registry.

## Implications for Roadmap

Based on combined research, the natural build order respects two hard dependency chains: (a) shared MQTT primitives and publisher infrastructure must exist before any publish or discovery logic, and (b) the topic/payload schema and HA discovery format must be finalized before any live publish calls are written, because renaming topics after consumers exist is extremely disruptive. The queue-based decoupling architecture must also be in place before wiring live data flow.

### Phase 1: MQTT Protocol Extraction + Dependency Addition

**Rationale:** Zero-risk refactor that creates the shared foundation. Must happen first because both `venus_reader.py` and `mqtt_publisher.py` will import from `mqtt_protocol.py`. Adding `aiomqtt` and `zeroconf` to `pyproject.toml` here allows all subsequent phases to use them without revisiting packaging.
**Delivers:** `mqtt_protocol.py` with extracted MQTT helpers (`_mqtt_connect`, `_mqtt_publish`, `_mqtt_subscribe`, `_parse_mqtt_messages`); `aiomqtt` and `zeroconf` in `pyproject.toml`; `venus_reader.py` updated to import from shared module; existing Venus OS integration unchanged and passing.
**Addresses:** Pitfall 1 (raw socket duplication), Pitfall 2 (blocking I/O — aiomqtt selected here).
**Avoids:** Any change to Venus OS subscriber behavior.

### Phase 2: Config + MqttPublisher Core (Queue Architecture)

**Rationale:** Establishes the `MqttPublishConfig` dataclass and the core `MqttPublisher` class with queue-based decoupling before any topic, payload, or HA discovery logic. This phase is about architectural correctness, not features. Getting the queue and lifecycle right here prevents all Pitfall 3 variants.
**Delivers:** `MqttPublishConfig` dataclass in `config.py`; `mqtt_publisher.py` with aiomqtt connection lifecycle (LWT, reconnect, clean session), bounded `asyncio.Queue(maxsize=100)`, drain loop, rate limiting via per-device timestamp gating, `stop()`/`start()` lifecycle for hot-reload; `context.py` updated with `mqtt_publisher` field; `__main__.py` shutdown sequence extended.
**Uses:** `aiomqtt`, `MqttPublishConfig`, established asyncio Task pattern from existing `__main__.py`.
**Avoids:** Pitfall 3 (poll loop coupling — queue decouples completely), Pitfall 9 (graceful shutdown — `stop()` publishes offline, drains queue, disconnects), Pitfall 11 (client ID collision — `pv-proxy-pub-{stable_hash}` not `pv-proxy`).

### Phase 3: Topic Structure + Payload Design + HA Discovery

**Rationale:** Topic hierarchy and telemetry payload schema must be locked in before any live publish call is written. HA auto-discovery payloads belong in this same phase because they directly reference the topic names and use the same `state_class`/`device_class` values — retrofitting HA discovery onto the wrong topic structure requires renaming published topics, breaking all existing consumers.
**Delivers:** Finalized topic hierarchy (see architecture above); `mqtt_payload()` function extracting ~15-18 fields from DashboardCollector snapshot (target 200-500 bytes, compact JSON via `separators=(",", ":")`); HA discovery config payloads for all 16 sensor entities (power, voltage, current, energy, temperature, status, efficiency, operating hours) with correct `unique_id`, `device` block, `state_class`, `device_class`, `availability_mode: all`; discovery published with `retain=True` on connect; `default_entity_id` used (not deprecated `object_id` — HA 2026.4).
**Addresses:** Table stakes (per-device topics, JSON payloads, virtual device, availability), differentiator (HA auto-discovery, Energy Dashboard-ready sensors).
**Avoids:** Pitfall 4 (HA discovery mistakes — retain, stable unique_id, correct state_class), Pitfall 5 (topic naming — hierarchical, device-keyed, designed before coding), Pitfall 8 (payload bloat — explicit field whitelist, excludes override_log and Venus internals).

### Phase 4: Wire into Broadcast Chain + Lifecycle

**Rationale:** Connect the fully designed publisher to live data only after the architecture is correct and the schema is finalized. This is the first phase where inverter data actually flows to the MQTT broker.
**Delivers:** `_on_aggregation_broadcast` extended to push device and virtual snapshots to publisher queue; live MQTT publishing from real inverter data; graceful shutdown sequence (publishes offline, drains queue, disconnects); config hot-reload (cancel old publisher task, start new one — follows Venus task pattern in `webapp.py`); publish rate enforced at configurable interval (default 5s per device).
**Implements:** Broadcast chain wiring, publisher task lifecycle in `__main__.py`.
**Avoids:** Pitfall 6 (excessive publish rate — configurable interval, per-device timestamp gating), Pitfall 9 (shutdown — drain-then-offline sequence), Pitfall 10 (hot-reload — explicit stop/start, fresh queue on restart).

### Phase 5: mDNS Broker Autodiscovery

**Rationale:** mDNS discovery is a first-setup UX aid, not a runtime dependency. Implementing it after core publishing is working means a broken discovery mechanism never blocks data flow. Start with `socket.getaddrinfo()` via `run_in_executor` (zero new code, covers `.local` hostnames), then add `zeroconf` browser for "scan for brokers" button if needed.
**Delivers:** `mdns_discovery.py` with `AsyncZeroconf` browse for `_mqtt._tcp.local.` (10-second timeout); one-time discovery flow (save result to config, fallback to manual entry); `getaddrinfo` via executor for hostname resolution at startup.
**Addresses:** Differentiator (mDNS autodiscovery).
**Avoids:** Pitfall 7 (mDNS race — discovery is config-time only, result persisted to YAML; runtime uses configured host with exponential-backoff reconnect), Pitfall 2 (blocking DNS — executor-wrapped getaddrinfo).

### Phase 6: Webapp Config UI + Dashboard Status

**Rationale:** User-facing surface comes after the backend is fully functional so the UI reflects real behavior. Follows established config panel and `ve-dot` design system patterns exactly — no new component patterns needed.
**Delivers:** Config panel section for MQTT Publishing (broker host, port, topic prefix, interval, enable toggle, mDNS discover button); connection status `ve-dot` on dashboard (reuse existing pattern); dirty tracking + Save/Cancel buttons (existing `ve-input--dirty` pattern); REST API endpoints in `webapp.py` for config read/write and publisher connection status.
**Uses:** Existing `ve-dot`, `ve-btn`, `ve-panel`, `ve-form-group`, `ve-input--dirty` design system components.
**Addresses:** Table stakes (enable/disable toggle, broker status indicator, configurable broker connection).

### Phase Ordering Rationale

- Phases 1-2 are pure infrastructure: shared protocol module, aiomqtt dependency, and core publisher class. No behavior visible to users, no risk to existing Venus OS or WebSocket functionality.
- Phase 3 locks in the schema before any live publishing — prevents the disruptive mistake of renaming topics after HA dashboards and automations depend on them.
- Phase 4 activates live data flow only after architecture is correct and schema is finalized.
- Phase 5 (mDNS) is independent of Phases 3-4 and can be parallelized if needed, but comes after core publishing to avoid blocking on optional UX.
- Phase 6 (UI) is last because it depends on having real backend state to reflect.
- This ordering means the event loop is never put at risk: queue decoupling and aiomqtt non-blocking I/O are both in place before a single MQTT message is sent.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (HA Discovery):** HA discovery schema changes with each HA release. Verify current required fields against HA 2026.x documentation before implementation. The `default_entity_id` vs `object_id` deprecation (HA 2026.4) noted in research is MEDIUM confidence and needs confirmation against the specific HA version deployed.
- **Phase 5 (mDNS):** Whether `mqtt-master.local` advertises `_mqtt._tcp.local.` via Avahi depends on the broker host's Avahi/mDNS configuration. Mosquitto does NOT do this by default (requires a separate Avahi service file). Verify before building the scan UI — if the broker does not advertise, `getaddrinfo` is the only viable approach and the scan button should be omitted.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Protocol Extraction):** Pure Python refactor of existing code; well-understood.
- **Phase 2 (Config + Core):** Follows the established `VenusConfig` dataclass pattern exactly; asyncio Task lifecycle follows `venus_mqtt_loop` pattern.
- **Phase 4 (Wiring + Lifecycle):** Follows the Venus task cancel/restart pattern already present in `webapp.py`.
- **Phase 6 (Config UI):** Follows existing config panel pattern with established design system components; no new component archetypes needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | aiomqtt and zeroconf are version-pinned, actively maintained, well-documented. Codebase analysis confirmed no existing paho-mqtt dependency. Raw-socket vs aiomqtt debate resolved by pitfalls analysis. |
| Features | HIGH | HA MQTT discovery format verified against official docs. Table stakes derived from multiple real-world solar MQTT projects. HA 2026.4 `default_entity_id` change is MEDIUM confidence — confirm against target HA version. |
| Architecture | HIGH | Based on direct codebase analysis (`venus_reader.py`, `__main__.py`, `aggregation.py`, `config.py`, `context.py`). Integration points identified precisely. Queue-based decoupling is the only correct architecture given the poll loop timing requirements. |
| Pitfalls | HIGH | Pitfalls 1-3 derived from direct codebase analysis with specific code paths cited. Pitfall 4 from HA community reports and official docs. All pitfalls have specific, actionable prevention strategies. |

**Overall confidence:** HIGH

### Gaps to Address

- **HA `default_entity_id` vs `object_id`:** Research flagged this as MEDIUM confidence. Confirm the exact HA version in the target deployment and whether `object_id` is still accepted or whether the migration is immediately required.
- **Avahi/mDNS on `mqtt-master.local`:** Whether the target broker advertises `_mqtt._tcp.local.` is unknown. If it does not (Mosquitto default), the zeroconf browser finds nothing and `getaddrinfo` is sufficient. Verify before building the scan UI in Phase 5.
- **DashboardCollector snapshot field names:** The payload design in Phase 3 depends on the exact field names produced by `DashboardCollector.collect_from_raw()`. Confirm field names match the telemetry payload schema in FEATURES.md before writing `mqtt_payload()` — field names may differ between SolarEdge and OpenDTU collectors.
- **Client ID stability:** PITFALLS recommends `pv-proxy-pub-{short_hash}` derived from hostname. Confirm the LXC hostname is stable across reboots, or use a config-persisted UUID instead to guarantee stable client ID for QoS 1 session persistence.
- **ARCHITECTURE.md vs STACK.md/PITFALLS.md conflict on raw sockets:** ARCHITECTURE.md recommends staying with raw sockets for the publisher for consistency with `venus_reader.py`. STACK.md and PITFALLS.md both recommend aiomqtt. Resolution: use aiomqtt. The raw socket approach cannot support QoS 1 PUBACK, LWT, or clean reconnect without reimplementing paho-mqtt.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `venus_reader.py`, `__main__.py`, `aggregation.py`, `config.py`, `context.py`, `pyproject.toml`, `dashboard.py` — direct source of truth for integration points and existing patterns
- [aiomqtt GitHub (empicano)](https://github.com/empicano/aiomqtt) — v2.4.0 May 2025; API design, LWT/QoS/reconnect capabilities
- [python-zeroconf GitHub](https://github.com/python-zeroconf/python-zeroconf) — v0.148.0 Oct 2025; AsyncZeroconf API
- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/) — discovery topic format, device grouping, origin field
- [Home Assistant MQTT Sensor](https://www.home-assistant.io/integrations/sensor.mqtt/) — device_class, state_class, value_template

### Secondary (MEDIUM confidence)
- [SolarAssistant MQTT](https://solar-assistant.io/help/integration/mqtt) — topic structure patterns for solar monitoring
- [deye-inverter-mqtt](https://github.com/kbialek/deye-inverter-mqtt) — publish intervals, publish-on-change, availability topics
- [EMQ Python MQTT Clients Guide 2025](https://www.emqx.com/en/blog/comparision-of-python-mqtt-client) — comparison of Python MQTT clients
- [HiveMQ MQTT Topic Best Practices](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/) — topic naming conventions
- [HA 2026.4 discovery deprecation](https://github.com/jomjol/AI-on-the-edge-device/issues/3932) — `object_id` to `default_entity_id` migration
- [HA Community: MQTT discovery + JSON](https://community.home-assistant.io/t/mqtt-auto-discovery-and-json-payload/409459) — JSON payload patterns
- [HA Community: Huawei Solar MQTT](https://community.home-assistant.io/t/app-huabus-huawei-solar-modbus-to-mqtt-sun2-3-5-000-mqtt-home-assistant-auto-discovery/958230) — real-world 68-entity solar HA discovery as pattern reference

### Tertiary (LOW confidence)
- [growatt2mqtt](https://github.com/nygma2004/growatt2mqtt) — 4s publish interval reference only
- [Home Assistant mDNS MQTT community discussion](https://community.home-assistant.io/t/mosquitto-broker-announcing-advertising-mqtt-service-via-mdns/343190) — `_mqtt._tcp` service type for Mosquitto Avahi configuration

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
