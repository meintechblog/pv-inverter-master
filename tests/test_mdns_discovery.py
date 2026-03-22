"""Tests for mDNS MQTT broker discovery module."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Module under test -- will be created in GREEN phase
from venus_os_fronius_proxy.mdns_discovery import discover_mqtt_brokers, SERVICE_TYPE


@pytest.mark.asyncio
async def test_discover_empty_scan():
    """discover_mqtt_brokers returns empty list when no brokers found."""
    mock_aiozc = AsyncMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("venus_os_fronius_proxy.mdns_discovery.AsyncZeroconf", return_value=mock_aiozc):
        with patch("venus_os_fronius_proxy.mdns_discovery.AsyncServiceBrowser") as mock_browser_cls:
            mock_browser_cls.return_value = AsyncMock()
            with patch("venus_os_fronius_proxy.mdns_discovery.asyncio.sleep", new_callable=AsyncMock):
                result = await discover_mqtt_brokers(timeout=0.1)

    assert result == []
    mock_aiozc.async_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_finds_broker():
    """discover_mqtt_brokers returns broker info when _mqtt._tcp.local. advertised."""
    mock_aiozc = AsyncMock()
    mock_aiozc.zeroconf = MagicMock()

    def fake_browser(zc, stype, handlers):
        # Simulate a service being added
        for handler in handlers:
            handler(zc, stype, f"Mosquitto.{SERVICE_TYPE}", MagicMock(value=1))  # Added=1
        return AsyncMock()

    mock_info = AsyncMock()
    mock_info.server = "mqtt-master.local."
    mock_info.port = 1883
    mock_info.async_request = AsyncMock()

    with patch("venus_os_fronius_proxy.mdns_discovery.AsyncZeroconf", return_value=mock_aiozc):
        with patch("venus_os_fronius_proxy.mdns_discovery.AsyncServiceBrowser", side_effect=fake_browser):
            with patch("venus_os_fronius_proxy.mdns_discovery.AsyncServiceInfo", return_value=mock_info):
                with patch("venus_os_fronius_proxy.mdns_discovery.asyncio.sleep", new_callable=AsyncMock):
                    result = await discover_mqtt_brokers(timeout=0.1)

    assert len(result) == 1
    assert result[0]["host"] == "mqtt-master.local"
    assert result[0]["port"] == 1883
    assert result[0]["name"] == "Mosquitto"
    mock_aiozc.async_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_calls_close_on_error():
    """async_close is called even when an error occurs during scan."""
    mock_aiozc = AsyncMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("venus_os_fronius_proxy.mdns_discovery.AsyncZeroconf", return_value=mock_aiozc):
        with patch("venus_os_fronius_proxy.mdns_discovery.AsyncServiceBrowser", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                await discover_mqtt_brokers(timeout=0.1)

    mock_aiozc.async_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_respects_timeout():
    """discover_mqtt_brokers passes timeout to asyncio.sleep."""
    mock_aiozc = AsyncMock()
    mock_aiozc.zeroconf = MagicMock()

    with patch("venus_os_fronius_proxy.mdns_discovery.AsyncZeroconf", return_value=mock_aiozc):
        with patch("venus_os_fronius_proxy.mdns_discovery.AsyncServiceBrowser", return_value=AsyncMock()):
            with patch("venus_os_fronius_proxy.mdns_discovery.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await discover_mqtt_brokers(timeout=2.5)

    mock_sleep.assert_awaited_once_with(2.5)


def test_service_type_constant():
    """SERVICE_TYPE is _mqtt._tcp.local."""
    assert SERVICE_TYPE == "_mqtt._tcp.local."
