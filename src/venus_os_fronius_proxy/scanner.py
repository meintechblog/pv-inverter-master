"""Network scanner for discovering SunSpec-compatible inverters on the LAN.

Performs a two-phase scan:
1. TCP port probe -- fast async connection test on Modbus ports
2. SunSpec verification -- reads SunSpec header and Common Block via Modbus

Exports: detect_subnet, scan_subnet, ScanConfig, DiscoveredDevice, decode_string
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from typing import Callable

import structlog
from pymodbus.client import AsyncModbusTcpClient

log = structlog.get_logger()

# SunSpec magic number: "SunS" as two uint16 registers
SUNSPEC_MAGIC = [0x5375, 0x6E53]
SUNSPEC_HEADER_ADDR = 40000
COMMON_BLOCK_ADDR = 40002
COMMON_BLOCK_COUNT = 67  # DID + Length + 65 data registers


def decode_string(registers: list[int]) -> str:
    """Decode uint16 register list to ASCII string, stripping nulls."""
    raw = b"".join(r.to_bytes(2, "big") for r in registers)
    return raw.decode("ascii", errors="replace").rstrip("\x00").strip()


@dataclass
class ScanConfig:
    """Configuration for network scan."""

    ports: list[int] = field(default_factory=lambda: [502, 1502])
    tcp_timeout: float = 0.5
    modbus_timeout: float = 2.0
    concurrency: int = 15
    scan_unit_ids: list[int] = field(default_factory=lambda: [1])
    skip_ips: set[str] = field(default_factory=set)


@dataclass
class DiscoveredDevice:
    """A SunSpec device found during scanning."""

    ip: str
    port: int
    unit_id: int
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str

    @property
    def supported(self) -> bool:
        """True if this device is a supported inverter type."""
        return "solaredge" in self.manufacturer.lower()


def detect_subnet() -> IPv4Network:
    """Auto-detect the local subnet from the first non-loopback, non-link-local interface.

    Uses `ip -j -4 addr show` to enumerate network interfaces.
    Raises RuntimeError if no usable interface is found.
    """
    result = subprocess.run(
        ["ip", "-j", "-4", "addr", "show"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    interfaces = json.loads(result.stdout)

    for iface in interfaces:
        for addr_info in iface.get("addr_info", []):
            ip_str = addr_info.get("local", "")
            prefix = addr_info.get("prefixlen", 24)
            try:
                ip = IPv4Address(ip_str)
            except ValueError:
                continue
            # Skip loopback (127.x.x.x)
            if ip.is_loopback:
                continue
            # Skip link-local (169.254.x.x)
            if ip.is_link_local:
                continue
            return IPv4Network(f"{ip_str}/{prefix}", strict=False)

    raise RuntimeError("No usable network interface found for subnet detection")


async def _probe_port(ip: str, port: int, timeout: float) -> bool:
    """Test whether a TCP port is open on the given IP.

    Returns True if connection succeeds within timeout, False otherwise.
    """
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _verify_sunspec(
    ip: str, port: int, unit_id: int, timeout: float
) -> DiscoveredDevice | None:
    """Verify SunSpec magic number and read Common Block identity.

    Returns DiscoveredDevice if valid SunSpec device, None otherwise.
    """
    client = AsyncModbusTcpClient(ip, port=port, timeout=timeout, retries=0)
    try:
        await client.connect()

        # Read SunSpec header (2 registers at 40000)
        header = await client.read_holding_registers(
            SUNSPEC_HEADER_ADDR, count=2, device_id=unit_id
        )
        if header.isError():
            return None
        if header.registers != SUNSPEC_MAGIC:
            return None

        # Read Common Block (67 registers at 40002)
        common = await client.read_holding_registers(
            COMMON_BLOCK_ADDR, count=COMMON_BLOCK_COUNT, device_id=unit_id
        )
        if common.isError():
            return None

        regs = common.registers
        # Validate Common Block structure
        did = regs[0]
        length = regs[1]
        if did != 1 or length != 65:
            log.warning("scanner.invalid_common_block", ip=ip, did=did, length=length)
            return None

        manufacturer = decode_string(regs[2:18])
        model = decode_string(regs[18:34])
        firmware = decode_string(regs[42:50])
        serial = decode_string(regs[50:66])

        return DiscoveredDevice(
            ip=ip,
            port=port,
            unit_id=unit_id,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial,
            firmware_version=firmware,
        )

    except Exception:
        log.debug("scanner.verify_failed", ip=ip, port=port)
        return None
    finally:
        client.close()


async def scan_subnet(
    config: ScanConfig | None = None,
    progress_callback: Callable | None = None,
) -> list[DiscoveredDevice]:
    """Scan the local subnet for SunSpec-compatible inverters.

    Phase 1: TCP probe all hosts on configured ports (concurrent, bounded by semaphore).
    Phase 2: Verify SunSpec on hosts with open ports.

    Args:
        config: Scan configuration. Uses defaults if None.
        progress_callback: Optional callback(phase, current, total) for progress updates.

    Returns:
        List of discovered SunSpec devices.
    """
    if config is None:
        config = ScanConfig()

    subnet = detect_subnet()
    hosts = [str(ip) for ip in subnet.hosts() if str(ip) not in config.skip_ips]

    log.info("scan.start", subnet=str(subnet), host_count=len(hosts), ports=config.ports)

    # Phase 1: TCP port probe
    semaphore = asyncio.Semaphore(config.concurrency)
    open_hosts: list[tuple[str, int]] = []
    total_probes = len(hosts) * len(config.ports)
    probe_count = 0

    async def probe_with_sem(ip: str, port: int) -> tuple[str, int, bool]:
        async with semaphore:
            result = await _probe_port(ip, port, config.tcp_timeout)
            return ip, port, result

    tasks = [
        probe_with_sem(ip, port)
        for ip in hosts
        for port in config.ports
    ]

    for coro in asyncio.as_completed(tasks):
        ip, port, is_open = await coro
        probe_count += 1
        if progress_callback:
            progress_callback("probe", probe_count, total_probes)
        if is_open:
            open_hosts.append((ip, port))

    log.info("scan.probe_complete", open_count=len(open_hosts))

    # Phase 2: SunSpec verification
    devices: list[DiscoveredDevice] = []
    verify_total = len(open_hosts) * len(config.scan_unit_ids)
    verify_count = 0

    for ip, port in open_hosts:
        for unit_id in config.scan_unit_ids:
            verify_count += 1
            if progress_callback:
                progress_callback("verify", verify_count, verify_total)
            device = await _verify_sunspec(ip, port, unit_id, config.modbus_timeout)
            if device:
                log.info(
                    "scan.device_found",
                    ip=ip, port=port, unit_id=unit_id,
                    manufacturer=device.manufacturer, model=device.model,
                )
                devices.append(device)

    log.info("scan.complete", devices_found=len(devices))
    return devices
