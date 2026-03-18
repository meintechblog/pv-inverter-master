"""Entry point for python -m venus_os_fronius_proxy."""
from __future__ import annotations

import asyncio
import logging
import sys

from venus_os_fronius_proxy.proxy import run_proxy
from venus_os_fronius_proxy.plugins.solaredge import SolarEdgePlugin


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Configuration (hardcoded for now, webapp config in Phase 4)
    plugin = SolarEdgePlugin(
        host="192.168.3.18",
        port=1502,
        unit_id=1,
    )

    try:
        asyncio.run(run_proxy(plugin, host="0.0.0.0", port=502))
    except KeyboardInterrupt:
        logging.info("Proxy stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
