# Phase 16: Install Script & README - Research

**Researched:** 2026-03-19
**Domain:** Shell scripting (bash installer), documentation (Markdown README)
**Confidence:** HIGH

## Summary

Phase 16 fixes two known issues: the install script generates YAML with the wrong key (`solaredge:` instead of `inverter:`) and lacks the `venus:` config section, and the README is outdated (documents the old config format, missing Venus OS integration flow). Both artifacts already exist and need targeted updates, not rewrites from scratch.

The install script at `install.sh` is a well-structured 160-line bash script. The critical bugs are: (1) line 94 writes `solaredge:` but `config.py` expects `inverter:`, (2) no `venus:` section generated, (3) no pre-flight check for port 502 availability, (4) curl flags in the documented usage lack `--fail`. The README at `README.md` documents the old `solaredge:` config key and has no mention of Venus OS MQTT configuration, the config page, or the setup flow.

**Primary recommendation:** Fix the YAML template in install.sh (inverter: key + venus: section), add port 502 and existing config pre-flight checks, then rewrite README sections for the full setup flow including Venus OS >= 3.7 prerequisite.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | Install Script fixen -- YAML Key Mismatch (`solaredge:` -> `inverter:`), Venus Config Section, sichere curl Flags | Exact line numbers identified (L94, L158), full correct YAML template derived from config.py dataclasses, curl security flags documented |
| DOCS-02 | README aktualisieren -- Setup-Flow dokumentieren, Venus OS >= 3.7 Voraussetzung, Badges, Screenshots | Current README gaps catalogued, correct config format from config.example.yaml, full feature list from phases 13-15 |
</phase_requirements>

## Standard Stack

No new libraries needed. This phase modifies two existing files:

| File | Purpose | Current State |
|------|---------|---------------|
| `install.sh` | One-line curl installer for Debian/Ubuntu | Wrong YAML key, missing venus section, no port check |
| `README.md` | Project documentation | Outdated config format, missing Venus OS setup flow |
| `config/config.example.yaml` | Reference config (already correct) | Uses `inverter:` key, has no venus section yet |

### Supporting Reference Files
| File | Purpose | Relevance |
|------|---------|-----------|
| `config.py` | Config schema (dataclasses) | Source of truth for all YAML keys and defaults |
| `config/config.local.yaml` | Dev config | Already uses `inverter:` key correctly |
| `config/venus-os-fronius-proxy.service` | systemd unit | Referenced by install script, already correct |
| `deploy.sh` | Dev deployment to LXC | Reference for network topology (192.168.3.191) |

## Architecture Patterns

### Install Script Structure (already established)
The install script follows a clean 8-step pattern:
1. Pre-flight checks (root, apt-get)
2. System dependencies
3. Service user
4. Clone/update repo
5. Python venv + install
6. Config generation (if missing)
7. Permissions
8. Systemd service install + start

No structural changes needed -- only content fixes within existing steps.

### Config YAML Template Must Match config.py Dataclasses

The correct YAML structure derived from `config.py` (lines 22-60):

```yaml
# PV-Inverter-Master Configuration
inverter:
  host: "192.168.3.18"   # SolarEdge inverter IP
  port: 1502             # Modbus TCP port
  unit_id: 1             # Modbus unit/slave ID

proxy:
  port: 502              # Venus OS connects here

venus:
  host: ""               # Venus OS IP (leave empty to skip MQTT)
  port: 1883             # MQTT port
  portal_id: ""          # Leave empty for auto-discovery

webapp:
  port: 80               # Dashboard URL

log_level: INFO
```

Key fields from dataclasses:
- `InverterConfig`: host, port, unit_id
- `ProxyConfig`: host, port, poll_interval, staleness_timeout (only port needed in minimal config)
- `VenusConfig`: host, port, portal_id
- `WebappConfig`: port
- `NightModeConfig`: threshold_seconds (advanced, omit from default)

### README Structure (target)
```
README.md
  - Title + description
  - Prerequisites (Venus OS >= 3.7, Debian 12+)
  - Quick Install (curl one-liner)
  - Configuration (correct YAML with inverter: and venus:)
  - Setup Flow (SolarEdge -> Proxy -> Venus OS MQTT)
  - Network Diagram
  - Dashboard (pages, features)
  - Management (systemctl commands)
  - Tech Stack
  - Development
  - License
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config validation in install script | Bash YAML parsing | Just write a correct static template | YAML parsing in bash is fragile |
| Port availability check | Custom netcat logic | `ss -tlnp` or `lsof -i :502` | Standard Linux tools, reliable |
| Config migration (solaredge -> inverter) | Sed-based key replacement | Warn user + manual edit | Automated YAML rewriting in bash is error-prone |

## Common Pitfalls

### Pitfall 1: Existing Config with Wrong Key
**What goes wrong:** Users who installed with old script have `solaredge:` key. New proxy code reads `inverter:` key. After update, config silently falls back to defaults (192.168.3.18:1502) which may be correct by coincidence but is not guaranteed.
**Why it happens:** `load_config()` silently uses defaults when key is missing (line 74: `data.get("inverter", {})`).
**How to avoid:** Install script must detect existing config with `solaredge:` key and warn the user, NOT auto-migrate (sed on YAML is fragile). Print clear instructions.
**Warning signs:** Service starts but connects to wrong IP / default IP.

### Pitfall 2: Port 502 Already in Use
**What goes wrong:** Another service (or previous install) already binds port 502. Service fails to start after install.
**Why it happens:** No pre-flight check. User only discovers after install completes.
**How to avoid:** Check port 502 availability before install. Warn if in use, show what process holds it.

### Pitfall 3: Curl Pipe to Bash Security
**What goes wrong:** `curl -sSL url | bash` can be exploited if TLS fails silently or partial download executes.
**Why it happens:** `-sS` suppresses progress but `-f` (fail on HTTP errors) is missing. Partial downloads can execute truncated scripts.
**How to avoid:** Use `curl -fsSL` (add `--fail`). The `-f` flag makes curl return error on HTTP 4xx/5xx instead of outputting HTML error page to bash.

### Pitfall 4: README Config Example Drift
**What goes wrong:** README shows one config format, install script generates another, config.example.yaml has a third.
**Why it happens:** Three sources of truth for config format.
**How to avoid:** README references config.example.yaml. Install script generates config matching config.example.yaml exactly. Single source of truth.

### Pitfall 5: Venus OS Version Prerequisite Not Documented
**What goes wrong:** Users with Venus OS < 3.7 try to use MQTT features, which may not be available.
**Why it happens:** MQTT on LAN was introduced/stabilized in Venus OS 3.7.
**How to avoid:** README states Venus OS >= 3.7 as prerequisite prominently.

## Code Examples

### Fix 1: Install Script YAML Template (replace lines 90-109)

```bash
    cat > "$CONFIG_DIR/config.yaml" << 'YAML'
# PV-Inverter-Master Configuration
# Docs: https://github.com/meintechblog/pv-inverter-proxy

# SolarEdge inverter connection
inverter:
  host: "192.168.3.18"    # Your SolarEdge inverter IP
  port: 1502              # Modbus TCP port
  unit_id: 1              # Modbus unit/slave ID

# Modbus proxy server (Venus OS connects here)
proxy:
  port: 502

# Venus OS MQTT (optional — leave host empty to disable)
venus:
  host: ""                # Venus OS / Cerbo GX IP address
  port: 1883              # MQTT port (default 1883)
  portal_id: ""           # Leave empty for auto-discovery

# Web dashboard
webapp:
  port: 80

# Logging
log_level: INFO
YAML
```

### Fix 2: Port 502 Pre-Flight Check (add after root check)

```bash
# Check if port 502 is already in use
if ss -tlnp 2>/dev/null | grep -q ':502 '; then
    echo ""
    echo -e "${BLUE}  Note: Port 502 is currently in use.${NC}"
    ss -tlnp 2>/dev/null | grep ':502 '
    echo ""
    echo -e "  The proxy needs port 502. Stop the conflicting service first."
    echo -e "  Or edit $CONFIG_DIR/config.yaml to use a different port."
    echo ""
fi
```

Note: This should be a warning, not a hard fail -- the port may be held by a previous installation of this same service that will be restarted.

### Fix 3: Existing Config Migration Warning

```bash
if [ -f "$CONFIG_DIR/config.yaml" ]; then
    if grep -q '^solaredge:' "$CONFIG_DIR/config.yaml" 2>/dev/null; then
        echo ""
        echo -e "${RED}  WARNING: Your config uses the old 'solaredge:' key.${NC}"
        echo -e "  The proxy now expects 'inverter:' instead."
        echo -e "  Please update your config:"
        echo -e "    nano $CONFIG_DIR/config.yaml"
        echo -e "  Change 'solaredge:' to 'inverter:' and add a 'venus:' section."
        echo -e "  See: $INSTALL_DIR/config/config.example.yaml"
        echo ""
    fi
    ok "Config exists at $CONFIG_DIR/config.yaml"
fi
```

### Fix 4: Secure Curl Flags in Documentation

```bash
# Current (line 158 and README):
curl -sSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash

# Fixed:
curl -fsSL https://raw.githubusercontent.com/meintechblog/pv-inverter-proxy/main/install.sh | bash
```

The `-f` (--fail) flag prevents bash from executing an HTML error page if GitHub returns 404/500.

### Fix 5: config.example.yaml Venus Section

The example config needs a `venus:` section added:

```yaml
# Venus OS MQTT connection (optional)
venus:
  host: ""                # Venus OS IP (empty = MQTT disabled, proxy runs standalone)
  port: 1883              # MQTT standard port
  portal_id: ""           # Leave empty for auto-discovery via N/+/system/0/Serial
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `solaredge:` config key | `inverter:` config key | Phase 5 (v1.0) | Install script never updated |
| No Venus OS integration | `venus:` config section | Phase 13 (v3.0) | Install script and README need update |
| Test Connection button | Live connection bobbles | Phase 14 (v3.0) | README references old UI |
| No MQTT setup guidance | MQTT setup guide card in UI | Phase 14 (v3.0) | README should document |
| Manual Venus OS config | Auto-detect banner | Phase 15 (v3.0) | README should document |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `cd "/Users/hulki/codex/venus os fronius proxy" && .venv/bin/pytest tests/ -x -q` |
| Full suite command | `cd "/Users/hulki/codex/venus os fronius proxy" && .venv/bin/pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | Install script generates correct YAML with `inverter:` key | manual-only | Visual inspection of install.sh heredoc | N/A |
| DOCS-01 | Install script YAML is valid and loadable by config.py | unit | `pytest tests/test_config.py -x -q` | Existing tests cover config loading |
| DOCS-01 | Secure curl flags (`-fsSL`) in install.sh | manual-only | `grep -q 'fsSL' install.sh` (shell check) | N/A |
| DOCS-02 | README documents `inverter:` key (not `solaredge:`) | manual-only | `grep -q 'inverter:' README.md` (shell check) | N/A |
| DOCS-02 | README mentions Venus OS >= 3.7 | manual-only | `grep -q '3.7' README.md` (shell check) | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/test_config.py -x -q` (ensure config loading still works)
- **Per wave merge:** Full test suite
- **Phase gate:** Full suite green + manual verification of install.sh YAML template parsability

### Wave 0 Gaps
None -- existing test infrastructure covers config loading. DOCS-01/DOCS-02 are primarily documentation tasks verifiable by grep/inspection rather than automated tests. Optionally, a `test_install_yaml_valid` test could parse the heredoc YAML from install.sh, but this is low value given the template is static.

## Open Questions

1. **Should config.example.yaml also be updated?**
   - What we know: It already uses `inverter:` key but lacks `venus:` section
   - Recommendation: Yes, add `venus:` section to config.example.yaml for consistency (single source of truth)

2. **Should the install script auto-migrate old configs?**
   - What we know: Sed-based YAML manipulation is fragile and risky
   - Recommendation: No -- warn the user and point to config.example.yaml. Let them manually update.

3. **Should README include screenshots?**
   - What we know: DOCS-02 mentions "Screenshots" but no screenshot infrastructure exists
   - Recommendation: Add placeholder text noting where screenshots would go, or skip if no screenshot files exist. Do not block phase completion on screenshots.

## Sources

### Primary (HIGH confidence)
- `src/venus_os_fronius_proxy/config.py` - Authoritative config schema (dataclasses with defaults)
- `config/config.example.yaml` - Current reference config (already uses `inverter:` key)
- `install.sh` - Current install script with identified bugs (lines 94, 158)
- `README.md` - Current README with outdated content

### Secondary (HIGH confidence)
- `config/config.local.yaml` - Dev config confirming `inverter:` key usage
- `tests/test_config.py` - Tests confirming expected config behavior
- `.planning/REQUIREMENTS.md` - DOCS-01, DOCS-02 requirement definitions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, only file edits
- Architecture: HIGH - Existing patterns maintained, exact line changes identified
- Pitfalls: HIGH - Bugs are concrete and reproducible (wrong YAML key, missing section)

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable -- shell script and markdown, no dependency churn)
