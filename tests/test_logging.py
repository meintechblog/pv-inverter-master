"""Tests for structured JSON logging configuration."""
from __future__ import annotations

import io
import json
import sys


def test_json_output():
    """configure_logging produces JSON output with timestamp, level, event."""
    from pv_inverter_proxy.logging_config import configure_logging
    import structlog

    # Reset structlog state for test isolation
    structlog.reset_defaults()

    # Capture stdout via StringIO
    capture = io.StringIO()
    configure_logging("DEBUG", output=capture)

    log = structlog.get_logger()
    log.info("test_event")

    output = capture.getvalue().strip()
    assert output, "Expected log output on capture stream"

    parsed = json.loads(output)
    assert "timestamp" in parsed
    assert parsed["level"] == "info"
    assert parsed["event"] == "test_event"


def test_component_binding():
    """Logger with component binding includes 'component' in JSON output."""
    from pv_inverter_proxy.logging_config import configure_logging
    import structlog

    structlog.reset_defaults()

    capture = io.StringIO()
    configure_logging("DEBUG", output=capture)

    log = structlog.get_logger(component="control")
    log.info("bound_event")

    output = capture.getvalue().strip()
    parsed = json.loads(output)
    assert parsed["component"] == "control"
    assert parsed["event"] == "bound_event"
