# Technology Stack: MQTT Data Publishing (v5.0)

**Project:** Venus OS Fronius Proxy
**Researched:** 2026-03-22
**Scope:** New dependencies for MQTT publishing, mDNS broker autodiscovery, configurable intervals
**Overall confidence:** HIGH

## Critical Context

The existing codebase does **NOT** use paho-mqtt despite previous research stating otherwise. The Venus OS MQTT subscriber (`venus_reader.py`) is a hand-rolled raw-socket MQTT 3.1.1 implementation (~100 LOC) that handles CONNECT, SUBSCRIBE, PUBLISH, and PINGREQ at the byte level. It runs blocking socket I/O via `run_in_executor` with QoS 0 only.

This hand-rolled approach works for the Venus OS subscriber (single broker, known topics, read-mostly) but is inadequate for a proper MQTT publisher because:
- No QoS 1 support (no PUBACK handling) -- data publishing benefits from at-least-once delivery
- No Last Will and Testament (LWT) -- consumers need to know when the publisher goes offline
- No reconnect with session persistence -- published data would be lost on disconnect
- No proper MQTT packet framing for large payloads

## Existing Stack (DO NOT CHANGE)

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12 | Runtime |
| pymodbus | >=3.6,<4.0 | Modbus TCP server + SolarEdge client |
| aiohttp | >=3.10,<4.0 | HTTP server, WebSocket, REST API, OpenDTU client |
| structlog | >=24.0 | Structured JSON logging |
| PyYAML | >=6.0,<7.0 | Configuration files |
| Vanilla JS | -- | Frontend (zero dependencies, no build) |

## Recommended Stack Additions

### MQTT Publishing Client

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| aiomqtt | >=2.3,<3.0 | Async MQTT client for publishing inverter data | Native asyncio (`async with`/`async for`), wraps battle-tested paho-mqtt, supports QoS 0/1/2, LWT, clean sessions, auto-reconnect. Fits the existing asyncio architecture perfectly. |
| paho-mqtt | >=2.0,<3.0 | Transitive dependency of aiomqtt | Installed automatically. Not used directly. |

**Why aiomqtt over alternatives:**
- The project is 100% asyncio. aiomqtt is the idiomatic asyncio MQTT client -- no callbacks, no threading, just `await client.publish()`.
- The existing `venus_reader.py` uses `run_in_executor` to bridge blocking sockets into asyncio. aiomqtt eliminates this anti-pattern for the publisher.
- paho-mqtt alone would require callback wiring and thread synchronization with the asyncio event loop.
- Extending the hand-rolled client for QoS 1, LWT, and reconnect would be reinventing paho-mqtt poorly.

**Key aiomqtt features used:**
- `Client(hostname, port)` with `async with` for connection lifecycle
- `client.publish(topic, payload, qos=)` for data publishing
- `will=Will(topic, payload)` for LWT (offline detection)
- Built-in reconnect on connection loss

**Confidence:** HIGH -- aiomqtt v2.4.0 released May 2025, actively maintained, 491+ GitHub stars, well-documented.

### mDNS Broker Autodiscovery

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| zeroconf | >=0.140,<1.0 | mDNS/DNS-SD service discovery for `_mqtt._tcp.local.` | Pure Python, asyncio-native (`AsyncZeroconf`, `AsyncServiceBrowser`), actively maintained (v0.148.0, Oct 2025). Used by Home Assistant for the same purpose. |

**Why zeroconf:**
- The standard `_mqtt._tcp.local.` service type is what Mosquitto brokers advertise via Avahi/mDNS. The target broker `mqtt-master.local` almost certainly advertises this.
- zeroconf has first-class async support via `AsyncZeroconf` and `AsyncServiceBrowser` -- no executor bridging needed.
- Only library in the Python ecosystem that does mDNS service browsing properly. There is no real alternative.
- Lightweight one-shot discovery: browse for `_mqtt._tcp.local.`, collect results for a few seconds, pick best match, done.

**Confidence:** HIGH -- python-zeroconf v0.148.0 released Oct 2025, >1000 GitHub stars, used by Home Assistant core.

### No Other Dependencies Needed

| Category | Decision | Rationale |
|----------|----------|-----------|
| JSON serialization | Use stdlib `json` | Payloads are small dicts (~500 bytes). No need for orjson/ujson. |
| Scheduling | Use `asyncio.sleep` in a loop | Configurable interval (e.g., 5s) in an `async while True` loop. The existing poll loops already use this exact pattern. |
| Topic templating | Use f-strings | Topics like `pv-proxy/{device_id}/power` are simple string formatting. No Jinja2 needed. |
| Config validation | Use existing dataclass pattern | Add a `MqttPublishConfig` dataclass to `config.py` following the established `VenusConfig` pattern. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| MQTT client | aiomqtt | paho-mqtt (direct) | Callback-based, requires thread bridging with asyncio. aiomqtt wraps it with clean async API. |
| MQTT client | aiomqtt | Extend hand-rolled client in venus_reader.py | Would need QoS 1 PUBACK, LWT, reconnect, session persistence -- essentially reimplementing paho-mqtt poorly. |
| MQTT client | aiomqtt | gmqtt | Less maintained, fewer users, no paho-mqtt foundation. |
| mDNS | zeroconf | avahi-browse (subprocess) | External dependency on avahi-daemon, parsing subprocess output is fragile, not async. |
| mDNS | zeroconf | socket.getaddrinfo for mqtt-master.local | Only resolves a known hostname. Does not discover unknown brokers on the LAN. |

## Integration Points

### Architecture Fit

```
DeviceRegistry (poll loops)
    |
    v per-device snapshot (DashboardCollector)
    |
    +---> WebSocket broadcast (existing, in webapp.py)
    |
    +---> MQTT Publisher (NEW, mqtt_publisher.py)
              |
              v aiomqtt.Client
              |
              v mqtt-master.local:1883
```

### MQTT Publisher Task

The publisher runs as an asyncio task in `__main__.py`, alongside `venus_mqtt_loop` and device poll tasks. Pattern:

```python
async def mqtt_publish_loop(app_ctx: AppContext, config: MqttPublishConfig):
    """Background task: publish device snapshots to external MQTT broker."""
    if not config.enabled:
        return

    host = config.host
    if config.autodiscovery:
        discovered = await discover_mqtt_broker()  # zeroconf
        if discovered:
            host = discovered

    will = aiomqtt.Will(
        topic=f"{config.topic_prefix}/status",
        payload=json.dumps({"online": False}),
        qos=1, retain=True,
    )

    async with aiomqtt.Client(host, config.port, will=will) as client:
        # Announce online
        await client.publish(
            f"{config.topic_prefix}/status",
            json.dumps({"online": True}), qos=1, retain=True,
        )
        while True:
            for dev_id, dev_state in app_ctx.devices.items():
                snapshot = dev_state.collector.last_snapshot
                if snapshot:
                    await client.publish(
                        f"{config.topic_prefix}/{dev_id}",
                        json.dumps(snapshot), qos=config.qos,
                    )
            await asyncio.sleep(config.interval)
```

### Config Dataclass

Add to `config.py` following the established `VenusConfig` pattern:

```python
@dataclass
class MqttPublishConfig:
    enabled: bool = False
    host: str = "mqtt-master.local"    # Default target broker
    port: int = 1883
    client_id: str = "pv-inverter-proxy"
    topic_prefix: str = "pv-proxy"     # -> pv-proxy/{device_id}/...
    interval: float = 5.0              # Publish interval in seconds
    autodiscovery: bool = True         # Try mDNS _mqtt._tcp before using host
    qos: int = 0                       # 0 or 1
```

Add `mqtt_publish: MqttPublishConfig` field to the `Config` dataclass. Load from YAML section `mqtt_publish:` using the same filtered-kwargs pattern as all other config sections.

### AppContext Extension

Add to `context.py`:

```python
# MQTT Publisher state
mqtt_publish_connected: bool = False
mqtt_publish_broker: str = ""        # Resolved broker address
mqtt_publish_task: object = None     # asyncio.Task
```

### Separation from Venus OS MQTT

The Venus OS MQTT (`venus_reader.py`) and the new MQTT publisher are completely separate concerns:
- **Venus MQTT**: Subscribes to Venus OS broker (192.168.3.146) for ESS settings. Hand-rolled raw-socket client, read-only.
- **MQTT Publisher**: Publishes to external broker (mqtt-master.local). aiomqtt client, write-only.

Do NOT refactor `venus_reader.py` to use aiomqtt in this milestone. It works, it is tested, and mixing concerns creates risk. Migration can happen in a future milestone if desired.

## What NOT to Add

| Library | Why Not |
|---------|---------|
| Home Assistant MQTT Discovery | Out of scope for v5.0. HA auto-discovery uses a specific JSON schema on `homeassistant/` topics. Add in a future milestone if needed. |
| MQTT bridge/relay | Not needed. This is a simple publisher, not a broker-to-broker bridge. |
| TLS/authentication libraries | Explicitly out of scope per PROJECT.md ("Alles im selben LAN, kein Internet-Exposure"). |
| Database for message persistence | MQTT QoS handles delivery guarantees. No need for local queue/DB. |
| orjson/msgpack | Payloads are tiny JSON dicts. stdlib `json` is fine. |
| pydantic | Dataclasses are sufficient for config validation. Established project pattern. |

## Installation

```bash
# New dependencies for v5.0
pip install "aiomqtt>=2.3,<3.0" "zeroconf>=0.140,<1.0"
```

Update `pyproject.toml`:
```toml
dependencies = [
    "pymodbus>=3.6,<4.0",
    "structlog>=24.0",
    "PyYAML>=6.0,<7.0",
    "aiohttp>=3.10,<4.0",
    "aiomqtt>=2.3,<3.0",       # NEW: async MQTT publishing
    "zeroconf>=0.140,<1.0",    # NEW: mDNS broker autodiscovery
]
```

**Dependency footprint:** aiomqtt pulls in paho-mqtt (~150KB). zeroconf is pure Python (~2MB installed). Total addition: ~2.5MB. Acceptable for an LXC deployment.

## New Files

| File | Purpose |
|------|---------|
| `src/venus_os_fronius_proxy/mqtt_publisher.py` | MQTT publish loop, broker connection, payload formatting |
| `src/venus_os_fronius_proxy/mdns_discovery.py` | mDNS `_mqtt._tcp.local.` broker discovery using zeroconf |

Modified files: `config.py` (add `MqttPublishConfig`), `context.py` (add publisher state), `__main__.py` (start publisher task), `webapp.py` (config API endpoints), `app.js` + `index.html` + `style.css` (config UI).

## Sources

- [aiomqtt GitHub (empicano)](https://github.com/empicano/aiomqtt) -- v2.4.0, May 2025
- [aiomqtt PyPI](https://pypi.org/project/aiomqtt/) -- latest release info
- [python-zeroconf GitHub](https://github.com/python-zeroconf/python-zeroconf) -- v0.148.0, Oct 2025
- [zeroconf PyPI](https://pypi.org/project/zeroconf/) -- latest release info
- [EMQ Python MQTT Clients Guide 2025](https://www.emqx.com/en/blog/comparision-of-python-mqtt-client) -- comparison of Python MQTT clients
- [Home Assistant mDNS MQTT discussion](https://community.home-assistant.io/t/mosquitto-broker-announcing-advertising-mqtt-service-via-mdns/343190) -- _mqtt._tcp service type for Mosquitto
- Existing codebase: `venus_reader.py`, `config.py`, `context.py`, `device_registry.py`, `__main__.py` (HIGH confidence, source of truth)
