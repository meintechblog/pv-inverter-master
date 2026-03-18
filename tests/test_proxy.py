"""Integration tests for proxy server orchestration.

Uses a real pymodbus server on a high port (15502) with mock plugins.
Tests verify SunSpec discovery, cache-based serving, staleness error behavior,
and unit ID filtering.
"""
from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.client import AsyncModbusTcpClient

from venus_os_fronius_proxy.plugin import InverterPlugin, PollResult
from venus_os_fronius_proxy.sunspec_models import (
    PROXY_UNIT_ID,
    encode_string,
    COMMON_DID,
    COMMON_LENGTH,
    INVERTER_DID,
    INVERTER_LENGTH,
    NAMEPLATE_DID,
    NAMEPLATE_LENGTH,
    CONTROLS_DID,
    CONTROLS_LENGTH,
)
from venus_os_fronius_proxy.proxy import (
    run_proxy,
    StalenessAwareSlaveContext,
    POLL_INTERVAL,
    STALENESS_TIMEOUT,
)


# ---------- Sample Data ----------

def _make_sample_common() -> list[int]:
    """67 registers: DID=1, Length=65, Manufacturer='SolarEdge', rest zeros."""
    regs = [0] * 67
    regs[0] = COMMON_DID       # 1
    regs[1] = COMMON_LENGTH    # 65
    # Manufacturer "SolarEdge" at offset 2-17
    regs[2:18] = encode_string("SolarEdge", 16)
    # Model "SE30K" at offset 18-33
    regs[18:34] = encode_string("SE30K", 16)
    # Version at offset 42-49
    regs[42:50] = encode_string("4.12.30", 8)
    # Serial at offset 50-65
    regs[50:66] = encode_string("7F1234567890ABCD", 16)
    # DeviceAddress at offset 66
    regs[66] = 1
    return regs


def _make_sample_inverter() -> list[int]:
    """52 registers: DID=103, Length=50, with sample measurement values."""
    regs = [0] * 52
    regs[0] = INVERTER_DID     # 103
    regs[1] = INVERTER_LENGTH  # 50
    # I_AC_Current (offset 2) = 440 (with SF -1 = 44.0A)
    regs[2] = 440
    # I_AC_CurrentA (offset 3) = 147
    regs[3] = 147
    # I_AC_Current_SF (offset 6) = -1
    regs[6] = struct.unpack(">H", struct.pack(">h", -1))[0]
    # I_AC_Power (offset 14) = 28500 (with SF 0 = 28500W)
    regs[14] = 28500
    # I_AC_Power_SF (offset 15) = 0
    regs[15] = 0
    # I_Status (offset 38) = 4 (MPPT)
    regs[38] = 4
    return regs


# ---------- Mock Plugin ----------

def _make_mock_plugin(
    poll_success: bool = True,
    common_regs: list[int] | None = None,
    inverter_regs: list[int] | None = None,
) -> InverterPlugin:
    """Create a mock InverterPlugin with configurable poll behavior."""
    plugin = MagicMock(spec=InverterPlugin)
    plugin.connect = AsyncMock()
    plugin.close = AsyncMock()

    if poll_success:
        cr = common_regs if common_regs is not None else _make_sample_common()
        ir = inverter_regs if inverter_regs is not None else _make_sample_inverter()
        plugin.poll = AsyncMock(return_value=PollResult(
            common_registers=cr,
            inverter_registers=ir,
            success=True,
        ))
    else:
        plugin.poll = AsyncMock(return_value=PollResult(
            common_registers=[],
            inverter_registers=[],
            success=False,
            error="Connection refused",
        ))

    # Model 120 from actual SolarEdgePlugin
    from venus_os_fronius_proxy.plugins.solaredge import SolarEdgePlugin
    real_plugin = SolarEdgePlugin()
    plugin.get_model_120_registers = MagicMock(
        return_value=real_plugin.get_model_120_registers()
    )
    plugin.get_static_common_overrides = MagicMock(
        return_value=real_plugin.get_static_common_overrides()
    )
    return plugin


# ---------- Test Helpers ----------

TEST_HOST = "127.0.0.1"
TEST_PORT = 15502


async def _wait_for_cache_update(
    client: AsyncModbusTcpClient,
    address: int,
    count: int,
    timeout: float = 2.0,
    poll_interval: float = 0.05,
) -> list[int]:
    """Polling-with-retry: read registers until non-zero or timeout.

    Returns the register values once any value in the result is non-zero.
    Raises TimeoutError if timeout is exceeded.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = await client.read_holding_registers(
            address, count=count, slave=PROXY_UNIT_ID,
        )
        if not result.isError():
            if any(v != 0 for v in result.registers):
                return list(result.registers)
        await asyncio.sleep(poll_interval)
    raise TimeoutError(f"Cache not updated within {timeout}s for address {address}")


# ---------- Fixtures ----------

@pytest.fixture
async def proxy_client():
    """Start proxy on TEST_HOST:TEST_PORT with mock plugin, yield client."""
    plugin = _make_mock_plugin(poll_success=True)

    # Start proxy as background task
    proxy_task = asyncio.create_task(
        run_proxy(plugin, host=TEST_HOST, port=TEST_PORT, poll_interval=0.05)
    )

    # Wait for server to be ready
    client = AsyncModbusTcpClient(TEST_HOST, port=TEST_PORT)
    for _ in range(40):  # up to 2s
        try:
            connected = await client.connect()
            if connected:
                break
        except Exception:
            pass
        await asyncio.sleep(0.05)
    else:
        proxy_task.cancel()
        pytest.fail("Could not connect to proxy server")

    yield client

    # Cleanup
    client.close()
    proxy_task.cancel()
    try:
        await proxy_task
    except asyncio.CancelledError:
        pass


@pytest.fixture
async def stale_proxy_client():
    """Start proxy with always-failing plugin and short staleness timeout."""
    plugin = _make_mock_plugin(poll_success=False)

    # We need to patch STALENESS_TIMEOUT for this test
    # Instead, we'll create a custom run with short timeout
    from venus_os_fronius_proxy.sunspec_models import build_initial_registers, DATABLOCK_START
    from venus_os_fronius_proxy.register_cache import RegisterCache
    from venus_os_fronius_proxy.proxy import (
        StalenessAwareSlaveContext, _poll_loop, _start_server,
    )
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
    from pymodbus.server import ModbusTcpServer

    initial_values = build_initial_registers()
    datablock = ModbusSequentialDataBlock(DATABLOCK_START, initial_values)
    cache = RegisterCache(datablock, staleness_timeout=0.1)  # Very short timeout

    model_120_regs = plugin.get_model_120_registers()
    datablock.setValues(40122, model_120_regs)

    slave_ctx = StalenessAwareSlaveContext(cache=cache, hr=datablock)
    server_ctx = ModbusServerContext(
        slaves={PROXY_UNIT_ID: slave_ctx},
        single=False,
    )

    await plugin.connect()

    server = ModbusTcpServer(
        context=server_ctx,
        address=(TEST_HOST, TEST_PORT + 1),  # Use different port
    )

    async def run_stale():
        await asyncio.gather(
            _start_server(server),
            _poll_loop(plugin, cache, poll_interval=0.05),
        )

    proxy_task = asyncio.create_task(run_stale())

    # Wait for server
    client = AsyncModbusTcpClient(TEST_HOST, port=TEST_PORT + 1)
    for _ in range(40):
        try:
            connected = await client.connect()
            if connected:
                break
        except Exception:
            pass
        await asyncio.sleep(0.05)
    else:
        proxy_task.cancel()
        pytest.fail("Could not connect to stale proxy server")

    # Wait for staleness timeout
    await asyncio.sleep(0.3)

    yield client

    client.close()
    proxy_task.cancel()
    try:
        await proxy_task
    except asyncio.CancelledError:
        pass


# ---------- Tests ----------

class TestServerConnection:
    @pytest.mark.asyncio
    async def test_server_accepts_connection(self, proxy_client):
        """Proxy accepts Modbus TCP connections."""
        assert proxy_client.connected

    @pytest.mark.asyncio
    async def test_unit_id_126_only(self, proxy_client):
        """Reads from unit ID 1 fail; reads from unit ID 126 succeed."""
        # Unit 126 should work
        result_126 = await proxy_client.read_holding_registers(
            40000, count=2, slave=PROXY_UNIT_ID,
        )
        assert not result_126.isError()

        # Unit 1 should fail
        result_1 = await proxy_client.read_holding_registers(
            40000, count=2, slave=1,
        )
        assert result_1.isError()


class TestSunSpecDiscovery:
    @pytest.mark.asyncio
    async def test_sunspec_discovery_flow(self, proxy_client):
        """Walk the SunSpec model chain: Header -> 1 -> 103 -> 120 -> 123 -> 0xFFFF."""
        # SunSpec Header at 40000-40001
        header = await proxy_client.read_holding_registers(
            40000, count=2, slave=PROXY_UNIT_ID,
        )
        assert not header.isError()
        assert header.registers[0] == 0x5375  # "Su"
        assert header.registers[1] == 0x6E53  # "nS"

        # Common Model at 40002
        common = await proxy_client.read_holding_registers(
            40002, count=2, slave=PROXY_UNIT_ID,
        )
        assert not common.isError()
        assert common.registers[0] == COMMON_DID      # 1
        assert common.registers[1] == COMMON_LENGTH    # 65

        # Model 103 at 40069
        inv = await proxy_client.read_holding_registers(
            40069, count=2, slave=PROXY_UNIT_ID,
        )
        assert not inv.isError()
        assert inv.registers[0] == INVERTER_DID    # 103
        assert inv.registers[1] == INVERTER_LENGTH # 50

        # Model 120 at 40121
        np = await proxy_client.read_holding_registers(
            40121, count=2, slave=PROXY_UNIT_ID,
        )
        assert not np.isError()
        assert np.registers[0] == NAMEPLATE_DID    # 120
        assert np.registers[1] == NAMEPLATE_LENGTH # 26

        # Model 123 at 40149
        ctrl = await proxy_client.read_holding_registers(
            40149, count=2, slave=PROXY_UNIT_ID,
        )
        assert not ctrl.isError()
        assert ctrl.registers[0] == CONTROLS_DID    # 123
        assert ctrl.registers[1] == CONTROLS_LENGTH # 24

        # End marker at 40175
        end = await proxy_client.read_holding_registers(
            40175, count=2, slave=PROXY_UNIT_ID,
        )
        assert not end.isError()
        assert end.registers[0] == 0xFFFF
        assert end.registers[1] == 0x0000


class TestCacheServing:
    @pytest.mark.asyncio
    async def test_inverter_registers_from_cache(self, proxy_client):
        """After polling, inverter registers match mock plugin data."""
        # Wait for cache to be populated via polling-with-retry
        # Read I_AC_Current at 40071 (offset 2 in Model 103)
        regs = await _wait_for_cache_update(
            proxy_client, 40071, count=1, timeout=2.0,
        )
        assert regs[0] == 440  # Sample I_AC_Current

    @pytest.mark.asyncio
    async def test_serves_from_cache(self, proxy_client):
        """Server reads from cache, not passthrough. Initial read may be zeros."""
        # Read Model 103 data immediately -- may be zeros before first poll
        initial = await proxy_client.read_holding_registers(
            40071, count=1, slave=PROXY_UNIT_ID,
        )
        assert not initial.isError()
        # initial might be 0 (before poll) or 440 (after poll) -- both OK

        # Wait for cache update using polling-with-retry
        regs = await _wait_for_cache_update(
            proxy_client, 40071, count=1, timeout=2.0,
        )
        assert regs[0] == 440  # Now has real data from cache

    @pytest.mark.asyncio
    async def test_common_model_has_fronius_manufacturer(self, proxy_client):
        """After poll, Common Model manufacturer reads 'Fronius' (translated from 'SolarEdge')."""
        # Wait for cache update on common model
        regs = await _wait_for_cache_update(
            proxy_client, 40004, count=16, timeout=2.0,
        )
        # Decode manufacturer string
        raw = b"".join(r.to_bytes(2, "big") for r in regs)
        manufacturer = raw.decode("ascii").rstrip("\x00")
        assert manufacturer == "Fronius"


class TestStaleness:
    @pytest.mark.asyncio
    async def test_returns_error_when_stale(self, stale_proxy_client):
        """When cache is stale, server returns Modbus error on reads."""
        # Cache is stale because plugin always fails and timeout is 0.1s
        # We waited 0.3s in fixture
        result = await stale_proxy_client.read_holding_registers(
            40071, count=1, slave=PROXY_UNIT_ID,
        )
        # Should be an error response (Modbus exception)
        assert result.isError(), "Expected Modbus error when cache is stale"


class TestProxyConstants:
    def test_poll_interval_default(self):
        """POLL_INTERVAL is 1.0 seconds."""
        assert POLL_INTERVAL == 1.0

    def test_staleness_timeout_default(self):
        """STALENESS_TIMEOUT is 30.0 seconds."""
        assert STALENESS_TIMEOUT == 30.0
