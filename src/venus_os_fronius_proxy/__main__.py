"""Entry point for venus-os-fronius-proxy service.

Loads YAML config, configures structured JSON logging, handles SIGTERM
for graceful shutdown (reset power limit to 100% before stopping).
Runs a health heartbeat every 5 minutes.
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time

import structlog

from venus_os_fronius_proxy.config import load_config
from venus_os_fronius_proxy.logging_config import configure_logging
from venus_os_fronius_proxy.plugins.solaredge import SolarEdgePlugin
from venus_os_fronius_proxy.proxy import run_proxy


HEARTBEAT_INTERVAL = 300  # 5 minutes


def main():
    parser = argparse.ArgumentParser(description="Venus OS Fronius Proxy")
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to config YAML (default: /etc/venus-os-fronius-proxy/config.yaml)",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Configure structured JSON logging
    configure_logging(config.log_level)
    log = structlog.get_logger(component="main")

    log.info(
        "starting",
        inverter_host=config.inverter.host,
        inverter_port=config.inverter.port,
        proxy_port=config.proxy.port,
        log_level=config.log_level,
    )

    # Create plugin from config
    plugin = SolarEdgePlugin(
        host=config.inverter.host,
        port=config.inverter.port,
        unit_id=config.inverter.unit_id,
    )

    # Graceful shutdown handling
    shutdown_event = asyncio.Event()

    async def _health_heartbeat(
        cache,
        conn_mgr,
        control_state,
        poll_counter,
    ):
        """Log health heartbeat every 5 minutes (per locked CONTEXT.md decision).

        Emits: poll_success_rate, cache_age, last_control_value, connection_state.
        """
        hb_log = structlog.get_logger(component="health")
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=HEARTBEAT_INTERVAL
                )
                break  # shutdown requested
            except asyncio.TimeoutError:
                pass  # 5 minutes elapsed, emit heartbeat

            cache_age = time.monotonic() - cache.last_successful_poll if cache._has_been_updated else -1
            success_rate = (
                poll_counter["success"] / poll_counter["total"] * 100
                if poll_counter["total"] > 0
                else 0.0
            )
            hb_log.info(
                "health_heartbeat",
                poll_success_rate=round(success_rate, 1),
                poll_total=poll_counter["total"],
                cache_age=round(cache_age, 1),
                cache_stale=cache.is_stale,
                connection_state=conn_mgr.state.value,
                last_control_value=control_state.wmaxlimpct_float if control_state.is_enabled else None,
                control_enabled=control_state.is_enabled,
            )

    async def run_with_shutdown():
        loop = asyncio.get_running_loop()

        def handle_signal(sig):
            log.info("shutdown_signal_received", signal=sig.name)
            shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signal, sig)

        # Start proxy in background task with shared context for heartbeat
        shared_ctx: dict = {}
        proxy_task = asyncio.create_task(
            run_proxy(
                plugin,
                host=config.proxy.host,
                port=config.proxy.port,
                poll_interval=config.proxy.poll_interval,
                shared_ctx=shared_ctx,
            )
        )

        # Wait briefly for run_proxy to populate shared_ctx
        for _ in range(50):  # up to 0.5s
            if shared_ctx:
                break
            await asyncio.sleep(0.01)

        # Start health heartbeat task
        heartbeat_task = None
        if shared_ctx:
            heartbeat_task = asyncio.create_task(
                _health_heartbeat(
                    cache=shared_ctx["cache"],
                    conn_mgr=shared_ctx["conn_mgr"],
                    control_state=shared_ctx["control_state"],
                    poll_counter=shared_ctx["poll_counter"],
                )
            )

        # Wait for shutdown signal
        await shutdown_event.wait()

        log.info("graceful_shutdown_starting")

        # Cancel heartbeat
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # Reset power limit to 100% (no limit) before stopping
        try:
            await asyncio.wait_for(
                plugin.write_power_limit(enable=True, limit_pct=100.0),
                timeout=5.0,
            )
            log.info("power_limit_reset", value_pct=100.0)
        except Exception as e:
            log.warning("power_limit_reset_failed", error=str(e))

        # Cancel proxy task
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass

        # Close plugin
        try:
            await plugin.close()
        except Exception as e:
            log.warning("plugin_close_failed", error=str(e))

        log.info("shutdown_complete")

    try:
        asyncio.run(run_with_shutdown())
    except KeyboardInterrupt:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
