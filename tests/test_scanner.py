"""Tests for network scanner module -- TCP port probing and SunSpec verification."""
from __future__ import annotations

import asyncio
from ipaddress import IPv4Network
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from venus_os_fronius_proxy.sunspec_models import encode_string
from venus_os_fronius_proxy.scanner import (
    ScanConfig,
    DiscoveredDevice,
    decode_string,
    detect_subnet,
    _probe_port,
    _verify_sunspec,
    scan_subnet,
)


def _make_mock_response(registers, is_error=False):
    """Create a mock Modbus response."""
    resp = MagicMock()
    resp.isError.return_value = is_error
    resp.registers = registers
    return resp


def _build_common_block(
    manufacturer="SolarEdge",
    model="SE30K",
    firmware="4.18.32",
    serial="7E1234AB",
):
    """Build 67 registers for a SunSpec Common Block."""
    regs = [0] * 67
    regs[0] = 1    # DID
    regs[1] = 65   # Length
    regs[2:18] = encode_string(manufacturer, 16)
    regs[18:34] = encode_string(model, 16)
    # regs[34:42] = options (zeros is fine)
    regs[42:50] = encode_string(firmware, 8)
    regs[50:66] = encode_string(serial, 16)
    # regs[66] = device address (0 is fine)
    return regs


# ── ScanConfig ──────────────────────────────────────────────────

class TestScanConfig:
    def test_scan_config_defaults(self):
        cfg = ScanConfig()
        assert cfg.ports == [502, 1502]
        assert cfg.tcp_timeout == 0.5
        assert cfg.modbus_timeout == 2.0
        assert cfg.concurrency == 15
        assert cfg.scan_unit_ids == [1]
        assert cfg.skip_ips == set()

    def test_scan_config_custom(self):
        cfg = ScanConfig(ports=[502], concurrency=10)
        assert cfg.ports == [502]
        assert cfg.concurrency == 10


# ── DiscoveredDevice ────────────────────────────────────────────

class TestDiscoveredDevice:
    def test_discovered_device_fields(self):
        dev = DiscoveredDevice(
            ip="192.168.3.18",
            port=1502,
            unit_id=1,
            manufacturer="SolarEdge",
            model="SE30K",
            serial_number="ABC123",
            firmware_version="4.18.32",
        )
        assert dev.ip == "192.168.3.18"
        assert dev.port == 1502
        assert dev.unit_id == 1
        assert dev.manufacturer == "SolarEdge"
        assert dev.model == "SE30K"
        assert dev.serial_number == "ABC123"
        assert dev.firmware_version == "4.18.32"
        assert dev.supported is True  # computed

    def test_supported_flag_solaredge(self):
        dev = DiscoveredDevice(
            ip="10.0.0.1", port=502, unit_id=1,
            manufacturer="SolarEdge", model="SE30K",
            serial_number="X", firmware_version="1.0",
        )
        assert dev.supported is True

    def test_supported_flag_other(self):
        dev = DiscoveredDevice(
            ip="10.0.0.2", port=502, unit_id=1,
            manufacturer="Fronius", model="Symo",
            serial_number="Y", firmware_version="2.0",
        )
        assert dev.supported is False


# ── decode_string ───────────────────────────────────────────────

class TestDecodeString:
    def test_decode_ascii(self):
        assert decode_string([0x4142, 0x4344]) == "ABCD"

    def test_decode_null_padded(self):
        assert decode_string([0x4142, 0x0000]) == "AB"

    def test_decode_empty(self):
        assert decode_string([0x0000]) == ""


# ── detect_subnet ──────────────────────────────────────────────

class TestDetectSubnet:
    def _ip_json(self, interfaces):
        """Build JSON output like `ip -j -4 addr show`."""
        import json
        result = []
        for name, ip, prefix in interfaces:
            result.append({
                "ifname": name,
                "addr_info": [{"local": ip, "prefixlen": prefix}],
            })
        return json.dumps(result)

    @patch("venus_os_fronius_proxy.scanner.subprocess.run")
    def test_detect_subnet_single_interface(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=self._ip_json([("eth0", "192.168.3.191", 24)]),
            returncode=0,
        )
        result = detect_subnet()
        assert result == IPv4Network("192.168.3.0/24")

    @patch("venus_os_fronius_proxy.scanner.subprocess.run")
    def test_detect_subnet_skips_loopback(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=self._ip_json([
                ("lo", "127.0.0.1", 8),
                ("eth0", "192.168.3.191", 24),
            ]),
            returncode=0,
        )
        result = detect_subnet()
        assert result == IPv4Network("192.168.3.0/24")

    @patch("venus_os_fronius_proxy.scanner.subprocess.run")
    def test_detect_subnet_skips_link_local(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=self._ip_json([
                ("avahi", "169.254.1.1", 16),
                ("eth0", "192.168.3.191", 24),
            ]),
            returncode=0,
        )
        result = detect_subnet()
        assert result == IPv4Network("192.168.3.0/24")

    @patch("venus_os_fronius_proxy.scanner.subprocess.run")
    def test_detect_subnet_no_interface(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=self._ip_json([("lo", "127.0.0.1", 8)]),
            returncode=0,
        )
        with pytest.raises(RuntimeError):
            detect_subnet()


# ── _probe_port ─────────────────────────────────────────────────

class TestProbePort:
    @pytest.mark.asyncio
    async def test_probe_port_open(self):
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        with patch("venus_os_fronius_proxy.scanner.asyncio.open_connection",
                    new_callable=AsyncMock, return_value=(MagicMock(), mock_writer)):
            result = await _probe_port("192.168.3.18", 502, 0.5)
        assert result is True

    @pytest.mark.asyncio
    async def test_probe_port_closed(self):
        with patch("venus_os_fronius_proxy.scanner.asyncio.open_connection",
                    new_callable=AsyncMock, side_effect=OSError("refused")):
            result = await _probe_port("192.168.3.18", 502, 0.5)
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_port_timeout(self):
        with patch("venus_os_fronius_proxy.scanner.asyncio.open_connection",
                    new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
            result = await _probe_port("192.168.3.18", 502, 0.5)
        assert result is False


# ── _verify_sunspec ─────────────────────────────────────────────

class TestVerifySunSpec:
    @pytest.mark.asyncio
    async def test_verify_sunspec_valid(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.close = MagicMock()
        # First call: SunSpec header
        header_resp = _make_mock_response([0x5375, 0x6E53])
        # Second call: Common Block
        common_resp = _make_mock_response(_build_common_block())
        mock_client.read_holding_registers = AsyncMock(
            side_effect=[header_resp, common_resp]
        )
        with patch("venus_os_fronius_proxy.scanner.AsyncModbusTcpClient",
                    return_value=mock_client):
            result = await _verify_sunspec("192.168.3.18", 1502, 1, 2.0)
        assert result is not None
        assert result.manufacturer == "SolarEdge"
        assert result.model == "SE30K"
        assert result.serial_number == "7E1234AB"
        assert result.firmware_version == "4.18.32"
        assert result.supported is True

    @pytest.mark.asyncio
    async def test_verify_sunspec_no_magic(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.close = MagicMock()
        header_resp = _make_mock_response([0x0000, 0x0000])
        mock_client.read_holding_registers = AsyncMock(return_value=header_resp)
        with patch("venus_os_fronius_proxy.scanner.AsyncModbusTcpClient",
                    return_value=mock_client):
            result = await _verify_sunspec("192.168.3.18", 1502, 1, 2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_sunspec_read_error(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.close = MagicMock()
        error_resp = _make_mock_response([], is_error=True)
        mock_client.read_holding_registers = AsyncMock(return_value=error_resp)
        with patch("venus_os_fronius_proxy.scanner.AsyncModbusTcpClient",
                    return_value=mock_client):
            result = await _verify_sunspec("192.168.3.18", 1502, 1, 2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_sunspec_connection_fail(self):
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=Exception("connection refused"))
        mock_client.close = MagicMock()
        with patch("venus_os_fronius_proxy.scanner.AsyncModbusTcpClient",
                    return_value=mock_client):
            result = await _verify_sunspec("192.168.3.18", 1502, 1, 2.0)
        assert result is None


# ── scan_subnet ─────────────────────────────────────────────────

class TestScanSubnet:
    @pytest.mark.asyncio
    async def test_scan_subnet_skips_configured_ips(self):
        cfg = ScanConfig(skip_ips={"192.168.3.18"})
        subnet = IPv4Network("192.168.3.0/30")  # Only .1, .2 (network .0, broadcast .3)

        with patch("venus_os_fronius_proxy.scanner.detect_subnet", return_value=subnet), \
             patch("venus_os_fronius_proxy.scanner._probe_port",
                   new_callable=AsyncMock, return_value=False) as mock_probe:
            result = await scan_subnet(cfg)

        # 192.168.3.18 is not in /30 anyway, but if it were, it should be skipped
        probed_ips = {call.args[0] for call in mock_probe.call_args_list}
        assert "192.168.3.18" not in probed_ips
        assert result == []

    @pytest.mark.asyncio
    async def test_scan_subnet_returns_devices(self):
        cfg = ScanConfig(ports=[1502])
        subnet = IPv4Network("192.168.3.0/30")  # hosts: .1, .2

        device = DiscoveredDevice(
            ip="192.168.3.1", port=1502, unit_id=1,
            manufacturer="SolarEdge", model="SE30K",
            serial_number="ABC", firmware_version="1.0",
        )

        async def mock_probe(ip, port, timeout):
            return ip == "192.168.3.1"

        async def mock_verify(ip, port, unit_id, timeout):
            if ip == "192.168.3.1":
                return device
            return None

        with patch("venus_os_fronius_proxy.scanner.detect_subnet", return_value=subnet), \
             patch("venus_os_fronius_proxy.scanner._probe_port", side_effect=mock_probe), \
             patch("venus_os_fronius_proxy.scanner._verify_sunspec", side_effect=mock_verify):
            result = await scan_subnet(cfg)

        assert len(result) == 1
        assert result[0].ip == "192.168.3.1"

    @pytest.mark.asyncio
    async def test_scan_subnet_empty_network(self):
        cfg = ScanConfig()
        subnet = IPv4Network("10.0.0.0/30")

        with patch("venus_os_fronius_proxy.scanner.detect_subnet", return_value=subnet), \
             patch("venus_os_fronius_proxy.scanner._probe_port",
                   new_callable=AsyncMock, return_value=False):
            result = await scan_subnet(cfg)

        assert result == []
