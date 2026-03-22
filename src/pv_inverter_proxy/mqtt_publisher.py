"""MQTT publisher with queue-based decoupling, LWT, HA discovery, and change detection.

Consumes messages from ctx.mqtt_pub_queue and publishes to the configured broker.
Completely independent from venus_reader.py (per D-03).
"""
from __future__ import annotations

import asyncio
import json
import time

import aiomqtt
import structlog

log = structlog.get_logger(component="mqtt_publisher")


async def mqtt_publish_loop(ctx, config, inverters=None, virtual_name="") -> None:
    """Background task: consume from queue, publish to MQTT broker.

    Args:
        ctx: AppContext with mqtt_pub_queue, mqtt_pub_connected, shutdown_event
        config: MqttPublishConfig with host, port, topic_prefix, client_id, interval_s
        inverters: Optional list of InverterEntry objects for HA discovery
        virtual_name: Optional virtual inverter name for HA discovery
    """
    queue = ctx.mqtt_pub_queue
    backoff = 1.0
    max_backoff = 30.0

    while not ctx.shutdown_event.is_set():
        try:
            will = aiomqtt.Will(
                topic=f"{config.topic_prefix}/status",
                payload="offline",
                qos=1,
                retain=True,
            )
            async with aiomqtt.Client(
                hostname=config.host,
                port=config.port,
                identifier=config.client_id,
                will=will,
                keepalive=30,
            ) as client:
                # Announce online (per D-06)
                await client.publish(
                    f"{config.topic_prefix}/status",
                    payload="online",
                    qos=1,
                    retain=True,
                )
                ctx.mqtt_pub_connected = True
                backoff = 1.0  # reset on successful connect
                log.info("mqtt_pub_connected", host=config.host, port=config.port)

                # Publish HA discovery configs once on connect (per D-13)
                if inverters:
                    from pv_inverter_proxy.mqtt_payloads import (
                        ha_discovery_configs,
                        ha_discovery_topic,
                        virtual_ha_discovery_configs,
                    )
                    for inv in inverters:
                        if not inv.enabled:
                            continue
                        configs = ha_discovery_configs(inv.id, config.topic_prefix, inv)
                        for idx, disc_cfg in enumerate(configs):
                            # Use ha_discovery_topic to generate topic from field key
                            from pv_inverter_proxy.mqtt_payloads import SENSOR_DEFS
                            field_key = SENSOR_DEFS[idx][1]
                            topic = ha_discovery_topic(inv.id, field_key)
                            await client.publish(
                                topic,
                                payload=json.dumps(disc_cfg),
                                qos=1,
                                retain=True,
                            )
                        # Device availability
                        await client.publish(
                            f"{config.topic_prefix}/device/{inv.id}/availability",
                            payload="online",
                            qos=1,
                            retain=True,
                        )
                    # Virtual device discovery
                    if virtual_name:
                        v_configs = virtual_ha_discovery_configs(
                            config.topic_prefix, virtual_name
                        )
                        for disc_cfg in v_configs:
                            field_key = disc_cfg.get("value_template", "").split(".")[-1].rstrip(" }}")
                            topic = ha_discovery_topic("virtual", field_key)
                            await client.publish(
                                topic,
                                payload=json.dumps(disc_cfg),
                                qos=1,
                                retain=True,
                            )
                        await client.publish(
                            f"{config.topic_prefix}/virtual/availability",
                            payload="online",
                            qos=1,
                            retain=True,
                        )

                    log.info("mqtt_ha_discovery_published",
                             devices=len([i for i in inverters if i.enabled]),
                             virtual=bool(virtual_name))

                # Consume from queue, throttle to interval_s, publish latest per key
                last_published: dict[str, str] = {}  # last JSON sent per topic key
                pending: dict[str, dict] = {}        # latest msg per topic key
                next_publish = time.monotonic()

                def _store(m):
                    mt = m.get("type")
                    if mt == "device":
                        pending[f"device:{m['device_id']}"] = m
                    elif mt == "virtual":
                        pending["virtual"] = m
                    else:
                        # Legacy format: topic + payload (no throttling)
                        pending[f"legacy:{id(m)}"] = m

                while not ctx.shutdown_event.is_set():
                    # Wait for queue message or publish window, whichever first
                    now = time.monotonic()
                    wait = max(0.01, next_publish - now)
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=wait)
                        _store(msg)
                    except asyncio.TimeoutError:
                        pass

                    # Drain any buffered messages
                    while not queue.empty():
                        try:
                            _store(queue.get_nowait())
                        except asyncio.QueueEmpty:
                            break

                    if time.monotonic() < next_publish or not pending:
                        continue

                    # Publish all pending messages
                    for key, pmsg in pending.items():
                        msg_type = pmsg.get("type")

                        if msg_type == "device":
                            from pv_inverter_proxy.mqtt_payloads import device_payload
                            payload = device_payload(pmsg["snapshot"], device_name=pmsg.get("device_name", ""))
                            payload_json = json.dumps(payload, separators=(",", ":"))
                            device_id = pmsg["device_id"]

                            if last_published.get(key) == payload_json:
                                ctx.mqtt_pub_skipped += 1
                                continue

                            last_published[key] = payload_json
                            topic = f"{config.topic_prefix}/device/{device_id}/state"
                            await client.publish(topic, payload=payload_json, qos=0, retain=True)
                            ctx.mqtt_pub_messages += 1
                            ctx.mqtt_pub_bytes += len(payload_json)
                            ctx.mqtt_pub_last_ts = time.time()

                        elif msg_type == "virtual":
                            from pv_inverter_proxy.mqtt_payloads import virtual_payload
                            payload = virtual_payload(pmsg["virtual_data"])
                            payload_json = json.dumps(payload, separators=(",", ":"))

                            if last_published.get(key) == payload_json:
                                ctx.mqtt_pub_skipped += 1
                                continue

                            last_published[key] = payload_json
                            topic = f"{config.topic_prefix}/virtual/state"
                            await client.publish(topic, payload=payload_json, qos=0, retain=True)
                            ctx.mqtt_pub_messages += 1
                            ctx.mqtt_pub_bytes += len(payload_json)
                            ctx.mqtt_pub_last_ts = time.time()

                        else:
                            # Legacy format: topic + payload
                            topic = pmsg.get("topic", "")
                            lpayload = pmsg.get("payload", {})
                            await client.publish(topic, payload=json.dumps(lpayload), qos=0)

                    pending.clear()
                    next_publish = time.monotonic() + config.interval_s

        except aiomqtt.MqttError as e:
            ctx.mqtt_pub_connected = False
            log.warning("mqtt_pub_disconnected", error=str(e), backoff=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
        except asyncio.CancelledError:
            break

    ctx.mqtt_pub_connected = False
    log.info("mqtt_pub_stopped")
