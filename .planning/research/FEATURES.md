# Feature Landscape: MQTT Data Publishing

**Domain:** PV inverter data publishing to external MQTT broker
**Researched:** 2026-03-22
**Scope:** New features only -- building on existing v4.0 multi-inverter proxy with DeviceRegistry, DashboardCollector snapshots, and Venus OS MQTT subscriber

## Table Stakes

Features users expect from any solar MQTT publisher. Missing = integration feels broken.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| Per-device MQTT topics | Every solar MQTT tool (SolarAssistant, deye-inverter-mqtt, growatt2mqtt) publishes per-device. Users filter by device in HA/Grafana | Low | DeviceRegistry, DashboardCollector snapshots | Topic per inverter + virtual aggregated device |
| JSON payloads with physical units | Standard format. All HA integrations expect structured JSON, not raw register values | Low | DashboardCollector already decodes to physical units | Reuse existing snapshot structure, flatten for MQTT |
| Configurable broker connection | Users have existing brokers (Mosquitto on HA, standalone, mqtt-master.local). Must point to their broker | Low | Config dataclass, existing YAML pattern | host, port, client_id, enable/disable |
| Configurable publish interval | deye-inverter-mqtt defaults 60s, growatt2mqtt does 4s, SolarAssistant ~5s. Users need control | Low | asyncio timer | Default 5s (matches poll interval), range 1-60s |
| Availability topic (online/offline) | HA uses availability to grey out sensors when device unreachable. Standard MQTT pattern | Low | MQTT LWT (Last Will and Testament) | `pv-proxy/status` with `online`/`offline` payload, set LWT on connect |
| Broker connection status in webapp | Existing pattern: Venus MQTT shows connection bobble. Users expect same for publish broker | Low | Existing connection bobble pattern | Reuse `ve-dot` component |
| Enable/disable toggle in config UI | Not everyone wants MQTT publishing. Must be opt-in, not forced | Low | Existing config page pattern | Per the existing Venus config section pattern |

## Differentiators

Features that set this apart from generic solar MQTT bridges. Not expected, but valued.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| Home Assistant MQTT Auto-Discovery | Zero-config HA integration. Devices + entities appear automatically with correct units, icons, device_class. Huge UX win -- no manual sensor.yaml editing | Medium | Requires specific HA discovery topic format + JSON config payloads | THE killer feature for this milestone |
| Virtual aggregated device in HA | HA sees both individual inverters AND the combined virtual PV plant. Matches proxy architecture | Low | AggregationLayer already computes sums | Publish aggregated snapshot as separate HA device |
| mDNS broker autodiscovery | Find mqtt-master.local or any broker advertising `_mqtt._tcp` without manual IP entry. Matches v3.1 auto-discovery pattern | Medium | python-zeroconf (new dependency) or socket-based mDNS query | Nice for first-setup UX, but fallback to manual config essential |
| Publish-on-change with max interval | Reduce broker load: only publish when values actually change, with configurable max staleness (e.g., 360s). deye-inverter-mqtt does this | Low-Med | Snapshot diff logic | Good for Grafana (less noise), but adds complexity. Defer to post-MVP |
| Per-device enable/disable publishing | Some inverters might be monitoring-only, user may not want all devices in HA | Low | Existing per-inverter config pattern | Add `mqtt_publish: true/false` to InverterEntry |
| Energy dashboard ready sensors | HA Energy Dashboard requires specific `state_class: total_increasing` + `device_class: energy` on kWh sensors. Without this, energy data won't appear in HA Energy tab | Low | Correct HA discovery config values | Include in auto-discovery payloads from day one |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Built-in MQTT broker | Proxy is a publisher, not infrastructure. Users have their own broker (Mosquitto, EMQX, etc.) | Connect to external broker only |
| TLS/authentication for MQTT | PROJECT.md explicitly marks this out of scope -- everything is same-LAN. Adding TLS would complicate setup for zero security benefit in this context | Plain TCP connection. Document that TLS is not supported |
| Retained messages for all data | Retained power/current values go stale instantly. Only retain availability and discovery config | Retain: discovery config + availability. Do NOT retain: telemetry data |
| Command/control via external MQTT | Power limiting commands should only come through the webapp or Venus OS (safety critical). Accepting commands from random MQTT clients is dangerous | Publish-only, no subscribe on external broker. Control stays in webapp/Venus OS |
| Custom topic templates | Jinja2 or variable substitution in topic paths adds complexity for marginal benefit. Fixed, well-structured topics are easier to document and debug | Fixed topic hierarchy with device ID interpolation |
| Separate MQTT client per device | One shared paho-mqtt client is simpler, more resource-efficient, and easier to manage lifecycle | Single MqttPublisher with per-device topic routing |
| Historical data replay | Proxy has in-memory ring buffers, not a database. MQTT is real-time. Grafana/InfluxDB handle history | Publish current values only. History is the consumer's job |
| QoS 2 (exactly once delivery) | Massive overhead for telemetry that updates every few seconds. Lost message = next one arrives in 5s anyway | QoS 0 for telemetry, QoS 1 for discovery config and availability |

## Feature Dependencies

```
Config: MqttPublishConfig dataclass
  |
  +-> Broker Connection (paho-mqtt async loop)
  |     |
  |     +-> LWT / Availability topic (set on connect)
  |     |
  |     +-> HA Auto-Discovery (publish config payloads on connect)
  |     |     |
  |     |     +-> Energy Dashboard ready sensors (correct state_class/device_class)
  |     |
  |     +-> Telemetry Publishing (periodic JSON payloads)
  |           |
  |           +-> Per-device topics (individual inverters)
  |           |
  |           +-> Virtual aggregated device topic
  |
  +-> Webapp Config UI (broker settings, enable/disable, status dot)
  |
  +-> mDNS Broker Discovery (optional, enhances config UX)
```

## Detailed Feature Specifications

### 1. MQTT Topic Structure

Use a fixed hierarchy. Based on ecosystem research (SolarAssistant, deye-inverter-mqtt, growatt2mqtt):

```
pv-proxy/status                              -> "online" / "offline" (LWT)
pv-proxy/device/{device_id}/state            -> JSON telemetry payload
pv-proxy/device/{device_id}/availability     -> "online" / "offline"
pv-proxy/virtual/state                       -> aggregated virtual inverter JSON
pv-proxy/virtual/availability                -> "online" / "offline"
```

Where `{device_id}` is the existing InverterEntry.id (12-char hex). The topic prefix `pv-proxy` should be configurable (default: `pv-proxy`).

### 2. Telemetry Payload Format

Flat JSON, physical units, matching existing DashboardCollector snapshot fields:

```json
{
  "ts": 1711100000.0,
  "ac_power_w": 8450.0,
  "ac_voltage_an_v": 230.5,
  "ac_voltage_bn_v": 231.2,
  "ac_voltage_cn_v": 229.8,
  "ac_current_a": 12.3,
  "ac_current_l1_a": 4.1,
  "ac_current_l2_a": 4.1,
  "ac_current_l3_a": 4.1,
  "ac_frequency_hz": 50.01,
  "dc_power_w": 8620.0,
  "dc_voltage_v": 680.0,
  "dc_current_a": 12.7,
  "energy_total_wh": 45230000,
  "daily_energy_wh": 32400,
  "temperature_c": 42.5,
  "status": "MPPT",
  "status_code": 4,
  "peak_power_w": 12500.0,
  "operating_hours": 6.25,
  "efficiency_pct": 67.6
}
```

### 3. Home Assistant MQTT Auto-Discovery

Publish config payloads to `homeassistant/sensor/{node_id}/{object_id}/config` on connect. One config message per sensor entity. All sensors grouped under one HA device per inverter.

Example discovery payload for AC Power sensor:

```json
{
  "name": "AC Power",
  "unique_id": "pv_proxy_{device_id}_ac_power",
  "state_topic": "pv-proxy/device/{device_id}/state",
  "value_template": "{{ value_json.ac_power_w }}",
  "unit_of_measurement": "W",
  "device_class": "power",
  "state_class": "measurement",
  "suggested_display_precision": 0,
  "availability": [
    {"topic": "pv-proxy/status"},
    {"topic": "pv-proxy/device/{device_id}/availability"}
  ],
  "availability_mode": "all",
  "device": {
    "identifiers": ["pv_proxy_{device_id}"],
    "name": "{inverter_name}",
    "manufacturer": "{inverter_mfr}",
    "model": "{inverter_model}",
    "serial_number": "{inverter_serial}",
    "sw_version": "5.0",
    "via_device": "pv_proxy",
    "configuration_url": "http://{proxy_ip}/"
  },
  "origin": {
    "name": "PV Inverter Proxy",
    "sw_version": "5.0",
    "support_url": "http://{proxy_ip}/"
  }
}
```

**Sensor entity map (per device):**

| Sensor | device_class | state_class | unit | display_precision |
|--------|-------------|-------------|------|-------------------|
| AC Power | `power` | `measurement` | `W` | 0 |
| DC Power | `power` | `measurement` | `W` | 0 |
| AC Voltage L1 | `voltage` | `measurement` | `V` | 1 |
| AC Voltage L2 | `voltage` | `measurement` | `V` | 1 |
| AC Voltage L3 | `voltage` | `measurement` | `V` | 1 |
| AC Current | `current` | `measurement` | `A` | 1 |
| AC Frequency | `frequency` | `measurement` | `Hz` | 2 |
| DC Voltage | `voltage` | `measurement` | `V` | 1 |
| DC Current | `current` | `measurement` | `A` | 1 |
| Temperature | `temperature` | `measurement` | `C` | 1 |
| Total Energy | `energy` | `total_increasing` | `Wh` | 0 |
| Daily Energy | `energy` | `total` | `Wh` | 0 |
| Peak Power | `power` | `measurement` | `W` | 0 |
| Operating Hours | `duration` | `total_increasing` | `h` | 2 |
| Efficiency | None | `measurement` | `%` | 1 |
| Status | `enum` | None | None | None |

**Important HA 2026.4 change:** Use `default_entity_id` instead of `object_id` in discovery payloads. The old `object_id` option is deprecated as of HA Core 2026.4.

### 4. Broker Connection Management

Use paho-mqtt v2.x async client (already a project dependency). Key behaviors:

- **Reconnect:** Automatic with exponential backoff (paho built-in)
- **LWT (Last Will):** Set `pv-proxy/status` to `offline` with retain=True on connect
- **On connect:** Publish `online` to status topic, then all discovery configs (retained)
- **Clean session:** True (no persistent sessions needed for publish-only)
- **Client ID:** `pv-proxy-pub-{short_uuid}` to avoid collision with Venus subscriber
- **Keep-alive:** 60s (standard)

### 5. Config Structure

New `MqttPublishConfig` dataclass alongside existing `VenusConfig`:

```yaml
mqtt_publish:
  enabled: false          # opt-in
  host: "mqtt-master.local"  # or IP, or discovered via mDNS
  port: 1883
  topic_prefix: "pv-proxy"
  interval: 5             # seconds, 1-60
  client_id: ""           # auto-generated if empty
```

### 6. mDNS Broker Discovery

Browse for `_mqtt._tcp.local.` services using python-zeroconf. This is a new dependency but well-established (used by Home Assistant itself). Discovery flow:

1. User clicks "Discover Broker" in config UI
2. Backend does 5-second mDNS browse
3. Returns list of found brokers with hostname + IP + port
4. User selects one, populates config fields
5. Falls back to manual entry if nothing found

**Confidence:** MEDIUM -- zeroconf is reliable, but not all MQTT brokers advertise via mDNS. Mosquitto does NOT do this by default (requires separate Avahi service file). The user's mqtt-master.local suggests they already have mDNS working for hostname resolution, so a simple `socket.getaddrinfo("mqtt-master.local", 1883)` might be sufficient without full zeroconf.

**Recommendation:** Start with hostname resolution (mqtt-master.local works via system mDNS). Add full zeroconf browse as a differentiator if time permits.

## MVP Recommendation

**Phase 1: Core Publishing (must-have)**
1. `MqttPublishConfig` dataclass + YAML config loading
2. paho-mqtt publisher with LWT, reconnect, lifecycle management
3. Per-device telemetry publishing (JSON payloads from DashboardCollector snapshots)
4. Virtual aggregated device publishing
5. Availability topics per device

**Phase 2: Home Assistant Integration (high value)**
6. HA MQTT Auto-Discovery config payloads (all sensor entities)
7. Energy Dashboard ready sensors (correct state_class/device_class)
8. Discovery cleanup on device removal (publish empty retained config)

**Phase 3: Webapp Config (user-facing)**
9. Config UI section for MQTT Publishing (host, port, interval, enable)
10. Connection status dot (reuse existing pattern)
11. mDNS broker discovery button (hostname resolution first, full zeroconf as stretch)

**Defer:**
- Publish-on-change mode: Nice optimization but adds snapshot diff complexity. Ship fixed interval first.
- Per-device publish enable/disable: All enabled devices publish. Keep it simple for v5.0.

## Sources

- [Home Assistant MQTT Integration](https://www.home-assistant.io/integrations/mqtt/) -- Discovery topic format, device grouping, origin field (HIGH confidence)
- [Home Assistant MQTT Sensor](https://www.home-assistant.io/integrations/sensor.mqtt/) -- device_class, state_class, value_template (HIGH confidence)
- [SolarAssistant MQTT](https://solar-assistant.io/help/integration/mqtt) -- Topic structure patterns for solar monitoring (MEDIUM confidence)
- [deye-inverter-mqtt](https://github.com/kbialek/deye-inverter-mqtt) -- Publish intervals, publish-on-change, availability topics (MEDIUM confidence)
- [growatt2mqtt](https://github.com/nygma2004/growatt2mqtt) -- 4s publish interval reference (LOW confidence)
- [HA 2026.4 discovery deprecation](https://github.com/jomjol/AI-on-the-edge-device/issues/3932) -- object_id -> default_entity_id migration (MEDIUM confidence)
- [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) -- mDNS service discovery for _mqtt._tcp (HIGH confidence)
- [HA Community: MQTT discovery + JSON](https://community.home-assistant.io/t/mqtt-auto-discovery-and-json-payload/409459) -- JSON payload patterns (MEDIUM confidence)
- [huABus Huawei Solar MQTT](https://community.home-assistant.io/t/app-huabus-huawei-solar-modbus-to-mqtt-sun2-3-5-000-mqtt-home-assistant-auto-discovery/958230) -- Real-world solar inverter MQTT auto-discovery with 68 entities (MEDIUM confidence)
