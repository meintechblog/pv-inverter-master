"""Tests for YAML configuration loading with defaults and overrides."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_load_config_defaults(tmp_path: Path):
    """load_config() with nonexistent file returns Config with all defaults."""
    from venus_os_fronius_proxy.config import load_config

    cfg = load_config(str(tmp_path / "nonexistent.yaml"))

    assert cfg.inverter.host == "192.168.3.18"
    assert cfg.inverter.port == 1502
    assert cfg.inverter.unit_id == 1
    assert cfg.proxy.host == "0.0.0.0"
    assert cfg.proxy.port == 502
    assert cfg.proxy.poll_interval == 1.0
    assert cfg.proxy.staleness_timeout == 30.0
    assert cfg.night_mode.threshold_seconds == 300.0
    assert cfg.log_level == "INFO"


def test_load_config_partial_override(tmp_path: Path):
    """YAML with partial inverter override keeps other defaults."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n  - host: "10.0.0.1"\n'
    )

    cfg = load_config(str(cfg_file))

    assert cfg.inverter.host == "10.0.0.1"
    assert cfg.inverter.port == 1502  # default preserved
    assert cfg.proxy.port == 502      # default preserved


def test_load_config_log_level(tmp_path: Path):
    """YAML with log_level override returns correct level."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('log_level: "DEBUG"\n')

    cfg = load_config(str(cfg_file))

    assert cfg.log_level == "DEBUG"


def test_load_config_night_mode(tmp_path: Path):
    """YAML with night_mode override returns correct threshold."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("night_mode:\n  threshold_seconds: 600.0\n")

    cfg = load_config(str(cfg_file))

    assert cfg.night_mode.threshold_seconds == 600.0


def test_venus_config_defaults():
    """VenusConfig() has host="", port=1883, portal_id=""."""
    from venus_os_fronius_proxy.config import VenusConfig

    vc = VenusConfig()
    assert vc.host == ""
    assert vc.port == 1883
    assert vc.portal_id == ""


def test_load_config_venus_section(tmp_path: Path):
    """load_config with venus section in YAML populates VenusConfig fields."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'venus:\n  host: "10.0.0.1"\n  port: 1884\n  portal_id: "abc123"\n'
    )

    cfg = load_config(str(cfg_file))

    assert cfg.venus.host == "10.0.0.1"
    assert cfg.venus.port == 1884
    assert cfg.venus.portal_id == "abc123"


def test_load_config_missing_venus(tmp_path: Path):
    """load_config without venus section uses VenusConfig defaults (no crash)."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('inverter:\n  host: "10.0.0.1"\n')

    cfg = load_config(str(cfg_file))

    assert cfg.venus.host == ""
    assert cfg.venus.port == 1883
    assert cfg.venus.portal_id == ""


# --- Multi-inverter config tests ---


def test_inverter_entry_fields():
    """InverterEntry has all identity fields with correct defaults."""
    from venus_os_fronius_proxy.config import InverterEntry

    entry = InverterEntry()
    assert entry.host == "192.168.3.18"
    assert entry.port == 1502
    assert entry.unit_id == 1
    assert entry.enabled is True
    assert isinstance(entry.id, str)
    assert len(entry.id) == 12
    assert entry.manufacturer == ""
    assert entry.model == ""
    assert entry.serial == ""
    assert entry.firmware_version == ""


def test_inverter_entry_unique_ids():
    """Two InverterEntry instances have different id values."""
    from venus_os_fronius_proxy.config import InverterEntry

    a = InverterEntry()
    b = InverterEntry()
    assert a.id != b.id


def test_config_inverters_is_list():
    """Config().inverters is a list containing one InverterEntry with default host."""
    from venus_os_fronius_proxy.config import Config, InverterEntry

    cfg = Config()
    assert isinstance(cfg.inverters, list)
    assert len(cfg.inverters) == 1
    assert isinstance(cfg.inverters[0], InverterEntry)
    assert cfg.inverters[0].host == "192.168.3.18"


def test_no_migration_code(tmp_path: Path):
    """load_config with old inverter: (singular) key ignores it (no migration)."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverter:\n  host: "1.2.3.4"\n  port: 502\n  unit_id: 3\n'
    )

    cfg = load_config(str(cfg_file))
    # Old format is ignored -- defaults are used instead
    assert isinstance(cfg.inverters, list)
    assert len(cfg.inverters) == 1
    assert cfg.inverters[0].host == "192.168.3.18"  # default, not migrated


def test_fresh_install_default(tmp_path: Path):
    """load_config on nonexistent file returns Config with one InverterEntry."""
    from venus_os_fronius_proxy.config import load_config, InverterEntry

    cfg = load_config(str(tmp_path / "nonexistent.yaml"))
    assert isinstance(cfg.inverters, list)
    assert len(cfg.inverters) == 1
    assert isinstance(cfg.inverters[0], InverterEntry)


def test_active_inverter_first_enabled():
    """get_active_inverter returns first entry where enabled=True."""
    from venus_os_fronius_proxy.config import Config, InverterEntry, get_active_inverter

    cfg = Config(inverters=[
        InverterEntry(host="1.1.1.1", enabled=True),
        InverterEntry(host="2.2.2.2", enabled=True),
    ])
    result = get_active_inverter(cfg)
    assert result is not None
    assert result.host == "1.1.1.1"


def test_active_inverter_skip_disabled():
    """With entries [disabled, enabled], returns the second."""
    from venus_os_fronius_proxy.config import Config, InverterEntry, get_active_inverter

    cfg = Config(inverters=[
        InverterEntry(host="1.1.1.1", enabled=False),
        InverterEntry(host="2.2.2.2", enabled=True),
    ])
    result = get_active_inverter(cfg)
    assert result is not None
    assert result.host == "2.2.2.2"


def test_active_inverter_none_enabled():
    """All disabled returns None."""
    from venus_os_fronius_proxy.config import Config, InverterEntry, get_active_inverter

    cfg = Config(inverters=[
        InverterEntry(host="1.1.1.1", enabled=False),
        InverterEntry(host="2.2.2.2", enabled=False),
    ])
    result = get_active_inverter(cfg)
    assert result is None


def test_scanner_config_default_ports(tmp_path: Path):
    """Load config with no scanner section, verify default ports."""
    from venus_os_fronius_proxy.config import load_config

    cfg = load_config(str(tmp_path / "nonexistent.yaml"))
    assert cfg.scanner.ports == [502, 1502]


def test_scanner_config_yaml_roundtrip(tmp_path: Path):
    """Save config with custom scanner ports, reload, verify ports match."""
    from venus_os_fronius_proxy.config import load_config, save_config, Config, ScannerConfig

    cfg = Config(scanner=ScannerConfig(ports=[502, 1502, 8502]))
    cfg_file = str(tmp_path / "config.yaml")
    save_config(cfg_file, cfg)

    reloaded = load_config(cfg_file)
    assert reloaded.scanner.ports == [502, 1502, 8502]


def test_load_multi_inverter_format(tmp_path: Path):
    """YAML with inverters list loads correctly as list of InverterEntry."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - host: "1.1.1.1"\n'
        '    port: 502\n'
        '    unit_id: 1\n'
        '    enabled: true\n'
        '    id: "aabbccddee11"\n'
        '  - host: "2.2.2.2"\n'
        '    port: 1502\n'
        '    unit_id: 2\n'
        '    enabled: false\n'
        '    id: "aabbccddee22"\n'
    )

    cfg = load_config(str(cfg_file))
    assert len(cfg.inverters) == 2
    assert cfg.inverters[0].host == "1.1.1.1"
    assert cfg.inverters[0].id == "aabbccddee11"
    assert cfg.inverters[1].host == "2.2.2.2"
    assert cfg.inverters[1].enabled is False


# --- v4.0 typed config tests ---


def test_load_config_with_type_field(tmp_path: Path):
    """Config YAML with type: solaredge loads correctly."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - host: "192.168.3.18"\n'
        '    type: solaredge\n'
        '    name: "Main Inverter"\n'
    )

    cfg = load_config(str(cfg_file))
    assert cfg.inverters[0].type == "solaredge"
    assert cfg.inverters[0].name == "Main Inverter"


def test_load_config_opendtu_entry(tmp_path: Path):
    """Config YAML with type: opendtu, gateway_host, serial fields."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - type: opendtu\n'
        '    name: "Balkon HM-800"\n'
        '    gateway_host: "192.168.3.98"\n'
        '    serial: "1234567890"\n'
        '    host: ""\n'
        '    port: 0\n'
        '    unit_id: 0\n'
    )

    cfg = load_config(str(cfg_file))
    entry = cfg.inverters[0]
    assert entry.type == "opendtu"
    assert entry.name == "Balkon HM-800"
    assert entry.gateway_host == "192.168.3.98"
    assert entry.serial == "1234567890"


def test_load_config_gateways_section(tmp_path: Path):
    """Config YAML with gateways: opendtu: [...] parses GatewayConfig."""
    from venus_os_fronius_proxy.config import load_config, GatewayConfig

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'gateways:\n'
        '  opendtu:\n'
        '    - host: "192.168.3.98"\n'
        '      user: admin\n'
        '      password: secret123\n'
        '      poll_interval: 10.0\n'
    )

    cfg = load_config(str(cfg_file))
    assert "opendtu" in cfg.gateways
    assert len(cfg.gateways["opendtu"]) == 1
    gw = cfg.gateways["opendtu"][0]
    assert isinstance(gw, GatewayConfig)
    assert gw.host == "192.168.3.98"
    assert gw.user == "admin"
    assert gw.password == "secret123"
    assert gw.poll_interval == 10.0


def test_load_config_name_field(tmp_path: Path):
    """Name field loaded for both solaredge and opendtu types."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - type: solaredge\n'
        '    name: "SE30K Dach"\n'
        '    host: "192.168.3.18"\n'
        '  - type: opendtu\n'
        '    name: "HM-800 Balkon"\n'
        '    gateway_host: "192.168.3.98"\n'
    )

    cfg = load_config(str(cfg_file))
    assert cfg.inverters[0].name == "SE30K Dach"
    assert cfg.inverters[1].name == "HM-800 Balkon"


def test_save_config_roundtrip_new_fields(tmp_path: Path):
    """Save and reload preserves type, name, gateway_host, gateways."""
    from venus_os_fronius_proxy.config import (
        Config, InverterEntry, GatewayConfig, save_config, load_config,
    )

    cfg = Config(
        inverters=[
            InverterEntry(
                type="opendtu", name="Balkon", gateway_host="192.168.3.98",
                serial="123456", host="", port=0, unit_id=0, id="test12345678",
            ),
        ],
        gateways={
            "opendtu": [GatewayConfig(host="192.168.3.98", password="pw123")],
        },
    )

    cfg_file = str(tmp_path / "config.yaml")
    save_config(cfg_file, cfg)
    reloaded = load_config(cfg_file)

    assert reloaded.inverters[0].type == "opendtu"
    assert reloaded.inverters[0].name == "Balkon"
    assert reloaded.inverters[0].gateway_host == "192.168.3.98"
    assert reloaded.inverters[0].serial == "123456"
    assert "opendtu" in reloaded.gateways
    assert reloaded.gateways["opendtu"][0].host == "192.168.3.98"
    assert reloaded.gateways["opendtu"][0].password == "pw123"


def test_inverter_entry_throttle_defaults():
    """InverterEntry has throttle_order=1, throttle_enabled=True, throttle_dead_time_s=0.0."""
    from venus_os_fronius_proxy.config import InverterEntry

    entry = InverterEntry()
    assert entry.throttle_order == 1
    assert entry.throttle_enabled is True
    assert entry.throttle_dead_time_s == 0.0


def test_load_config_throttle_fields(tmp_path: Path):
    """YAML with throttle fields loads into InverterEntry correctly."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - host: "10.0.0.1"\n'
        '    throttle_order: 3\n'
        '    throttle_enabled: false\n'
        '    throttle_dead_time_s: 5.0\n'
    )

    cfg = load_config(str(cfg_file))
    assert cfg.inverters[0].throttle_order == 3
    assert cfg.inverters[0].throttle_enabled is False
    assert cfg.inverters[0].throttle_dead_time_s == 5.0


def test_load_config_throttle_defaults(tmp_path: Path):
    """YAML without throttle fields uses defaults."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'inverters:\n'
        '  - host: "10.0.0.1"\n'
    )

    cfg = load_config(str(cfg_file))
    assert cfg.inverters[0].throttle_order == 1
    assert cfg.inverters[0].throttle_enabled is True
    assert cfg.inverters[0].throttle_dead_time_s == 0.0


def test_get_gateway_for_inverter():
    """get_gateway_for_inverter returns correct GatewayConfig matching gateway_host."""
    from venus_os_fronius_proxy.config import (
        Config, InverterEntry, GatewayConfig, get_gateway_for_inverter,
    )

    cfg = Config(
        inverters=[],
        gateways={
            "opendtu": [
                GatewayConfig(host="192.168.3.98", password="pw1"),
                GatewayConfig(host="192.168.3.99", password="pw2"),
            ],
        },
    )

    opendtu_entry = InverterEntry(type="opendtu", gateway_host="192.168.3.99")
    result = get_gateway_for_inverter(cfg, opendtu_entry)
    assert result is not None
    assert result.host == "192.168.3.99"
    assert result.password == "pw2"

    # SolarEdge entry returns None
    se_entry = InverterEntry(type="solaredge")
    assert get_gateway_for_inverter(cfg, se_entry) is None

    # Non-matching host returns None
    no_match = InverterEntry(type="opendtu", gateway_host="10.0.0.1")
    assert get_gateway_for_inverter(cfg, no_match) is None


# --- MQTT Publish config tests (Phase 25) ---


def test_mqtt_publish_config_defaults(tmp_path: Path):
    """MqttPublishConfig defaults loaded from empty YAML."""
    from venus_os_fronius_proxy.config import load_config

    cfg = load_config(str(tmp_path / "nonexistent.yaml"))

    assert cfg.mqtt_publish.enabled is False
    assert cfg.mqtt_publish.host == "mqtt-master.local"
    assert cfg.mqtt_publish.port == 1883
    assert cfg.mqtt_publish.topic_prefix == "pvproxy"
    assert cfg.mqtt_publish.interval_s == 5
    assert cfg.mqtt_publish.client_id == "pv-proxy-pub"


def test_mqtt_publish_config_override(tmp_path: Path):
    """All mqtt_publish fields overridden from YAML."""
    from venus_os_fronius_proxy.config import load_config

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "mqtt_publish:\n"
        "  enabled: true\n"
        '  host: "10.0.0.5"\n'
        "  port: 8883\n"
        '  topic_prefix: "solar"\n'
        "  interval_s: 10\n"
        '  client_id: "my-pub"\n'
    )

    cfg = load_config(str(cfg_file))

    assert cfg.mqtt_publish.enabled is True
    assert cfg.mqtt_publish.host == "10.0.0.5"
    assert cfg.mqtt_publish.port == 8883
    assert cfg.mqtt_publish.topic_prefix == "solar"
    assert cfg.mqtt_publish.interval_s == 10
    assert cfg.mqtt_publish.client_id == "my-pub"
