"""Plugin registry and factory for inverter type dispatch."""
from __future__ import annotations

from venus_os_fronius_proxy.config import GatewayConfig, InverterEntry


def plugin_factory(
    entry: InverterEntry,
    gateway_config: GatewayConfig | None = None,
):
    """Create the appropriate InverterPlugin for an InverterEntry.

    Args:
        entry: InverterEntry with type field ("solaredge" or "opendtu").
        gateway_config: Optional GatewayConfig for opendtu entries.
            If None for opendtu, a default is created from entry.gateway_host.

    Returns:
        An InverterPlugin instance configured for the entry.

    Raises:
        ValueError: For unknown inverter types.
    """
    if entry.type == "solaredge":
        from venus_os_fronius_proxy.plugins.solaredge import SolarEdgePlugin
        return SolarEdgePlugin(host=entry.host, port=entry.port, unit_id=entry.unit_id)
    elif entry.type == "opendtu":
        from venus_os_fronius_proxy.plugins.opendtu import OpenDTUPlugin
        if gateway_config is None:
            gateway_config = GatewayConfig(host=entry.gateway_host)
        return OpenDTUPlugin(
            gateway_config=gateway_config,
            serial=entry.serial,
            name=entry.name,
        )
    else:
        raise ValueError(f"Unknown inverter type: {entry.type}")
