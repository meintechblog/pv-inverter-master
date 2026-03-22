# Architecture: MQTT Data Publishing Integration

**Domain:** MQTT publishing for PV inverter proxy
**Researched:** 2026-03-22
**Confidence:** HIGH (based on thorough codebase analysis)

## Current Architecture Summary

The existing data flow is:

```
[Inverter Hardware]
       |
       v  (Modbus TCP / REST poll)
[DeviceRegistry._device_poll_loop]  -- per-device asyncio Task
       |
       |  plugin.poll() -> PollResult
       |  device_state.collector.collect_from_raw()  -> snapshot dict
       |  on_success(device_id) callback
       |
       v
[AggregationLayer.recalculate]
       |
       |  Reads all device_state.last_poll_data
       |  Sums/averages into RegisterCache (for Venus OS Modbus reads)
       |  Calls _broadcast_fn(device_id)
       |
       v
[_on_aggregation_broadcast]
       |
       |  broadcast_device_snapshot(app, device_id, snapshot)
       |  broadcast_virtual_snapshot(app)
       |
       v
[WebSocket clients]  -- browser dashboards
```

Key architectural facts:
- **No paho-mqtt dependency.** The existing venus_reader.py uses raw socket MQTT (hand-rolled CONNECT/SUBSCRIBE/PUBLISH packets). This is intentional -- zero unnecessary dependencies.
- **Per-device DashboardCollector** produces structured snapshot dicts with decoded physical values (watts, volts, amps, temperature, energy, status).
- **AggregationLayer** is the natural "data changed" event point -- it fires after every successful device poll.
- **AppContext** is the central state holder, passed everywhere.
- **Config dataclass pattern** is well-established (VenusConfig, ProxyConfig, etc.).

## Recommended Architecture: MQTT Publisher

### Integration Point: Hook into AggregationLayer broadcast

The MQTT publisher should hook into the same callback chain as WebSocket broadcast. The AggregationLayer already has a `_broadcast_fn` that fires after every aggregation. This is the correct integration point because:

1. **Data is already decoded** -- DashboardCollector snapshots contain physical values, no register decoding needed.
2. **Timing is right** -- fires once per device poll success, after aggregation, same cadence as WebSocket.
3. **Both per-device and virtual data available** -- can publish individual device snapshots AND aggregated totals.

**Do NOT hook into the poll loop directly.** The poll loop is per-device and low-level. The aggregation callback already has the unified view.

### New Component: MqttPublisher

```
[AggregationLayer.recalculate]
       |
       v  _broadcast_fn(device_id)
[_on_aggregation_broadcast]
       |
       +---> broadcast_device_snapshot (WebSocket)  [existing]
       +---> broadcast_virtual_snapshot (WebSocket)  [existing]
       +---> mqtt_publisher.on_device_update(device_id, snapshot)  [NEW]
       +---> mqtt_publisher.on_virtual_update(virtual_data)  [NEW]
```

### Component Boundaries

| Component | Responsibility | New/Modified | Communicates With |
|-----------|---------------|--------------|-------------------|
| `MqttPublisher` | MQTT connection lifecycle, message formatting, publishing | **NEW** | AppContext, Config |
| `MqttPublishConfig` | Broker host/port, topic prefix, interval, enable flag | **NEW** (dataclass in config.py) | Config |
| `__main__.py` | Wire MqttPublisher into broadcast chain, lifecycle | **MODIFIED** | MqttPublisher, AggregationLayer |
| `config.py` | Add `MqttPublishConfig` dataclass, load/save | **MODIFIED** | - |
| `context.py` | Add `mqtt_publisher` reference to AppContext | **MODIFIED** | MqttPublisher |
| `webapp.py` | Config API endpoints for MQTT publishing settings | **MODIFIED** | Config, MqttPublisher |
| `_on_aggregation_broadcast` | Extended to also call MqttPublisher | **MODIFIED** | MqttPublisher |

### Data Flow: Device Poll to MQTT Publish

```
1. plugin.poll() succeeds in _device_poll_loop
2. collector.collect_from_raw() produces snapshot dict
3. on_success(device_id) -> AggregationLayer.recalculate()
4. AggregationLayer writes to RegisterCache
5. AggregationLayer calls _broadcast_fn(device_id)
6. _on_aggregation_broadcast:
   a. WebSocket broadcast (existing)
   b. MqttPublisher.on_device_update(device_id, snapshot)  [NEW]
   c. MqttPublisher.on_virtual_update(virtual_data)  [NEW]
7. MqttPublisher formats JSON, publishes to MQTT broker
```

### MqttPublisher Design

```python
class MqttPublisher:
    """Publishes inverter data to external MQTT broker.

    Uses raw socket MQTT (consistent with venus_reader.py pattern).
    Runs as asyncio Task with reconnection loop.
    Rate-limits publishes per configurable interval.
    """

    def __init__(self, config: MqttPublishConfig):
        self._config = config
        self._socket: socket.socket | None = None
        self._connected: bool = False
        self._last_publish: dict[str, float] = {}  # device_id -> monotonic ts
        self._reconnect_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start connection loop as background task."""

    async def stop(self) -> None:
        """Disconnect and cancel background task."""

    async def on_device_update(self, device_id: str, snapshot: dict) -> None:
        """Called from broadcast chain. Rate-limits, formats, publishes."""

    async def on_virtual_update(self, virtual_data: dict) -> None:
        """Publish aggregated virtual inverter data."""

    def _format_device_payload(self, device_id: str, snapshot: dict) -> dict:
        """Extract publishable fields from snapshot."""

    async def _connect_loop(self) -> None:
        """Background task: maintain MQTT connection with reconnection."""
```

### MQTT Protocol: Raw Sockets vs paho-mqtt vs aiomqtt

**Recommendation: Raw sockets, consistent with venus_reader.py.**

Rationale:
- venus_reader.py already has working raw MQTT CONNECT/SUBSCRIBE/PUBLISH helpers (`_mqtt_connect`, `_mqtt_publish`). The publisher only needs CONNECT + PUBLISH (no SUBSCRIBE).
- Adding paho-mqtt or aiomqtt would be the first new runtime dependency since the project started. The codebase philosophy is "zero unnecessary dependencies."
- Publishing is simpler than subscribing -- no need for a full MQTT client library.
- The existing `_mqtt_publish` function in venus_reader.py can be extracted to a shared `mqtt_protocol.py` module.

**New shared module: `mqtt_protocol.py`**
Extract from venus_reader.py: `_mqtt_connect`, `_mqtt_publish`, `_mqtt_subscribe`, `_parse_mqtt_messages`. Both venus_reader.py and MqttPublisher import from this shared module. This eliminates code duplication.

### Config Structure

```yaml
mqtt_publish:
  enabled: false
  host: "mqtt-master.local"   # or IP
  port: 1883
  topic_prefix: "pv-proxy"
  interval: 5.0               # seconds between publishes (rate limit)
  client_id: "pv-inverter-proxy"
```

```python
@dataclass
class MqttPublishConfig:
    enabled: bool = False
    host: str = "mqtt-master.local"
    port: int = 1883
    topic_prefix: str = "pv-proxy"
    interval: float = 5.0
    client_id: str = "pv-inverter-proxy"
```

### Topic Structure

```
{topic_prefix}/device/{device_id}/status     -- JSON payload
{topic_prefix}/device/{device_id}/power      -- JSON payload
{topic_prefix}/virtual/status                -- aggregated JSON payload
{topic_prefix}/availability                  -- "online" / "offline" (LWT)
```

Example:
```
pv-proxy/device/a1b2c3d4e5f6/status
  {"ac_power_w": 12500, "dc_power_w": 13100, "status": "MPPT", ...}

pv-proxy/virtual/status
  {"total_power_w": 14200, "device_count": 2, ...}

pv-proxy/availability
  "online"
```

### Reconnection Strategy

Follow the same pattern as venus_reader.py and ConnectionManager:

1. **Initial connect** in `start()` -- fail gracefully, log warning, enter reconnect loop.
2. **Reconnect loop** -- exponential backoff 5s to 60s, same as ConnectionManager constants.
3. **Connection state** tracked in `self._connected` bool, exposed via AppContext for dashboard display.
4. **Socket errors during publish** -- catch, set `_connected = False`, reconnect loop picks up.
5. **PINGREQ keepalive** -- send every 30s when idle (same as venus_reader.py).
6. **Last Will and Testament (LWT)** -- set `{topic_prefix}/availability` to `"offline"` on unexpected disconnect.

### Rate Limiting

The poll loop fires every 1-5 seconds depending on device type. Publishing every poll would flood MQTT.

**Strategy: Per-device timestamp gating.**
```python
async def on_device_update(self, device_id: str, snapshot: dict) -> None:
    now = time.monotonic()
    last = self._last_publish.get(device_id, 0)
    if now - last < self._config.interval:
        return  # skip, too soon
    self._last_publish[device_id] = now
    # ... format and publish
```

This ensures each device publishes at most once per `interval` seconds, regardless of poll frequency.

### Broker Autodiscovery (mDNS)

For finding `mqtt-master.local` or other brokers on the LAN:

**Recommendation: Use `socket.getaddrinfo()` for `.local` hostname resolution first.** On most Linux systems (including Debian 13 on LXC), Avahi/mDNS is available and `.local` hostnames resolve via NSS. This requires zero new dependencies.

If explicit mDNS scanning is needed (discover brokers without knowing hostname):
- Use `zeroconf` library to discover `_mqtt._tcp.local.` services.
- This IS a new dependency but only needed for the discovery feature, not for publishing.
- Can be optional: try import, fall back to manual config.

**Phased approach:**
1. Phase 1: Support IP addresses and `.local` hostnames (zero deps).
2. Phase 2: Add `zeroconf` for "scan for brokers" button in UI (optional dep).

## Patterns to Follow

### Pattern 1: Background Task with Graceful Shutdown
**What:** MqttPublisher runs as an asyncio.Task, registered in AppContext, cancelled during shutdown.
**When:** Any long-running background service.
**Why:** Consistent with venus_mqtt_loop, heartbeat_task, poll loops.
```python
# In __main__.py run_with_shutdown():
if config.mqtt_publish.enabled:
    publisher = MqttPublisher(config.mqtt_publish)
    app_ctx.mqtt_publisher = publisher
    mqtt_pub_task = asyncio.create_task(publisher.start())

# In shutdown:
if mqtt_pub_task:
    await publisher.stop()
```

### Pattern 2: Config Hot-Reload
**What:** MQTT publishing config can be changed at runtime via webapp API without restart.
**When:** User changes broker host/port/interval in the config UI.
**Why:** Consistent with VenusConfig hot-reload pattern (cancel old task, start new loop).
```python
# In webapp config save handler:
if mqtt_publish_changed:
    if app_ctx.mqtt_publisher:
        await app_ctx.mqtt_publisher.stop()
    app_ctx.mqtt_publisher = MqttPublisher(new_config.mqtt_publish)
    asyncio.create_task(app_ctx.mqtt_publisher.start())
```

### Pattern 3: Extract Shared MQTT Protocol Module
**What:** Move raw MQTT socket helpers to `mqtt_protocol.py`.
**When:** First phase of MQTT publishing work.
**Why:** venus_reader.py and MqttPublisher both need CONNECT/PUBLISH. DRY.

```python
# mqtt_protocol.py
def mqtt_connect(host, port, client_id, will_topic=None, will_message=None): ...
def mqtt_publish(sock, topic, message, retain=False): ...
def mqtt_subscribe(sock, topics): ...
def mqtt_pingreq(sock): ...
def parse_mqtt_messages(data): ...
```

venus_reader.py then imports from mqtt_protocol.py instead of defining its own.

### Pattern 4: Publish Fire-and-Forget from Broadcast Chain
**What:** `on_device_update` is called synchronously in the broadcast chain but must not block.
**When:** Every aggregation broadcast.
**Why:** If MQTT is slow/down, WebSocket broadcast must not be delayed.

```python
# Option A: Non-blocking socket send (preferred)
# The raw socket publish is fast (<1ms for local network).
# If socket is dead, catch error, set _connected=False, return immediately.

# Option B: Queue-based (if latency becomes an issue)
# Push to asyncio.Queue, background task drains and publishes.
# More complex, only needed if publish blocks.
```

**Recommendation: Option A (direct send with error catch).** Raw socket publish to a LAN broker is sub-millisecond. Only switch to queue if profiling shows it blocks the event loop.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Poll Loop for MQTT Publishing
**What:** Creating a dedicated timer that reads snapshots independently.
**Why bad:** Introduces timing skew, duplicate data reads, potential for stale data races.
**Instead:** Hook into the existing broadcast chain triggered by AggregationLayer.

### Anti-Pattern 2: Using paho-mqtt Client
**What:** Adding paho-mqtt as a dependency for publishing.
**Why bad:** Breaks the zero-unnecessary-deps philosophy. Raw sockets work fine for simple PUBLISH. paho-mqtt's threading model conflicts with asyncio.
**Instead:** Raw socket MQTT using shared mqtt_protocol.py module.

### Anti-Pattern 3: Publishing Raw Modbus Registers
**What:** Sending register arrays over MQTT for downstream to decode.
**Why bad:** MQTT consumers (Home Assistant, Grafana, Node-RED) expect physical values in standard units.
**Instead:** Publish decoded snapshot values (watts, volts, etc.) from DashboardCollector.

### Anti-Pattern 4: Blocking the Event Loop with DNS Resolution
**What:** Calling `socket.getaddrinfo("mqtt-master.local", 1883)` synchronously in async context.
**Why bad:** mDNS resolution can take 2-5 seconds, blocks entire event loop.
**Instead:** Use `loop.run_in_executor(None, socket.getaddrinfo, ...)` or resolve once at startup.

### Anti-Pattern 5: Publishing Every Poll Cycle
**What:** No rate limiting, publishing 1Hz data from each device.
**Why bad:** Floods broker, wastes bandwidth, most consumers don't need 1Hz updates.
**Instead:** Configurable interval (default 5s) with per-device timestamp gating.

## Suggested Build Order

The build order respects dependencies -- each phase produces a testable artifact.

### Phase 1: MQTT Protocol Extraction
**What:** Extract raw MQTT helpers from venus_reader.py into `mqtt_protocol.py`.
**Modifies:** venus_reader.py (imports change), creates mqtt_protocol.py.
**Test:** Existing venus_reader tests still pass, new unit tests for mqtt_protocol.
**Risk:** Low. Pure refactor, no behavior change.

### Phase 2: Config + MqttPublisher Core
**What:** Add `MqttPublishConfig` dataclass, create `mqtt_publisher.py` with connection lifecycle.
**Modifies:** config.py (add dataclass + load/save), context.py (add field).
**Creates:** mqtt_publisher.py.
**Test:** Unit test publisher connect/disconnect, config serialization.
**Depends on:** Phase 1 (mqtt_protocol.py).

### Phase 3: Wire into Broadcast Chain
**What:** Extend `_on_aggregation_broadcast` in __main__.py to call MqttPublisher. Add start/stop lifecycle.
**Modifies:** __main__.py.
**Test:** Integration test: mock broker, verify messages arrive after poll.
**Depends on:** Phase 2.

### Phase 4: Topic Structure + Payload Formatting
**What:** Define topic hierarchy, JSON payload format, LWT, retain flags.
**Modifies:** mqtt_publisher.py (format methods).
**Test:** Unit test payload formatting against expected schema.
**Depends on:** Phase 3.

### Phase 5: Broker Autodiscovery (mDNS)
**What:** `.local` hostname resolution via `getaddrinfo` in executor. Optional zeroconf scan.
**Creates:** broker_discovery.py (or method in mqtt_publisher.py).
**Test:** Unit test with mock DNS, integration test on LAN.
**Depends on:** Phase 2.

### Phase 6: Webapp Config UI
**What:** Config panel for MQTT publishing (broker, port, interval, enable/disable). Connection status dot.
**Modifies:** webapp.py (API endpoints), frontend JS/HTML.
**Test:** API tests, manual UI verification.
**Depends on:** Phase 2, Phase 3.

### Phase 7: Hot-Reload + Dashboard Status
**What:** Restart publisher on config change without app restart. Show MQTT publish status on dashboard.
**Modifies:** webapp.py (config save handler), frontend.
**Depends on:** Phase 6.

## Scalability Considerations

| Concern | Current (2 devices) | At 10 devices | At 50 devices |
|---------|---------------------|---------------|---------------|
| Publish rate | 2 msgs/5s | 10 msgs/5s | 50 msgs/5s |
| Socket writes | Negligible | Negligible | Still fine for LAN MQTT |
| Payload size | ~500 bytes/msg | Same per msg | Same per msg |
| Memory | Negligible | Negligible | Negligible |
| Broker load | Trivial | Trivial | Trivial for Mosquitto |

No scalability concerns for the foreseeable use case. LAN MQTT brokers handle thousands of messages per second.

## File Inventory: New vs Modified

| File | Status | Purpose |
|------|--------|---------|
| `mqtt_protocol.py` | **NEW** | Shared raw MQTT socket helpers |
| `mqtt_publisher.py` | **NEW** | MqttPublisher class |
| `broker_discovery.py` | **NEW** (optional) | mDNS broker discovery |
| `config.py` | **MODIFIED** | Add MqttPublishConfig dataclass |
| `context.py` | **MODIFIED** | Add mqtt_publisher field to AppContext |
| `__main__.py` | **MODIFIED** | Wire publisher lifecycle |
| `venus_reader.py` | **MODIFIED** | Import from mqtt_protocol.py |
| `webapp.py` | **MODIFIED** | Config API + status endpoint |
| Frontend HTML/JS | **MODIFIED** | Config UI panel, dashboard status dot |

## Sources

- Codebase analysis: venus_reader.py (raw MQTT implementation pattern)
- Codebase analysis: __main__.py (task lifecycle and broadcast wiring)
- Codebase analysis: aggregation.py (broadcast callback chain)
- Codebase analysis: config.py (dataclass config pattern)
- Codebase analysis: dashboard.py (snapshot dict structure)
- Codebase analysis: context.py (AppContext fields)
- Codebase analysis: pyproject.toml (dependency policy -- no paho-mqtt)
