# Technology Stack

**Project:** Venus OS Fronius Proxy (SolarEdge -> Fronius Modbus TCP translation)
**Researched:** 2026-03-17
**Overall Confidence:** MEDIUM (versions verified via PyPI, some architectural claims from training data only)

## Recommended Stack

**Language: Python 3.12+** -- Debian 13 (Trixie) ships Python 3.12 or 3.13. Python is the dominant language for Modbus/industrial automation, has the best library support (pymodbus), and matches the skill level needed for this kind of infrastructure glue code. No reason to consider Go, Rust, or Node for this project.

### Core: Modbus TCP

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **pymodbus** | 3.8.x (latest: 3.8.6) | Modbus TCP client AND server | The only mature Python Modbus library that supports both async client (reading SolarEdge) and async server (emulating Fronius for Venus OS) in a single package. Built on asyncio. Has dedicated `ModbusTcpServer` for exactly our use case. | HIGH (verified PyPI) |
| **pysunspec2** | 1.3.x (latest: 1.3.3) | SunSpec model definitions and register mapping | Official SunSpec Alliance library. Contains JSON model definitions for all SunSpec models (inverter, nameplate, settings, controls). Use it for register layout reference, NOT as the runtime Modbus layer -- pymodbus handles the wire protocol. | MEDIUM (verified PyPI, but need to validate how well it integrates) |

**Why NOT other Modbus libraries:**
- `modbus-tk`: Synchronous only, no async server, unmaintained since 2021
- `umodbus`: Minimal, no built-in server capability, not actively developed
- `minimalmodbus`: Serial only, no TCP support
- Raw sockets: Unnecessary complexity when pymodbus handles framing, unit IDs, and function codes

### Web Framework (Config UI)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **FastAPI** | 0.128.x (latest: 0.128.8) | REST API + serves config webapp | Async-native (shares event loop with pymodbus), auto-generates OpenAPI docs, lightweight enough for a config UI, excellent Pydantic integration for config validation. | HIGH (verified PyPI) |
| **uvicorn** | 0.39.x (latest: 0.39.0) | ASGI server | Standard FastAPI deployment server. In this project, embed it programmatically (not CLI) so the proxy process manages both Modbus and HTTP. | HIGH (verified PyPI) |
| **Jinja2** | 3.1.x (latest: 3.1.6) | Server-side HTML templates | For the config UI pages. No need for a full SPA framework -- this is a simple settings page with connection status. | HIGH (verified PyPI) |
| **htmx** (CDN) | 2.x | Dynamic UI updates without JS framework | Enables live connection status updates, form submissions without page reload, and WebSocket status feeds -- all without writing a React/Vue app. Served from CDN or bundled as a single .js file. | MEDIUM (version from training data) |

**Why NOT other web approaches:**
- `Flask`: Synchronous by default, would need threading/Celery -- unnecessary complexity alongside async pymodbus
- `Django`: Massively overkill for a config page with 5 fields
- `React/Vue/Svelte SPA`: Overkill. This is a config page, not an application. htmx + Jinja2 gives dynamic behavior with zero build step
- `Bottle/Starlette raw`: FastAPI adds type safety and auto-docs for almost no overhead over raw Starlette

### Configuration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **TOML** (stdlib `tomllib`) | Python 3.12 stdlib | Config file format | Human-readable, supports comments (unlike JSON), Python 3.11+ has it in stdlib (`tomllib` for reading). Use `tomli-w` (1.2.0) for writing. Better than YAML (no implicit type coercion footguns). | HIGH |
| **Pydantic** | 2.12.x (latest: 2.12.5) | Config validation and typed settings | Validates config on load, provides clear error messages, integrates with FastAPI for API models. Single source of truth for config schema. | HIGH (verified PyPI) |
| **tomli-w** | 1.2.x (latest: 1.2.0) | Write TOML files | Companion to stdlib `tomllib` (read-only). Needed for saving config changes from the webapp. | HIGH (verified PyPI) |

### Logging and Observability

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **structlog** | 25.x (latest: 25.5.0) | Structured logging | JSON-structured logs for systemd journal integration. Contextual logging (attach inverter_id, register_address to log entries). Much better than stdlib `logging` for debugging Modbus translation issues. | HIGH (verified PyPI) |

### Process Management

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **systemd** | OS-provided | Service management | Native on Debian 13. Handles restart-on-failure, logging to journal, boot startup. No need for supervisord or PM2. | HIGH |
| **asyncio** | Python stdlib | Async runtime | Single event loop runs pymodbus server, pymodbus client, and uvicorn concurrently. No threads, no multiprocessing -- everything is I/O-bound. | HIGH |

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **pytest** | 8.4.x (latest: 8.4.2) | Test runner | Standard Python testing. | HIGH (verified PyPI) |
| **pytest-asyncio** | 1.2.x (latest: 1.2.0) | Async test support | Required for testing async pymodbus and FastAPI code. | HIGH (verified PyPI) |
| **ruff** | 0.15.x (latest: 0.15.6) | Linter + formatter | Replaces flake8, black, isort in one fast tool. | HIGH (verified PyPI) |

### Packaging and Deployment

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| **uv** | 0.10.x (latest: 0.10.11) | Package manager and venv | 10-100x faster than pip, handles venvs, lockfiles, and Python version management. Install via `curl` on the LXC container. | HIGH (verified PyPI) |

## Architecture-Relevant Stack Decisions

### Single-Process Design
The proxy runs as ONE Python process with ONE asyncio event loop handling:
1. **Modbus TCP Client** -- polls SolarEdge registers on a configurable interval (e.g., every 1s)
2. **Modbus TCP Server** -- responds to Venus OS Modbus TCP requests with translated Fronius-compatible register values
3. **HTTP Server** -- serves the config webapp (uvicorn embedded)

This avoids IPC complexity, shared state problems, and simplifies deployment to a single systemd unit.

### Why NOT multi-process:
- Modbus polling is I/O-bound (network reads), not CPU-bound
- HTTP config UI has near-zero traffic (one user, occasionally)
- A single asyncio loop handles all three workloads trivially
- No need for Redis, message queues, or socket files

### Register Translation Layer
- Use pysunspec2 model definitions as a **reference** to build the register mapping tables
- Implement the actual register datastore using pymodbus's `ModbusSlaveContext` / `ModbusServerContext`
- The mapping is a Python dict/class that translates between SolarEdge register addresses and Fronius/SunSpec model register addresses
- Plugin architecture: each inverter brand is a Python module that implements a `RegisterTranslator` interface

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Language | Python 3.12+ | Go | No mature Modbus server library equivalent to pymodbus. Would need to implement SunSpec framing from scratch. |
| Language | Python 3.12+ | Node.js | `jsmodbus` exists but far less mature than pymodbus. No SunSpec library. |
| Modbus | pymodbus | modbus-tk | Synchronous only, unmaintained, no async server |
| Web | FastAPI + Jinja2 + htmx | Flask | Sync-first design conflicts with async Modbus loop |
| Web | FastAPI + Jinja2 + htmx | React SPA | Massive overkill for a config page. Adds build toolchain, node_modules, complexity. |
| Config | TOML | YAML | YAML has implicit type coercion bugs (e.g., `NO` -> `false`). TOML is explicit. |
| Config | TOML | JSON | JSON has no comments. Config files need comments. |
| Deployment | systemd + uv | Docker | Project constraint: no Docker in LXC. Also unnecessary abstraction for a single service. |
| Deployment | systemd + uv | supervisord | systemd is already on Debian, handles everything supervisord does and more |
| Logging | structlog | stdlib logging | stdlib logging is painful for structured context. structlog integrates better with systemd journal. |

## Python Version Note

Debian 13 (Trixie) is expected to ship Python 3.12 or 3.13. The stack requires Python 3.11+ minimum (for `tomllib` in stdlib). Pin to `>=3.12` in `pyproject.toml`.

**Validation needed:** Confirm exact Python version on the target LXC container (`python3 --version`).

## Installation

```bash
# On the Debian 13 LXC container:

# Install uv (package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init venus-os-fronius-proxy
cd venus-os-fronius-proxy

# Core dependencies
uv add pymodbus>=3.8.0
uv add pysunspec2>=1.3.0
uv add fastapi>=0.128.0
uv add uvicorn[standard]>=0.39.0
uv add jinja2>=3.1.0
uv add pydantic>=2.12.0
uv add tomli-w>=1.2.0
uv add structlog>=25.0.0

# Dev dependencies
uv add --dev pytest>=8.4.0
uv add --dev pytest-asyncio>=1.2.0
uv add --dev ruff>=0.15.0
```

## systemd Unit File (Template)

```ini
[Unit]
Description=Venus OS Fronius Proxy (SolarEdge Modbus TCP Translation)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=venusproxy
Group=venusproxy
WorkingDirectory=/opt/venus-os-fronius-proxy
ExecStart=/opt/venus-os-fronius-proxy/.venv/bin/python -m venus_os_fronius_proxy
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
# Hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/opt/venus-os-fronius-proxy/config

[Install]
WantedBy=multi-user.target
```

## Debian 13 System Dependencies

```bash
# Minimal system packages needed
apt update && apt install -y python3 python3-venv git

# No C compilation needed -- all Python packages are pure Python or have wheels
```

## Sources

- pymodbus 3.8.6: PyPI (verified via `pip3 index versions`)
- FastAPI 0.128.8: PyPI (verified via `pip3 index versions`)
- uvicorn 0.39.0: PyPI (verified via `pip3 index versions`)
- pysunspec2 1.3.3: PyPI (verified via `pip3 index versions`)
- Pydantic 2.12.5: PyPI (verified via `pip3 index versions`)
- structlog 25.5.0: PyPI (verified via `pip3 index versions`)
- pytest 8.4.2: PyPI (verified via `pip3 index versions`)
- ruff 0.15.6: PyPI (verified via `pip3 index versions`)
- uv 0.10.11: PyPI (verified via `pip3 index versions`)

**Note:** Web search was unavailable during research. Library capability claims (e.g., pymodbus async server features, pysunspec2 model definitions) are based on training data and should be validated against current documentation during implementation.
