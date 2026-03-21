"""Tests for PowerLimitDistributor: waterfall, dead-time, monitoring-only, offline."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from venus_os_fronius_proxy.config import Config, InverterEntry
from venus_os_fronius_proxy.connection import ConnectionState
from venus_os_fronius_proxy.distributor import DeviceLimitState, PowerLimitDistributor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    device_id: str = "dev1",
    rated_power: int = 30000,
    throttle_order: int = 1,
    throttle_enabled: bool = True,
    throttle_dead_time_s: float = 0.0,
    enabled: bool = True,
) -> InverterEntry:
    return InverterEntry(
        id=device_id,
        host="10.0.0.1",
        rated_power=rated_power,
        throttle_order=throttle_order,
        throttle_enabled=throttle_enabled,
        throttle_dead_time_s=throttle_dead_time_s,
        enabled=enabled,
    )


def _make_plugin() -> AsyncMock:
    """Create a mock InverterPlugin with write_power_limit."""
    plugin = AsyncMock()
    plugin.write_power_limit = AsyncMock(
        return_value=MagicMock(success=True, error=None)
    )
    return plugin


def _make_conn_mgr(state: ConnectionState = ConnectionState.CONNECTED) -> MagicMock:
    mgr = MagicMock()
    mgr.state = state
    return mgr


def _make_device_state(plugin=None, conn_mgr=None):
    """Create a minimal DeviceState-like object."""
    from venus_os_fronius_proxy.context import DeviceState
    ds = DeviceState()
    ds.plugin = plugin or _make_plugin()
    ds.conn_mgr = conn_mgr or _make_conn_mgr()
    return ds


def _build_distributor(
    entries: list[tuple[str, int, int, bool, float]],
    conn_states: dict[str, ConnectionState] | None = None,
) -> tuple[PowerLimitDistributor, dict[str, AsyncMock]]:
    """Build a distributor with given devices.

    entries: list of (device_id, rated_power, throttle_order, throttle_enabled, dead_time_s)
    Returns (distributor, {device_id: plugin_mock})
    """
    conn_states = conn_states or {}
    inverter_entries = []
    plugins = {}

    for dev_id, rated, to, te, dt in entries:
        entry = _make_entry(
            device_id=dev_id,
            rated_power=rated,
            throttle_order=to,
            throttle_enabled=te,
            throttle_dead_time_s=dt,
        )
        inverter_entries.append(entry)
        plugins[dev_id] = _make_plugin()

    config = Config(inverters=inverter_entries)

    # Build a mock registry with _managed dict
    from venus_os_fronius_proxy.context import AppContext
    app_ctx = AppContext()

    for dev_id, rated, to, te, dt in entries:
        entry = next(e for e in inverter_entries if e.id == dev_id)
        cs = conn_states.get(dev_id, ConnectionState.CONNECTED)
        ds = _make_device_state(plugin=plugins[dev_id], conn_mgr=_make_conn_mgr(cs))
        app_ctx.devices[dev_id] = ds

    # Build mock registry
    registry = MagicMock()
    managed = {}
    for dev_id in plugins:
        entry = next(e for e in inverter_entries if e.id == dev_id)
        ds = app_ctx.devices[dev_id]
        md = MagicMock()
        md.entry = entry
        md.plugin = plugins[dev_id]
        md.device_state = ds
        managed[dev_id] = md
    registry._managed = managed

    distributor = PowerLimitDistributor(registry=registry, config=config)
    return distributor, plugins


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_waterfall_to_ordering():
    """TO1 throttled first; TO2 stays at 100% when budget consumed by TO1."""
    # SE30K (TO1, 30kW) + HM800 (TO2, 800W) = 30800W total
    # 50% limit = 15400W allowed
    # TO1: min(30000, 15400) = 15400W -> 51.33%. Remaining = 0.
    # TO2: remaining = 0 -> 0%
    dist, plugins = _build_distributor([
        ("se30k", 30000, 1, True, 0.0),
        ("hm800", 800, 2, True, 0.0),
    ])

    await dist.distribute(50.0, enable=True)

    # SE30K should be throttled (around 51.33%)
    se_call = plugins["se30k"].write_power_limit
    se_call.assert_called_once()
    _, call_kwargs = se_call.call_args
    if not call_kwargs:
        call_args = se_call.call_args[0]
        assert call_args[0] is True  # enable
        assert abs(call_args[1] - 51.33) < 0.5  # ~51.33%
    else:
        assert abs(call_kwargs.get("limit_pct", se_call.call_args[0][1]) - 51.33) < 0.5

    # HM800 should get 0%
    hm_call = plugins["hm800"].write_power_limit
    hm_call.assert_called_once()
    hm_args = hm_call.call_args[0]
    assert hm_args[0] is True
    assert abs(hm_args[1] - 0.0) < 0.01


@pytest.mark.asyncio
async def test_same_to_equal_split():
    """Two devices with same TO split remaining budget equally."""
    # SE30K (TO1, 30kW) + HM-A (TO2, 800W) + HM-B (TO2, 800W) = 31600W
    # 97% limit = 30652W
    # TO1: min(30000, 30652) = 30000 -> 100%. Remaining = 652.
    # TO2: 652W / 2 devices = 326W each -> 326/800 = 40.75%
    dist, plugins = _build_distributor([
        ("se30k", 30000, 1, True, 0.0),
        ("hm_a", 800, 2, True, 0.0),
        ("hm_b", 800, 2, True, 0.0),
    ])

    await dist.distribute(97.0, enable=True)

    # SE30K at 100%
    se_args = plugins["se30k"].write_power_limit.call_args[0]
    assert abs(se_args[1] - 100.0) < 0.01

    # Both HM at ~40.75%
    hm_a_args = plugins["hm_a"].write_power_limit.call_args[0]
    hm_b_args = plugins["hm_b"].write_power_limit.call_args[0]
    assert abs(hm_a_args[1] - 40.75) < 0.5
    assert abs(hm_b_args[1] - 40.75) < 0.5


@pytest.mark.asyncio
async def test_monitoring_only_excluded():
    """Device with throttle_enabled=False gets no write_power_limit call."""
    dist, plugins = _build_distributor([
        ("se30k", 30000, 1, True, 0.0),
        ("monitor", 5000, 2, False, 0.0),  # monitoring-only
        ("hm800", 800, 3, True, 0.0),
    ])

    await dist.distribute(50.0, enable=True)

    # Monitor device: NO call
    plugins["monitor"].write_power_limit.assert_not_called()

    # SE30K and HM800 should have been called
    plugins["se30k"].write_power_limit.assert_called_once()
    plugins["hm800"].write_power_limit.assert_called_once()


@pytest.mark.asyncio
async def test_dead_time_buffering():
    """Second call within dead-time buffers (not sent immediately)."""
    dist, plugins = _build_distributor([
        ("dev1", 10000, 1, True, 5.0),  # 5s dead-time
    ])

    # First call goes through
    await dist.distribute(80.0, enable=True)
    assert plugins["dev1"].write_power_limit.call_count == 1

    # Second call within dead-time: should NOT result in another write
    await dist.distribute(60.0, enable=True)
    assert plugins["dev1"].write_power_limit.call_count == 1  # still 1


@pytest.mark.asyncio
async def test_dead_time_flush():
    """After dead-time expires, buffered value is sent."""
    dist, plugins = _build_distributor([
        ("dev1", 10000, 1, True, 0.5),  # 0.5s dead-time
    ])

    # First call
    await dist.distribute(80.0, enable=True)
    assert plugins["dev1"].write_power_limit.call_count == 1

    # Buffer a second call
    await dist.distribute(60.0, enable=True)
    assert plugins["dev1"].write_power_limit.call_count == 1

    # Mock time forward past dead-time
    for ds in dist._device_states.values():
        ds.last_write_ts -= 1.0  # push back by 1s (past 0.5s dead-time)

    # Flush pending
    await dist.flush_pending()
    assert plugins["dev1"].write_power_limit.call_count == 2


@pytest.mark.asyncio
async def test_offline_redistribution():
    """Offline device excluded; share goes to remaining devices."""
    # dev_a (TO1, 10kW, online) + dev_b (TO2, 10kW, OFFLINE) = 20kW total
    # 50% = 10000W allowed
    # dev_b offline -> excluded from waterfall
    # Only dev_a eligible: min(10000, 10000) = 10000 -> 100%
    dist, plugins = _build_distributor(
        [
            ("dev_a", 10000, 1, True, 0.0),
            ("dev_b", 10000, 2, True, 0.0),
        ],
        conn_states={"dev_a": ConnectionState.CONNECTED, "dev_b": ConnectionState.RECONNECTING},
    )

    await dist.distribute(50.0, enable=True)

    # dev_a gets full budget (100%)
    da_args = plugins["dev_a"].write_power_limit.call_args[0]
    assert abs(da_args[1] - 100.0) < 0.01

    # dev_b offline: no write
    plugins["dev_b"].write_power_limit.assert_not_called()


@pytest.mark.asyncio
async def test_disable_sends_100():
    """enable=False sends 100% to all throttle-eligible devices."""
    dist, plugins = _build_distributor([
        ("se30k", 30000, 1, True, 0.0),
        ("hm800", 800, 2, True, 0.0),
        ("monitor", 5000, 3, False, 0.0),  # monitoring-only
    ])

    await dist.distribute(100.0, enable=False)

    # Throttle-eligible get write_power_limit(False, 100.0)
    se_args = plugins["se30k"].write_power_limit.call_args[0]
    assert se_args[0] is False  # enable=False
    assert abs(se_args[1] - 100.0) < 0.01

    hm_args = plugins["hm800"].write_power_limit.call_args[0]
    assert hm_args[0] is False
    assert abs(hm_args[1] - 100.0) < 0.01

    # Monitoring-only: no call
    plugins["monitor"].write_power_limit.assert_not_called()


@pytest.mark.asyncio
async def test_pct_watt_conversion():
    """50% of total rated -> correct per-device percentages."""
    # 3 devices all TO1: 10kW + 20kW + 10kW = 40kW
    # 50% = 20000W. All same TO -> split equally: 20000/3 = 6666.67W each
    # dev_a: 6666.67/10000 = 66.67%, dev_b: 6666.67/20000 = 33.33%, dev_c: 6666.67/10000 = 66.67%
    dist, plugins = _build_distributor([
        ("dev_a", 10000, 1, True, 0.0),
        ("dev_b", 20000, 1, True, 0.0),
        ("dev_c", 10000, 1, True, 0.0),
    ])

    await dist.distribute(50.0, enable=True)

    da_args = plugins["dev_a"].write_power_limit.call_args[0]
    db_args = plugins["dev_b"].write_power_limit.call_args[0]
    dc_args = plugins["dev_c"].write_power_limit.call_args[0]

    assert abs(da_args[1] - 66.67) < 0.5
    assert abs(db_args[1] - 33.33) < 0.5
    assert abs(dc_args[1] - 66.67) < 0.5


@pytest.mark.asyncio
async def test_rated_power_zero_excluded():
    """Device with rated_power=0 is excluded from throttle eligibility."""
    dist, plugins = _build_distributor([
        ("known", 10000, 1, True, 0.0),
        ("unknown", 0, 2, True, 0.0),  # rated_power=0
    ])

    await dist.distribute(50.0, enable=True)

    # "known" should be called
    plugins["known"].write_power_limit.assert_called_once()
    # "unknown" should NOT be called (excluded)
    plugins["unknown"].write_power_limit.assert_not_called()
