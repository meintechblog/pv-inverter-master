"""Typed application context replacing the flat shared_ctx dict.

AppContext holds all runtime state for the proxy. DeviceState holds
per-device state (one entry per inverter). Compat property accessors
proxy to the primary (first) device for single-device operation.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class DeviceState:
    """Per-device runtime state."""
    collector: object = None       # DashboardCollector (avoid circular import)
    poll_counter: dict = field(default_factory=lambda: {"success": 0, "total": 0})
    conn_mgr: object = None        # ConnectionManager
    last_poll_data: dict | None = None  # raw poll registers for register viewer
    plugin: object = None          # InverterPlugin instance


@dataclass
class AppContext:
    """Typed application context replacing flat shared_ctx dict."""

    # Core infrastructure
    cache: object = None           # RegisterCache
    control_state: object = None   # ControlState
    config: object = None          # Config
    config_path: str = ""

    # Device states (keyed by InverterEntry.id)
    devices: dict[str, DeviceState] = field(default_factory=dict)

    # Venus OS
    venus_mqtt_connected: bool = False
    venus_os_detected: bool = False
    venus_os_detected_ts: float = 0.0
    venus_os_client_ip: str = ""
    venus_task: object = None      # asyncio.Task
    venus_settings: dict | None = None

    # Webapp
    webapp: object = None          # aiohttp web.Application

    # Internal
    polling_paused: bool = False
    _last_modbus_client_ip: str = ""
    override_log: object = None    # OverrideLog
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Backward compat: single-device accessors for Phase 21
    # These will be removed in Phase 22 when DeviceRegistry takes over
    @property
    def primary_device(self) -> DeviceState | None:
        """Return first device state (single-device compat)."""
        return next(iter(self.devices.values()), None)

    @property
    def dashboard_collector(self):
        """Compat accessor for primary device collector."""
        dev = self.primary_device
        return dev.collector if dev else None

    @property
    def conn_mgr(self):
        """Compat accessor for primary device connection manager."""
        dev = self.primary_device
        return dev.conn_mgr if dev else None

    @property
    def poll_counter(self):
        """Compat accessor for primary device poll counter."""
        dev = self.primary_device
        return dev.poll_counter if dev else {"success": 0, "total": 0}

    @property
    def last_poll_data(self):
        """Compat accessor for primary device last poll data."""
        dev = self.primary_device
        return dev.last_poll_data if dev else None

    @last_poll_data.setter
    def last_poll_data(self, value):
        dev = self.primary_device
        if dev:
            dev.last_poll_data = value
