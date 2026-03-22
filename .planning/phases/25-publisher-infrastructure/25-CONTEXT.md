# Phase 25: Publisher Infrastructure & Broker Connectivity - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

The system can connect to a configurable MQTT broker, maintain a resilient connection with LWT, and discover brokers on the LAN via mDNS. No telemetry publishing yet — that's Phase 26. This phase builds the plumbing: aiomqtt client, config dataclass, queue architecture, reconnect logic, and mDNS discovery endpoint.

</domain>

<decisions>
## Implementation Decisions

### MQTT Library
- **D-01:** Use `aiomqtt` (>=2.3) for the publisher — native asyncio, QoS 1, LWT, retain, auto-reconnect. Do NOT extend venus_reader.py raw socket client.
- **D-02:** Use `zeroconf` (>=0.140) for mDNS broker discovery — AsyncZeroconf, discovers `_mqtt._tcp.local.` services.
- **D-03:** Leave venus_reader.py completely untouched — existing Venus OS MQTT subscriber is a separate concern.

### Topic Structure
- **D-04:** Topic prefix `pvproxy` as default, configurable via `topic_prefix` in config.
- **D-05:** Topic layout: `{prefix}/{device_id}/state`, `{prefix}/{device_id}/availability`, `{prefix}/virtual/state`, `{prefix}/status`
- **D-06:** Availability topic uses LWT: "online" on connect, "offline" as Will message.

### Config YAML
- **D-07:** New top-level key `mqtt_publish:` in config.yaml (separate from venus MQTT).
- **D-08:** Fields: `enabled` (bool, default false), `host` (str, default "mqtt-master.local"), `port` (int, default 1883), `topic_prefix` (str, default "pvproxy"), `interval_s` (int, default 5), `client_id` (str, default "pv-proxy-pub").
- **D-09:** New `MqttPublishConfig` dataclass in config.py following established pattern.

### Architecture
- **D-10:** Queue-based decoupling: asyncio.Queue (maxsize=100) between broadcast chain and publisher. Publisher task consumes from queue, never blocks poll loop.
- **D-11:** Publisher is a single asyncio.Task stored in AppContext as `mqtt_pub_task`.
- **D-12:** Hot-reload follows venus_reader pattern: cancel old task, create new task with new config on config save.
- **D-13:** Reconnect with exponential backoff (1s → 2s → 4s → ... → 30s cap) handled by aiomqtt.

### mDNS Discovery
- **D-14:** mDNS scan is manual only — triggered via REST endpoint `POST /api/mqtt/discover`, no auto-scan at startup.
- **D-15:** Scan runs for 3 seconds, returns list of found brokers with hostname + port.
- **D-16:** mDNS scan logic in new module `mdns_discovery.py`, wired as webapp endpoint.

### Claude's Discretion
- Exact aiomqtt Client wrapper structure
- Queue overflow strategy (drop oldest vs block)
- Exact mDNS response format
- Error logging detail level
- Whether client_id includes hostname for uniqueness

</decisions>

<specifics>
## Specific Ideas

- Target broker is `mqtt-master.local` — this should "just work" as default config
- Follows existing patterns exactly: dataclass config, AppContext state, conditional task creation in __main__.py, hot-reload via cancel/recreate in webapp config_save_handler

</specifics>

<canonical_refs>
## Canonical References

### Existing MQTT patterns
- `src/venus_os_fronius_proxy/venus_reader.py` — Raw socket MQTT client pattern (DO NOT modify, but understand the loop structure)
- `src/venus_os_fronius_proxy/context.py` — AppContext dataclass where publisher task/state will live

### Config patterns
- `src/venus_os_fronius_proxy/config.py` — Dataclass config pattern to follow for MqttPublishConfig
- `config/config.example.yaml` — Example config structure to extend

### Startup and lifecycle
- `src/venus_os_fronius_proxy/__main__.py` — Async task creation pattern (venus_task model)
- `src/venus_os_fronius_proxy/webapp.py` — Hot-reload pattern in config_save_handler

### Research
- `.planning/research/STACK.md` — aiomqtt + zeroconf library details
- `.planning/research/ARCHITECTURE.md` — Integration points and data flow
- `.planning/research/PITFALLS.md` — Queue decoupling, reconnect pitfalls

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Config` dataclass aggregation pattern (config.py) — add `mqtt_publish: MqttPublishConfig` field
- `AppContext` state pattern (context.py) — add `mqtt_pub_task`, `mqtt_pub_connected` fields
- `venus_mqtt_loop` startup pattern (__main__.py) — conditional task creation model
- `config_save_handler` hot-reload (webapp.py) — cancel/recreate task pattern

### Established Patterns
- All long-running loops are asyncio.Tasks stored in AppContext
- Config uses `@dataclass` with defaults, loaded via dict comprehension from YAML
- Hot-reload = cancel old task + create new task (no locking, asyncio single-threaded)
- structlog for all logging with bound context

### Integration Points
- `config.py` — Add MqttPublishConfig dataclass + add to Config
- `context.py` — Add mqtt_pub fields to AppContext
- `__main__.py` — Add conditional publisher task creation
- `webapp.py` — Add hot-reload in config_save_handler + mDNS discovery endpoint
- `pyproject.toml` — Add aiomqtt + zeroconf dependencies
- New file: `mqtt_publisher.py` — Publisher loop with queue consumer
- New file: `mdns_discovery.py` — mDNS scan function

</code_context>

<deferred>
## Deferred Ideas

- Actual telemetry payload format and publishing — Phase 26
- Home Assistant MQTT Auto-Discovery config payloads — Phase 26
- Webapp MQTT config UI — Phase 27
- MQTT username/password auth — Future
- TLS for MQTT — Future

</deferred>

---

*Phase: 25-publisher-infrastructure*
*Context gathered: 2026-03-22*
