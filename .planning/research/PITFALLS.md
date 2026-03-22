# Domain Pitfalls: MQTT Data Publishing (v5.0)

**Domain:** Adding MQTT publishing to an existing asyncio Python proxy app
**Researched:** 2026-03-22
**Applies to:** v5.0 milestone (publishing inverter data to external MQTT broker mqtt-master.local, Home Assistant/Node-RED/Grafana integration)
**Overall confidence:** HIGH (pitfalls derived from codebase analysis + documented community issues)

---

## Critical Pitfalls

Mistakes that cause data loss, service crashes, or broken Venus OS integration.

### Pitfall 1: Raw Socket MQTT Client Cannot Support Two Concurrent Brokers

**What goes wrong:** The existing `venus_reader.py` implements MQTT using raw TCP sockets (`socket.socket`) with hand-rolled MQTT 3.1.1 packet encoding/decoding. This was adequate for a single subscribe-only connection to Venus OS, but it has no support for managing two independent broker connections (Venus OS for reading, mqtt-master.local for publishing). Attempting to extend this raw socket approach for publishing will create an unmaintainable mess: duplicate packet parsers, duplicate reconnection logic, duplicate keepalive timers.

**Why it happens:** The raw socket approach was a pragmatic v3.0 choice to avoid adding paho-mqtt as a dependency (it is NOT in pyproject.toml despite being mentioned in PROJECT.md). It works for the narrow Venus OS subscription use case. But publishing requires QoS handling, retained message support, proper CONNACK/PUBACK flows, and clean session management that the raw approach lacks.

**Consequences:**
- Publishing with QoS 1 (recommended for telemetry) requires PUBACK tracking -- the raw client has no message ID management
- Retained messages (critical for Home Assistant discovery) need the retain flag in PUBLISH packets -- possible but error-prone with raw bytes
- Two independent raw socket loops each doing `s.recv(8192)` with `asyncio.sleep(0.1)` doubles the blocking I/O burden on the event loop
- No Will message support (needed for availability topics)

**Prevention:**
- Use `aiomqtt` (the maintained asyncio wrapper around paho-mqtt) for the NEW publisher connection. It provides native async context managers, proper QoS, retain, and Will message support. Add `aiomqtt>=2.0,<3.0` to dependencies.
- Do NOT refactor the existing `venus_reader.py` raw socket client in this milestone. It works. Changing it risks breaking the Venus OS integration for zero user value. Refactoring it to aiomqtt can be a separate future milestone.
- The two MQTT connections are completely independent: different brokers, different purposes, different lifetimes. They should be separate modules (`venus_reader.py` stays as-is, new `mqtt_publisher.py` uses aiomqtt).

**Detection:** If you find yourself adding PUBACK parsing to `venus_reader.py` or trying to make one socket talk to two brokers, you are going down the wrong path.

**Phase:** First phase -- establish the publisher client as an independent module before adding any topic/payload logic.

---

### Pitfall 2: Blocking the asyncio Event Loop with MQTT Operations

**What goes wrong:** The existing `venus_reader.py` already has a subtle performance issue: it does blocking `s.recv(8192)` on a raw socket with a 1-second timeout, inside an `async def` that uses `await asyncio.sleep(0.1)` between reads. This means every read blocks the event loop for up to 1 second. Adding a second MQTT connection that also blocks will compound this, causing poll loop jitter, WebSocket broadcast delays, and Modbus server response latency.

**Why it happens:** The raw socket approach in venus_reader was designed before the app had WebSocket push, multi-device polling, and real-time power control. The 1-second timeout was acceptable when the event loop had fewer tasks. With v4.0's DeviceRegistry running N concurrent poll loops plus WebSocket broadcasts, event loop time is now precious.

**Consequences:**
- Poll loops for SolarEdge (1s interval) and OpenDTU (5s interval) may drift or miss cycles
- WebSocket broadcasts to dashboard clients arrive late, breaking the "real-time" feel
- Modbus server responses to Venus OS slow down, potentially triggering Venus OS timeout/disconnect
- Under load (many devices + frequent MQTT publishes), the system becomes sluggish

**Prevention:**
- Use `aiomqtt` for the publisher -- it uses paho-mqtt's loop with `add_reader()`/`add_writer()` registered on the asyncio event loop, so MQTT I/O is truly non-blocking.
- Never call `socket.recv()`, `socket.send()`, or any blocking I/O from an `async def` without `run_in_executor()`.
- The publisher should use `client.publish()` which is an awaitable -- it yields control back to the event loop while waiting for broker acknowledgment.

**Detection:** If Modbus response times to Venus OS increase after enabling MQTT publishing, or if dashboard WebSocket updates become jerky, the event loop is being blocked.

**Phase:** Core publisher implementation. The asyncio integration must be correct from the start.

---

### Pitfall 3: Publishing Inside the Poll Loop Hot Path

**What goes wrong:** The most natural place to add MQTT publishing is inside the existing poll success callback chain: `_device_poll_loop` -> `on_success` (AggregationLayer.recalculate) -> `broadcast_device_snapshot`. Adding `await mqtt_client.publish()` in this chain means a slow or disconnected MQTT broker blocks the entire poll-aggregate-broadcast pipeline. If mqtt-master.local is unreachable, ALL inverter polling stalls.

**Why it happens:** Developers naturally think "when data arrives, publish it." But the poll loop is latency-sensitive: SolarEdge expects 1-second poll cycles, and the aggregation -> WebSocket broadcast must complete within that window.

**Consequences:**
- MQTT broker offline = all inverter polling stops (cascading failure)
- MQTT publish with QoS 1 adds round-trip latency to every poll cycle
- Network glitch to mqtt-master.local causes Venus OS to see stale data (poll loop blocked waiting for MQTT timeout)
- Cannot independently control publish rate vs poll rate

**Prevention:**
- **Decouple publishing from polling using an asyncio.Queue.** The poll/aggregation pipeline pushes snapshots into a queue. A separate publisher task drains the queue and publishes at its own pace.
- The queue should have a bounded size (e.g., `maxsize=100`). If the publisher falls behind (broker offline), old messages are dropped -- stale telemetry has no value.
- Publisher reconnection and retry happen in the publisher task, completely invisible to the poll loop.
- This also allows configurable publish intervals: the publisher task can throttle (e.g., publish at most once per 5 seconds per device) by tracking last-publish timestamps.

**Detection:** If disabling MQTT publishing makes the dashboard noticeably more responsive, the coupling is too tight.

**Phase:** Core publisher architecture. The queue decoupling must be designed before any publish logic.

---

### Pitfall 4: Home Assistant MQTT Discovery Payload Mistakes

**What goes wrong:** Home Assistant MQTT Discovery requires precise JSON payloads published to `homeassistant/<component>/<node_id>/<object_id>/config` with specific required fields (`unique_id`, `device`, `state_topic`, `name`). Small mistakes cause silent failures: HA simply ignores malformed discovery messages with no error log. Common mistakes: missing `unique_id` (entities appear but cannot be customized), wrong `state_topic` (entity created but always "unavailable"), publishing discovery without `retain: true` (entities disappear on HA restart).

**Why it happens:** The HA MQTT Discovery protocol is documented but has many implicit requirements that only surface through trial and error. The protocol evolved over time and older blog posts show deprecated patterns.

**Consequences:**
- Entities appear in HA but show "unavailable" permanently (wrong state_topic)
- Entities disappear after HA restart (discovery messages not retained)
- Duplicate entities after proxy restart (non-stable unique_id)
- Device grouping broken (inconsistent `device.identifiers` across entities)

**Prevention:**
- Always publish discovery config messages with `retain=True`
- Use the inverter's persistent ID (from `InverterEntry.id`) as part of `unique_id` to ensure stability across restarts
- Group all entities under one HA device using consistent `device: { identifiers: ["pv_proxy_{device_id}"], name: "...", manufacturer: "...", model: "..." }`
- Use `json_attributes_topic` to publish the full snapshot as JSON attributes, with individual `state_topic` for the primary value (ac_power_w)
- Publish an `availability_topic` with LWT (Last Will and Testament) so HA shows the device as offline when the proxy dies
- Test discovery by subscribing to `homeassistant/#` on mqtt-master.local and verifying the JSON structure before writing HA integration code

**Detection:** Entities in HA show "unavailable" or disappear after restarts. Check with `mosquitto_sub -t "homeassistant/#" -v` to see what discovery payloads are actually arriving.

**Phase:** Home Assistant discovery phase -- after basic publishing works. This is a separate concern from raw data publishing.

---

## Moderate Pitfalls

### Pitfall 5: Topic Naming That Prevents Future Extensibility

**What goes wrong:** Choosing flat or inconsistent topic hierarchies like `pv-proxy/power` or `inverter1/ac_power_w` that cannot accommodate multiple devices, the virtual aggregated inverter, or future sensor types. Renaming topics after Home Assistant users have built dashboards and automations is extremely disruptive.

**Prevention:**
- Use a hierarchical, device-keyed structure from day one:
  ```
  pv-proxy/device/{device_id}/state          # Full JSON snapshot
  pv-proxy/device/{device_id}/power           # Just ac_power_w (for simple consumers)
  pv-proxy/virtual/state                      # Aggregated virtual inverter
  pv-proxy/status                             # Online/offline availability
  ```
- Use lowercase, hyphens for separators, no spaces, no special characters
- Include the proxy instance identifier in the root to support multiple proxy instances on the same broker
- Design topics BEFORE implementing -- changing them later breaks all downstream consumers

**Phase:** Topic design phase, before any publish code is written.

---

### Pitfall 6: Excessive Publish Rate Overwhelming the Broker or Consumers

**What goes wrong:** The proxy polls SolarEdge every 1 second and OpenDTU every 5 seconds. Naively publishing every poll result to MQTT means 1 message/second/device. With 3 devices, a virtual inverter, and per-field topics, this could be 50+ messages/second. Small brokers (Mosquitto on a Raspberry Pi) and consumers (Home Assistant on the same Pi) can struggle with this rate.

**Prevention:**
- Default publish interval should be 5-10 seconds, NOT matching the poll interval. Power data changes slowly -- publishing every second wastes bandwidth for negligible value.
- Make the interval configurable in the YAML config (`mqtt_publish.interval: 5`).
- Implement a **change-based publish optimization**: skip publishing if the snapshot hasn't materially changed (e.g., power within 10W, same status). This dramatically reduces message rate at night when inverters are sleeping.
- Use a single JSON payload per device rather than per-field topics. One `pv-proxy/device/{id}/state` message with the full snapshot is far more efficient than 20 individual topic publishes.
- QoS 0 for telemetry (fire-and-forget), QoS 1 only for discovery and availability messages.

**Phase:** Publisher implementation. Rate limiting must be built into the initial design, not bolted on later.

---

### Pitfall 7: mDNS Broker Discovery Race Condition on Startup

**What goes wrong:** The v5.0 requirements include "MQTT Broker Autodiscovery im LAN (mDNS)". If the proxy starts before the MQTT broker is up (common after power outage where everything reboots simultaneously), mDNS discovery fails, and the publisher gives up or enters an error state. Unlike the Venus OS MQTT reader (which has a clear "not configured" fallback), a publishing feature that silently fails is worse than one that never started.

**Prevention:**
- mDNS discovery should be a one-time configuration aid (like the existing inverter auto-scan), NOT a runtime dependency. Once the broker address is discovered/confirmed, save it to config.yaml.
- The publisher should use the configured broker address with robust reconnection (exponential backoff: 1s, 2s, 4s, 8s, max 60s).
- If mDNS discovery is used, implement a timeout (10s) with fallback to the default `mqtt-master.local` hostname. DNS resolution of `.local` hostnames via mDNS/Avahi is generally reliable on LAN without needing explicit mDNS service discovery.
- Log clearly when broker is unreachable: `mqtt_publisher_connecting`, `mqtt_publisher_connected`, `mqtt_publisher_disconnected` with structlog.

**Phase:** Broker configuration and autodiscovery phase.

---

### Pitfall 8: Payload Serialization Performance with Large Snapshots

**What goes wrong:** The dashboard snapshot dict (see `DashboardCollector.collect_from_raw`) contains nested dicts with 30+ fields including time series buffer references, override logs, and Venus OS state. Naively `json.dumps(snapshot)` on every publish cycle serializes data that MQTT consumers do not need (sparkline buffers, internal connection counters, override log history). Payloads grow to 2-5KB per device per publish, consuming unnecessary bandwidth and broker storage (retained messages).

**Prevention:**
- Create a dedicated `mqtt_payload(snapshot)` function that extracts ONLY the fields relevant for external consumers:
  - `ac_power_w`, `dc_power_w`, `ac_voltage_*`, `ac_current_*`, `ac_frequency_hz`
  - `energy_total_wh`, `daily_energy_wh`
  - `temperature_c`, `status`, `status_code`
  - `peak_power_w`, `operating_hours`
  - `connection.state`
- Exclude: `override_log`, `venus_os` internals, `control` internals (these are webapp-only concerns)
- Target payload size: 200-500 bytes per device. This is well within MQTT best practices.
- Use `json.dumps(payload, separators=(",", ":"))` for compact JSON (no whitespace).

**Phase:** Payload design phase, alongside topic design.

---

### Pitfall 9: No Graceful Shutdown for the Publisher

**What goes wrong:** The existing `__main__.py` has a clean shutdown sequence: cancel heartbeat, stop webapp, stop device registry, cancel Modbus server. If the MQTT publisher is added as another asyncio task but not included in this shutdown sequence, the process may hang (waiting for publisher reconnection timeout) or crash (task exception during shutdown). Worse: without sending an MQTT "offline" message before disconnecting, Home Assistant will show the device as "available" for up to the MQTT keepalive period (default 60s) after the proxy is actually down.

**Prevention:**
- Add the publisher task to the shutdown sequence in `run_with_shutdown()`, between webapp stop and device registry stop.
- On shutdown: publish `offline` to the availability topic BEFORE disconnecting.
- Use `aiomqtt`'s Will message (LWT) as a fallback: if the proxy crashes without graceful shutdown, the broker automatically publishes the offline message.
- Set a reasonable MQTT keepalive (30-60s) so stale "online" status resolves quickly after ungraceful shutdown.

**Phase:** Publisher lifecycle management, during core implementation.

---

### Pitfall 10: Config Hot-Reload Complexity for MQTT Publisher

**What goes wrong:** The existing Venus MQTT reader supports hot-reload: when the user changes venus config via the webapp, the old `venus_task` is cancelled and a new `venus_mqtt_loop` is started (see `webapp.py` config save handler). The MQTT publisher will need the same capability (user changes broker address, port, or publish interval via the webapp). But hot-reloading an MQTT connection is tricky: you must drain the publish queue, disconnect cleanly (sending offline status), then reconnect with new settings. If done wrong, you get duplicate connections or lost messages.

**Prevention:**
- Design the publisher with a `stop()` / `start()` lifecycle from the beginning.
- Hot-reload sequence: `publisher.stop()` (drains queue, publishes offline, disconnects) -> update config -> `publisher.start()` (connects with new settings, publishes online, sends discovery).
- The publish queue should be part of the publisher object, not a global. When the publisher restarts, it gets a fresh queue.
- Cancel the old publisher task and await it (catching CancelledError) before starting a new one, exactly like the Venus task pattern.

**Phase:** Config UI integration phase.

---

## Minor Pitfalls

### Pitfall 11: Client ID Collisions Between Venus Reader and Publisher

**What goes wrong:** If both MQTT connections happen to use the same client ID (e.g., both defaulting to `pv-proxy`), and they ever connect to the same broker (unlikely but possible if Venus OS and mqtt-master.local are the same machine), the broker will disconnect the first client when the second connects. MQTT brokers enforce unique client IDs.

**Prevention:**
- Venus reader uses `pv-proxy-venus-sub` (already uses `pv-proxy-sub`)
- Publisher uses `pv-proxy-pub-{short_hash}` where short_hash is derived from the machine's hostname or a stable config identifier
- Never use random client IDs -- they prevent the broker from associating sessions across reconnects (QoS 1 message redelivery relies on persistent sessions keyed by client ID)

---

### Pitfall 12: Timezone and Timestamp Format Inconsistency

**What goes wrong:** The dashboard snapshot uses `time.time()` (Unix epoch float). MQTT consumers like Home Assistant expect ISO 8601 timestamps or Unix epoch integers. If the proxy publishes `"ts": 1711100000.123456` but an HA template expects `"ts": "2026-03-22T10:00:00Z"`, the entity shows incorrect values or errors.

**Prevention:**
- Publish timestamps as Unix epoch integers (seconds) in the MQTT payload. This is the most universal format.
- Include an ISO 8601 string as a secondary field if needed: `"ts_iso": "2026-03-22T10:00:00+01:00"`.
- Document the timestamp format in a README or in the MQTT discovery payload's `value_template`.

---

### Pitfall 13: Testing MQTT Publishing Without a Real Broker

**What goes wrong:** The existing test suite (7,400 LOC) uses no MQTT broker mocks. Adding MQTT publisher tests that require a running Mosquitto instance makes the CI fragile and slow. Tests that skip when no broker is available provide no coverage.

**Prevention:**
- Use `unittest.mock.AsyncMock` to mock the aiomqtt client for unit tests.
- Test the payload serialization, topic generation, and queue logic independently of MQTT transport.
- For integration testing, use a minimal in-process mock or pytest fixture that verifies publish calls without a real broker.
- The queue-based decoupling (Pitfall 3) makes testing easier: you can test the queue producer (poll loop integration) and queue consumer (publisher) independently.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Publisher client setup | Pitfall 1 (raw socket reuse), Pitfall 2 (blocking IO) | Use aiomqtt, separate module |
| Publisher architecture | Pitfall 3 (poll loop coupling) | asyncio.Queue decoupling |
| Topic + payload design | Pitfall 5 (naming), Pitfall 8 (payload bloat) | Design topics before coding, extract minimal payload |
| Publish rate control | Pitfall 6 (excessive rate) | Configurable interval, change-based optimization |
| Home Assistant discovery | Pitfall 4 (discovery mistakes) | Retain flag, stable unique_id, LWT |
| Broker autodiscovery | Pitfall 7 (mDNS race) | Config aid not runtime dependency, fallback to hostname |
| Lifecycle management | Pitfall 9 (shutdown), Pitfall 10 (hot-reload) | Explicit stop/start, LWT, drain queue |
| Config UI | Pitfall 10 (hot-reload) | Follow Venus task cancel pattern |
| Testing | Pitfall 13 (no broker in CI) | Mock aiomqtt client, test queue logic separately |

## Sources

- Codebase analysis: `venus_reader.py` (raw socket MQTT), `__main__.py` (task lifecycle), `dashboard.py` (snapshot structure), `config.py` (dataclass config), `device_registry.py` (poll loop pattern), `context.py` (AppContext), `pyproject.toml` (no paho-mqtt dependency)
- [paho-mqtt thread safety issue #358](https://github.com/eclipse-paho/paho.mqtt.python/issues/358)
- [aiomqtt - the idiomatic asyncio MQTT client](https://github.com/empicano/aiomqtt)
- [Python MQTT Clients: A 2025 Selection Guide (EMQ)](https://www.emqx.com/en/blog/comparision-of-python-mqtt-client)
- [MQTT Topics Best Practices (HiveMQ)](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/)
- [MQTT Broker Message Restrictions](http://www.steves-internet-guide.com/mqtt-broker-message-restrictions/)
- [Mosquitto configuration (message_size_limit, max_queued_messages)](https://mosquitto.org/man/mosquitto-conf-5.html)
- [MQTT Topic Naming Convention (Tinkerman)](https://tinkerman.cat/post/mqtt-topic-naming-convention)
