"""Tests for AppContext and DeviceState dataclasses."""
from __future__ import annotations


def test_app_context_defaults():
    """AppContext() creates with sensible defaults."""
    from venus_os_fronius_proxy.context import AppContext

    ctx = AppContext()
    assert ctx.cache is None
    assert ctx.control_state is None
    assert ctx.config is None
    assert ctx.config_path == ""
    assert ctx.devices == {}
    assert ctx.venus_mqtt_connected is False
    assert ctx.venus_os_detected is False
    assert ctx.polling_paused is False
    assert ctx.webapp is None
    assert ctx.override_log is None
    assert ctx.primary_device is None


def test_device_state_creation():
    """DeviceState() creates empty state with correct defaults."""
    from venus_os_fronius_proxy.context import DeviceState

    ds = DeviceState()
    assert ds.collector is None
    assert ds.poll_counter == {"success": 0, "total": 0}
    assert ds.conn_mgr is None
    assert ds.last_poll_data is None
    assert ds.plugin is None


def test_app_context_primary_device():
    """Adding a DeviceState to devices dict, primary_device returns it."""
    from venus_os_fronius_proxy.context import AppContext, DeviceState

    ctx = AppContext()
    ds = DeviceState()
    ctx.devices["dev1"] = ds

    assert ctx.primary_device is ds


def test_app_context_compat_accessors():
    """dashboard_collector, conn_mgr, poll_counter proxy to primary device."""
    from venus_os_fronius_proxy.context import AppContext, DeviceState

    ctx = AppContext()
    collector_mock = object()
    conn_mgr_mock = object()
    ds = DeviceState(
        collector=collector_mock,
        conn_mgr=conn_mgr_mock,
        poll_counter={"success": 5, "total": 10},
        last_poll_data={"test": True},
    )
    ctx.devices["dev1"] = ds

    assert ctx.dashboard_collector is collector_mock
    assert ctx.conn_mgr is conn_mgr_mock
    assert ctx.poll_counter == {"success": 5, "total": 10}
    assert ctx.last_poll_data == {"test": True}

    # Test last_poll_data setter
    ctx.last_poll_data = {"new": True}
    assert ds.last_poll_data == {"new": True}


def test_app_context_compat_no_device():
    """Compat accessors return sensible defaults when no device exists."""
    from venus_os_fronius_proxy.context import AppContext

    ctx = AppContext()
    assert ctx.dashboard_collector is None
    assert ctx.conn_mgr is None
    assert ctx.poll_counter == {"success": 0, "total": 0}
    assert ctx.last_poll_data is None
