"""Read ESS settings from Venus OS via Modbus TCP.

Polls Venus OS periodically and stores the latest settings in a dict
that gets included in the dashboard snapshot.
"""
from __future__ import annotations

import asyncio
import time

import structlog

logger = structlog.get_logger(component="venus_reader")


async def read_venus_settings(host: str, port: int = 502) -> dict | None:
    """Read ESS settings from Venus OS Modbus TCP (unit 100).

    Returns dict with parsed values, or None on failure.
    """
    from pymodbus.client import AsyncModbusTcpClient

    try:
        client = AsyncModbusTcpClient(host, port=port)
        await client.connect()
        if not client.connected:
            return None

        r = await client.read_holding_registers(2700, count=10, device_id=100)
        client.close()

        if r.isError():
            return None

        regs = r.registers

        def s16(v: int) -> int:
            return v - 65536 if v > 32767 else v

        max_feed_in_raw = regs[6]  # 2706
        # Value is in hecto-watts (100 = 10000W)
        max_feed_in_w = max_feed_in_raw * 100 if max_feed_in_raw < 32768 else -1

        return {
            "ac_setpoint_w": s16(regs[0]),         # 2700: Grid setpoint
            "max_feed_in_w": max_feed_in_w,         # 2706: Max feed-in power
            "overvoltage_feed_in": bool(regs[7]),   # 2707: DC-coupled PV excess
            "prevent_feedback": bool(regs[8]),       # 2708: AC-coupled PV excess
            "limiter_active": bool(regs[9]),         # 2709: PV power limiter active
            "ts": time.time(),
        }
    except Exception as e:
        logger.debug("venus_read_failed", error=str(e))
        return None


async def venus_reader_loop(
    shared_ctx: dict,
    host: str,
    port: int = 502,
    interval: float = 10.0,
) -> None:
    """Background task that polls Venus OS settings periodically."""
    while True:
        try:
            data = await read_venus_settings(host, port)
            if data is not None:
                shared_ctx["venus_settings"] = data
        except Exception:
            pass
        await asyncio.sleep(interval)
