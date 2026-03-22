"""MQTT publisher with queue-based decoupling, LWT, and exponential backoff reconnect.

Consumes messages from ctx.mqtt_pub_queue and publishes to the configured broker.
Completely independent from venus_reader.py (per D-03).
"""
from __future__ import annotations

import asyncio
import json

import aiomqtt
import structlog

log = structlog.get_logger(component="mqtt_publisher")


async def mqtt_publish_loop(ctx, config) -> None:
    """Background task: consume from queue, publish to MQTT broker.

    Args:
        ctx: AppContext with mqtt_pub_queue, mqtt_pub_connected, shutdown_event
        config: MqttPublishConfig with host, port, topic_prefix, client_id, interval_s
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

                # Consume from queue and publish
                while not ctx.shutdown_event.is_set():
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=config.interval_s)
                        topic = msg["topic"]
                        payload = msg["payload"]
                        await client.publish(topic, payload=json.dumps(payload), qos=0)
                    except asyncio.TimeoutError:
                        pass  # No messages -- loop continues, keepalive handled by aiomqtt

        except aiomqtt.MqttError as e:
            ctx.mqtt_pub_connected = False
            log.warning("mqtt_pub_disconnected", error=str(e), backoff=backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
        except asyncio.CancelledError:
            break

    ctx.mqtt_pub_connected = False
    log.info("mqtt_pub_stopped")
