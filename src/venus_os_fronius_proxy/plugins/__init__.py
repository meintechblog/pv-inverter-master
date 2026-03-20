"""Plugin registry and factory for inverter type dispatch."""
from __future__ import annotations

from venus_os_fronius_proxy.config import InverterEntry


def plugin_factory(entry: InverterEntry):
    """Create the appropriate InverterPlugin for an InverterEntry.

    Args:
        entry: InverterEntry with type field ("solaredge" or "opendtu").

    Returns:
        An InverterPlugin instance configured for the entry.

    Raises:
        NotImplementedError: For opendtu type (deferred to Plan 21-02).
        ValueError: For unknown inverter types.
    """
    if entry.type == "solaredge":
        from venus_os_fronius_proxy.plugins.solaredge import SolarEdgePlugin
        return SolarEdgePlugin(host=entry.host, port=entry.port, unit_id=entry.unit_id)
    elif entry.type == "opendtu":
        raise NotImplementedError("OpenDTU plugin not yet implemented (Plan 21-02)")
    else:
        raise ValueError(f"Unknown inverter type: {entry.type}")
