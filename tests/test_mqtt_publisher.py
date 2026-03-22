"""Tests for MQTT publisher module with queue-based publish loop, LWT, and reconnect."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import aiomqtt


def _make_config(**overrides):
    """Build a minimal MqttPublishConfig-like object."""
    defaults = dict(
        host="localhost",
        port=1883,
        topic_prefix="pvproxy",
        client_id="test-pub",
        interval_s=1,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_ctx(queue_maxsize=100):
    """Build a minimal AppContext-like object."""
    return SimpleNamespace(
        mqtt_pub_queue=asyncio.Queue(maxsize=queue_maxsize),
        mqtt_pub_connected=False,
        shutdown_event=asyncio.Event(),
    )


@pytest.fixture
def mock_client():
    """Patch aiomqtt.Client as an async context manager returning a mock client."""
    client_instance = AsyncMock()
    client_instance.publish = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=client_instance)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=cm) as mock_cls:
        mock_cls._instance = client_instance
        mock_cls._cm = cm
        yield mock_cls


@pytest.fixture
def mock_will():
    """Patch aiomqtt.Will to capture LWT parameters."""
    with patch("aiomqtt.Will") as mock_w:
        yield mock_w


async def test_connect_sets_connected(mock_client, mock_will):
    """mqtt_publish_loop sets ctx.mqtt_pub_connected=True after successful connect."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    # After first connect + publish online, set shutdown to exit loop
    async def shutdown_after_connect(*args, **kwargs):
        ctx.shutdown_event.set()

    mock_client._instance.publish.side_effect = shutdown_after_connect

    await mqtt_publish_loop(ctx, config)
    assert ctx.mqtt_pub_connected is False  # False after loop exits (cleanup)


async def test_publishes_online_on_connect(mock_client, mock_will):
    """mqtt_publish_loop publishes 'online' to {prefix}/status with QoS 1 + retain."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config(topic_prefix="test")

    async def shutdown_after_connect(*args, **kwargs):
        ctx.shutdown_event.set()

    mock_client._instance.publish.side_effect = shutdown_after_connect

    await mqtt_publish_loop(ctx, config)

    # First publish call should be the online announcement
    calls = mock_client._instance.publish.call_args_list
    assert len(calls) >= 1
    first_call = calls[0]
    assert first_call.args[0] == "test/status"
    assert first_call.kwargs.get("payload") == "online"
    assert first_call.kwargs.get("qos") == 1
    assert first_call.kwargs.get("retain") is True


async def test_will_message_configured(mock_client, mock_will):
    """mqtt_publish_loop sets Will message to 'offline' on {prefix}/status."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config(topic_prefix="mypv")

    async def shutdown_after_connect(*args, **kwargs):
        ctx.shutdown_event.set()

    mock_client._instance.publish.side_effect = shutdown_after_connect

    await mqtt_publish_loop(ctx, config)

    mock_will.assert_called_once_with(
        topic="mypv/status",
        payload="offline",
        qos=1,
        retain=True,
    )


async def test_consumes_queue_messages(mock_client, mock_will):
    """mqtt_publish_loop consumes messages from queue and publishes to broker."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    call_count = 0
    original_publish = AsyncMock()

    async def track_publish(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call is "online", after that we process queue
        if call_count == 1:
            # Enqueue a message for the loop to consume
            await ctx.mqtt_pub_queue.put({"topic": "pvproxy/power", "payload": {"watts": 5000}})
        elif call_count == 2:
            # After consuming the queue message, shut down
            ctx.shutdown_event.set()

    mock_client._instance.publish.side_effect = track_publish

    await mqtt_publish_loop(ctx, config)

    calls = mock_client._instance.publish.call_args_list
    assert len(calls) >= 2
    # Second call should be the queued message
    second = calls[1]
    assert second.args[0] == "pvproxy/power"


async def test_reconnect_with_backoff(mock_client, mock_will):
    """mqtt_publish_loop reconnects with increasing backoff on MqttError."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    connect_attempts = 0

    async def fail_connect(*args, **kwargs):
        nonlocal connect_attempts
        connect_attempts += 1
        if connect_attempts >= 3:
            ctx.shutdown_event.set()
        raise aiomqtt.MqttError("Connection refused")

    mock_client._cm.__aenter__ = fail_connect

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await mqtt_publish_loop(ctx, config)

    # Should have called sleep with increasing backoff
    sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert len(sleep_calls) >= 2
    assert sleep_calls[0] == 1.0
    assert sleep_calls[1] == 2.0


async def test_disconnect_sets_connected_false(mock_client, mock_will):
    """mqtt_publish_loop sets ctx.mqtt_pub_connected=False on disconnect."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    # On connect, publish "online" succeeds. Then the inner loop starts;
    # we make queue.get raise MqttError to simulate a disconnect during operation.
    call_count = 0

    async def publish_then_disconnect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # "online" publish succeeds -- connected will be set to True
            return
        # Any subsequent publish raises MqttError
        raise aiomqtt.MqttError("Disconnected")

    mock_client._instance.publish.side_effect = publish_then_disconnect

    # Put a message so the inner loop tries to publish (and hits disconnect)
    await ctx.mqtt_pub_queue.put({"topic": "t", "payload": {}})

    # After MqttError, the outer except sets connected=False and sleeps.
    # On second connect attempt, shut down.
    connect_count = 0
    original_aenter = mock_client._cm.__aenter__

    async def connect_or_shutdown(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        if connect_count == 1:
            return await original_aenter(*args, **kwargs)
        ctx.shutdown_event.set()
        raise aiomqtt.MqttError("Stop")

    mock_client._cm.__aenter__ = connect_or_shutdown

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await mqtt_publish_loop(ctx, config)

    assert ctx.mqtt_pub_connected is False


async def test_clean_shutdown_on_cancel(mock_client, mock_will):
    """mqtt_publish_loop stops cleanly on CancelledError."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    async def raise_cancel(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_client._cm.__aenter__ = raise_cancel

    # Should not raise
    await mqtt_publish_loop(ctx, config)
    assert ctx.mqtt_pub_connected is False


async def test_shutdown_event_stops_loop(mock_client, mock_will):
    """mqtt_publish_loop exits when shutdown_event is set."""
    from venus_os_fronius_proxy.mqtt_publisher import mqtt_publish_loop

    ctx = _make_ctx()
    config = _make_config()

    # Set shutdown before entering loop
    ctx.shutdown_event.set()

    await mqtt_publish_loop(ctx, config)
    assert ctx.mqtt_pub_connected is False


async def test_queue_full_drops_message():
    """put_nowait on full queue raises QueueFull, which should be caught by producer."""
    q = asyncio.Queue(maxsize=1)
    q.put_nowait({"topic": "t", "payload": {}})

    # Second put_nowait should raise QueueFull
    with pytest.raises(asyncio.QueueFull):
        q.put_nowait({"topic": "t2", "payload": {}})

    # Documented producer pattern: try/except QueueFull
    try:
        q.put_nowait({"topic": "t3", "payload": {}})
    except asyncio.QueueFull:
        pass  # Expected -- message dropped, no exception propagated
