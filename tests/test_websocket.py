"""Tests for WebSocket push infrastructure (/ws endpoint)."""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from pymodbus.datastore import ModbusSequentialDataBlock

from venus_os_fronius_proxy.connection import ConnectionManager
from venus_os_fronius_proxy.dashboard import DashboardCollector, _PB_OFFSET
from venus_os_fronius_proxy.register_cache import RegisterCache
from venus_os_fronius_proxy.sunspec_models import build_initial_registers, DATABLOCK_START
from venus_os_fronius_proxy.timeseries import TimeSeriesBuffer
from venus_os_fronius_proxy.webapp import broadcast_to_clients, ws_handler


def _make_cache_with_values(overrides: dict[int, int | list[int]] | None = None) -> RegisterCache:
    """Build a RegisterCache with known register values."""
    initial_values = build_initial_registers()
    datablock = ModbusSequentialDataBlock(DATABLOCK_START, initial_values)
    cache = RegisterCache(datablock, staleness_timeout=30.0)
    cache.last_successful_poll = time.monotonic()
    cache._has_been_updated = True

    if overrides:
        for addr, val in overrides.items():
            if isinstance(val, list):
                datablock.setValues(addr + _PB_OFFSET, val)
            else:
                datablock.setValues(addr + _PB_OFFSET, [val])
    return cache


def _make_collector_with_snapshot() -> DashboardCollector:
    """Create a DashboardCollector with one collect() call so last_snapshot is set."""
    collector = DashboardCollector()
    cache = _make_cache_with_values({
        40071: 1820, 40075: 65535,  # AC Current, SF=-1
        40079: 2301, 40082: 65535,  # AC Voltage AN, SF=-1
        40083: 12450, 40084: 65534,  # AC Power, SF=-2
        40085: 5001, 40086: 65534,  # AC Freq, SF=-2
        40103: 382, 40106: 65535,  # Sink Temp, SF=-1
        40107: 4,  # Status=MPPT
        40093: [0, 21543200], 40095: 0,  # Energy
        40088: 0, 40090: 0, 40092: 0,
        40097: 0, 40099: 0, 40101: 0,
    })
    conn_mgr = ConnectionManager(poll_interval=1.0)
    poll_counter = {"success": 50, "total": 55}
    collector.collect(cache, conn_mgr=conn_mgr, poll_counter=poll_counter)
    return collector


@pytest.fixture
async def ws_client():
    """Create an aiohttp test client with the ws_handler route and shared_ctx."""
    collector = _make_collector_with_snapshot()

    app = web.Application()
    app["shared_ctx"] = {"dashboard_collector": collector}
    app["ws_clients"] = set()
    app.router.add_get("/ws", ws_handler)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


@pytest.fixture
async def ws_client_with_history():
    """Create a test client with a DashboardCollector that has 100 ac_power_w samples."""
    collector = _make_collector_with_snapshot()
    # Populate 100 samples in ac_power_w buffer
    buf = collector._buffers["ac_power_w"]
    # Clear existing (from collect call above) and add 100 known samples
    buf._buf.clear()
    for i in range(100):
        buf.append(float(i * 10), ts=1000.0 + i)

    app = web.Application()
    app["shared_ctx"] = {"dashboard_collector": collector}
    app["ws_clients"] = set()
    app.router.add_get("/ws", ws_handler)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


async def test_ws_connect_receives_snapshot(ws_client):
    """Connect to /ws, first message is JSON with type=snapshot containing inverter and connection."""
    async with ws_client.ws_connect("/ws") as ws:
        msg = await ws.receive_json()
        assert msg["type"] == "snapshot"
        assert "inverter" in msg["data"]
        assert "connection" in msg["data"]


async def test_ws_connect_receives_history(ws_client_with_history):
    """Connect to /ws, second message is history with downsampled ac_power_w."""
    async with ws_client_with_history.ws_connect("/ws") as ws:
        # First message is snapshot
        _snapshot = await ws.receive_json()
        assert _snapshot["type"] == "snapshot"

        # Second message is history
        msg = await ws.receive_json()
        assert msg["type"] == "history"
        assert "ac_power_w" in msg["data"]
        # 100 samples with step 10 = 10 data points
        points = msg["data"]["ac_power_w"]
        assert len(points) == 10
        # Each point is [timestamp, value]
        assert len(points[0]) == 2


async def test_broadcast_to_multiple_clients(ws_client):
    """Two WS clients both receive broadcast snapshot."""
    async with ws_client.ws_connect("/ws") as ws1, ws_client.ws_connect("/ws") as ws2:
        # Drain initial snapshot+history messages
        await ws1.receive_json()  # snapshot
        await ws1.receive_json()  # history
        await ws2.receive_json()  # snapshot
        await ws2.receive_json()  # history

        # Broadcast a new snapshot
        test_snapshot = {"ts": 12345, "inverter": {"ac_power_w": 999}, "connection": {}}
        await broadcast_to_clients(ws_client.app, test_snapshot)

        msg1 = await ws1.receive_json()
        msg2 = await ws2.receive_json()
        assert msg1["type"] == "snapshot"
        assert msg1["data"]["inverter"]["ac_power_w"] == 999
        assert msg2["type"] == "snapshot"
        assert msg2["data"]["inverter"]["ac_power_w"] == 999


async def test_dead_client_cleanup(ws_client):
    """Closing a WS client then broadcasting does not raise errors."""
    async with ws_client.ws_connect("/ws") as ws:
        await ws.receive_json()  # snapshot
        await ws.receive_json()  # history

    # ws is now closed; broadcast should not raise
    test_snapshot = {"ts": 12345, "inverter": {}, "connection": {}}
    await broadcast_to_clients(ws_client.app, test_snapshot)
    # No exception means success; dead client was cleaned up


async def test_ws_handler_no_collector():
    """Connect to /ws when shared_ctx has no dashboard_collector -- no crash."""
    app = web.Application()
    app["shared_ctx"] = {}  # No dashboard_collector
    app["ws_clients"] = set()
    app.router.add_get("/ws", ws_handler)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        async with client.ws_connect("/ws") as ws:
            # Should connect without crash; no messages expected
            # Close from client side
            await ws.close()
    finally:
        await client.close()
