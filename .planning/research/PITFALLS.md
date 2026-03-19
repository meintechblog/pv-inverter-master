# Domain Pitfalls: Setup & Onboarding (v3.0)

**Domain:** IoT proxy setup/onboarding — config hot-reload, MQTT reconnection, connection status, install scripts
**Researched:** 2026-03-19
**Applies to:** v3.0 milestone (adding setup flow to existing running system)

## Critical Pitfalls

Mistakes that cause data loss, broken inverter control, or bricked installs.

### Pitfall 1: Config Hot-Reload Mutates Shared State Mid-Operation

**What goes wrong:** The existing `config_save_handler` in `webapp.py` (lines 248-265) mutates the live `Config` dataclass in-place (`config.inverter.host = host`) and then calls `plugin.reconfigure()`. If the reconfigure fails partway through, the in-memory config has the new values but the running connection is in a broken state. Adding MQTT config hot-reload multiplies this risk -- the MQTT loop reads `VENUS_HOST` and `PORTAL_ID` as module-level constants, so "reconfigure" currently means restarting the whole loop task.

**Why it happens:** Mutable shared state without transactional semantics. The current code sets `reconfiguring = True` as a flag but has no rollback path if `plugin.reconfigure()` throws.

**Consequences:**
- Dashboard shows "reconfiguring" forever if exception is swallowed
- MQTT reconnects to old host while config file says new host (config/runtime drift)
- Venus OS loses power control during a botched reconfigure

**Prevention:**
- Apply config changes atomically: build a NEW config object, validate it, swap the reference. Keep the old config for rollback on failure.
- For MQTT: cancel the existing `venus_mqtt_loop` task and create a new one with updated host/portal_id rather than trying to hot-patch module globals.
- Set a timeout on reconfigure operations (e.g., 10s). If timeout expires, rollback to previous config.
- The `save_config()` function already uses atomic file write (temp + `os.replace`). Match this pattern for in-memory state.

**Detection:** Config file and runtime state diverge. Add a `/api/config/effective` endpoint that returns what is actually running (not just what was loaded).

**Phase:** Config page implementation (earliest phase). Must be designed before building the UI.

---

### Pitfall 2: MQTT Raw Socket Reconnection Loses Subscriptions Silently

**What goes wrong:** The current `venus_reader.py` reconnects after any exception with a 5s delay (line 209-210), re-subscribes and re-requests initial values. The dangerous edge case: the socket TCP handshake succeeds but MQTT CONNACK indicates session-rejected. In the current raw socket implementation, the CONNACK response (line 32: `s.recv(4)`) is read but **never parsed** -- a rejected connection or error code is silently ignored.

**Why it happens:** Raw socket MQTT implementation skips protocol-level error handling. The 4-byte CONNACK has a return code at byte 4 that must be checked (0x00 = accepted, anything else = rejected). Current code assumes success.

**Consequences:**
- MQTT appears "connected" but receives no messages
- Dashboard shows stale Venus OS settings (last known values from `shared_ctx["venus_settings"]`)
- Venus OS lock/override detection stops working -- user thinks system is active but MQTT is dead
- No log entry for the actual failure since `s.recv(4)` does not validate

**Prevention:**
- Parse CONNACK return code: `connack = s.recv(4); if connack[3] != 0: raise ConnectionError(f"MQTT rejected: {connack[3]}")`
- Add an MQTT connection status field to `shared_ctx` (e.g., `shared_ctx["mqtt_connected"] = True/False` with timestamp)
- Surface this status in the dashboard -- this is exactly what the "greyed-out elements" feature needs
- Add a keepalive watchdog: if no MQTT message received for 60s (including PINGRESP), force reconnect

**Detection:** Dashboard elements that depend on MQTT data show stale timestamps. Add `mqtt_last_message_ts` to the status API.

**Phase:** MQTT configurable phase. Fix CONNACK parsing as prerequisite before making host/portal configurable.

---

### Pitfall 3: Venus OS Auto-Discovery Race Between Modbus Accept and MQTT Setup

**What goes wrong:** The plan is to auto-detect Venus OS by watching for incoming Modbus connections. But the proxy server starts before MQTT is configured. If Venus OS connects via Modbus, the proxy detects it and tries to auto-configure MQTT to the same IP -- but the MQTT connection attempt might happen while Venus OS is still in its own startup sequence (MQTT broker not yet ready). The auto-config "succeeds" (saves to config) but MQTT fails silently.

**Why it happens:** Temporal coupling -- Modbus TCP connection arriving does not guarantee MQTT readiness on the same host. Venus OS boots Modbus client before MQTT broker in some firmware versions.

**Consequences:**
- Config saved with correct Venus OS IP but MQTT never connects
- User sees "Venus OS detected" success message but dashboard elements stay greyed out
- User has to manually trigger reconnect or restart service

**Prevention:**
- Auto-discovery should detect the Modbus connection source IP but NOT immediately save it as confirmed config
- Show the detected IP as a "suggestion" with a "Test & Apply" button
- MQTT connection test (connect + subscribe + receive at least one message within 5s) must succeed before marking as configured
- Implement retry with backoff specifically for the initial MQTT setup (separate from the main reconnect loop)

**Detection:** Add a `setup_state` enum: `unconfigured -> detected -> testing -> confirmed -> failed`. Expose in status API and UI.

**Phase:** Venus OS auto-discovery phase. Design the state machine before implementing detection.

---

### Pitfall 4: Install Script curl|bash Overwrites User Config on Update

**What goes wrong:** The current `install.sh` (line 88) only creates config if missing (`if [ ! -f ... ]`), which is correct for fresh installs. But when adding MQTT config fields to `config.yaml`, existing users who update via `curl | bash` keep their old config without the new `mqtt:` section. The app then falls back to hardcoded defaults (`VENUS_HOST = "192.168.3.146"`) -- but once those hardcoded values are removed (the whole point of making MQTT configurable), the app crashes or silently uses wrong defaults.

**Why it happens:** Config schema evolution without migration. The install script preserves existing config (good) but has no mechanism to merge new fields into existing config (bad).

**Consequences:**
- Existing users who update get a broken MQTT setup
- New users get a config with MQTT section, existing users do not -- inconsistent behavior
- If defaults are removed from code (to force config), existing installs break

**Prevention:**
- Keep all defaults in the `Config` dataclass (as currently done) -- never remove fallback defaults from code
- Add a config migration step to `install.sh`: check if `mqtt:` section exists in existing config, append it if missing
- Better: have the app detect missing config sections and show a setup wizard in the UI ("New: MQTT configuration available -- configure now")
- Version the config schema (add `version: 2` field). App detects old version and prompts for update.

**Detection:** Log a warning at startup for each config section that uses defaults: `"mqtt section missing from config, using defaults"`. This makes the issue visible in `journalctl`.

**Phase:** Install script polish phase. Must be coordinated with config page implementation.

---

### Pitfall 5: Connection Status Bobble Shows False Positives During Transient States

**What goes wrong:** The config page plans a "live connection bobble" (green/red indicator). The existing `status_handler` returns `solaredge: conn_mgr.state.value` and `venus_os: "active"` (hardcoded!). Multiple race conditions:

1. **SolarEdge status during reconfigure:** `reconfiguring` flag is set (line 255) but the bobble might poll status between disconnect and reconnect, showing "reconnecting" briefly even on successful reconfigure
2. **Venus OS always "active":** Currently hardcoded to `"active"` -- adding real MQTT status creates a period where the bobble flips between states during normal MQTT keepalive cycles
3. **Frontend polling vs WebSocket:** If the config page polls `/api/status` while the dashboard uses WebSocket, they can show contradictory connection states

**Why it happens:** Connection status is inherently a lagging indicator. The proxy checks connectivity via poll results, not via a dedicated health check. Network state changes are async -- the status API returns a snapshot that may be milliseconds stale.

**Consequences:**
- User sees green bobble, saves config, inverter is actually unreachable
- Bobble flickers red/green during normal operation (MQTT keepalive timeout = 1s in current code)
- User loses trust in the status indicator and ignores real failures

**Prevention:**
- Debounce status transitions: require 3 consecutive failed polls (3s) before showing "disconnected". Show "checking..." during transitions.
- Replace hardcoded `venus_os: "active"` with actual MQTT connection state from `shared_ctx`
- Use WebSocket for status updates on the config page too (not polling) -- single source of truth
- Add "last successful communication" timestamps for both SolarEdge and MQTT, show relative time ("2s ago", "45s ago")

**Detection:** If `last_successful_poll` age > 5s but status shows "connected", something is wrong. Add a consistency check.

**Phase:** Config page phase. Design the status model before building the bobble UI.

## Moderate Pitfalls

### Pitfall 6: MQTT Topic Prefix Breaks When Portal ID Is Wrong

**What goes wrong:** Venus OS portal ID (`88a29ec1e5f4`) is currently hardcoded. When making it configurable, if the user enters the wrong portal ID, MQTT subscribes to topics that don't exist. No error -- just silence. MQTT wildcard subscriptions succeed even for nonexistent topic prefixes.

**Prevention:**
- After subscribing, wait 5s for at least one message. If nothing received, warn the user that the portal ID might be wrong.
- Auto-detect portal ID: subscribe to `N/+/system/0/Serial` (wildcard for any portal ID), extract the portal ID from the first message received. This is the strongly recommended approach over manual entry.
- Show the detected portal ID in the config UI for confirmation.

**Phase:** MQTT configurable phase. Auto-detection strongly recommended over manual entry.

---

### Pitfall 7: Config Page Save While Venus OS Is Actively Writing Power Limits

**What goes wrong:** User opens config page, changes SolarEdge IP, hits save. `plugin.reconfigure()` disconnects from the old inverter and connects to the new one. During this window (1-5s), Venus OS writes a power limit via Modbus. `StalenessAwareSlaveContext.async_setValues()` tries to forward via `self._plugin.write_power_limit()`, but the plugin is mid-reconnection. Exception propagates as Modbus error to Venus OS.

**Prevention:**
- Queue incoming Venus OS writes during reconfiguration (buffer for max 10s)
- Return Modbus "device busy" (exception code 0x06) during reconfigure instead of 0x04
- Replay buffered writes after reconnection succeeds
- Alternatively: disable reconfigure if `control_state.last_source == "venus_os"` and limit was written < 60s ago. Force user to wait.

**Phase:** Config page phase. Add reconfigure guard before implementing save handler.

---

### Pitfall 8: Greyed-Out Dashboard Elements Re-Enable Before MQTT Is Stable

**What goes wrong:** Plan says "grey out dashboard elements until MQTT connected." If the implementation checks `shared_ctx["mqtt_connected"]` and MQTT connects briefly then drops, the UI enables elements, user interacts, then elements grey out again mid-interaction (e.g., while dragging the power clamp slider).

**Prevention:**
- Require MQTT to be connected for at least 10s before enabling dependent UI elements
- Use a "stable connection" flag: connected AND received at least 3 messages AND no disconnects in last 10s
- When MQTT drops after being stable, show a toast notification instead of immediately greying out (give 30s grace period)
- Disable interactive controls (Lock, Override, Venus Settings write) immediately on MQTT loss, but keep read-only display elements visible with a "stale" indicator

**Phase:** MQTT setup guide / greyed-out elements phase. Define the state machine before CSS.

---

### Pitfall 9: Blocking Socket Operations in Async Event Loop

**What goes wrong:** The current `venus_reader.py` uses blocking `socket.socket` calls inside an async function with `await asyncio.sleep(0.1)` between reads. This works when MQTT is the only consumer, but adding config test connections, MQTT connection tests for auto-discovery, and concurrent status checks increases the chance of blocking the event loop. The `s.settimeout(1)` means each `s.recv()` can block for up to 1 second.

**Prevention:**
- Wrap blocking socket calls in `asyncio.get_event_loop().run_in_executor(None, ...)` for the MQTT reader
- Better: for new MQTT connections (config test, auto-discovery), use `asyncio.open_connection()` instead of raw `socket.socket`. Keep the existing raw socket for the main reader to avoid regression risk.
- For config test connections (`config_test_handler`), already uses `AsyncModbusTcpClient` which is correct. Apply the same async pattern to MQTT test connections.

**Phase:** MQTT configurable phase. Address when adding MQTT connection testing.

---

### Pitfall 10: Three Hardcoded Venus OS IPs and Two Hardcoded Portal IDs

**What goes wrong:** Venus OS connection details are scattered across three locations:
1. `venus_reader.py` line 19: `VENUS_HOST = "192.168.3.146"`
2. `webapp.py` line 598: `AsyncModbusTcpClient("192.168.3.146", port=502)` in `venus_write_handler`
3. `webapp.py` line 677: `_mqtt_write_venus("192.168.3.146", "88a29ec1e5f4", ...)` in `venus_dbus_handler`

And two portal IDs:
1. `venus_reader.py` line 18: `PORTAL_ID = "88a29ec1e5f4"`
2. `webapp.py` line 677: same hardcoded string

If only some of these are updated to read from config, the system uses different hosts for different operations. The MQTT reader connects to the configured host, but `venus_dbus_handler` still writes to the hardcoded IP.

**Prevention:**
- Make MQTT config a first-class `MqttConfig` dataclass (host, port, portal_id) on the `Config` object
- Pass `config.mqtt` to all consumers through their constructors or through `shared_ctx`
- Search for all occurrences of `192.168.3.146` and `88a29ec1e5f4` before considering the task complete
- Add a grep-test in CI: `grep -r "192.168.3" src/ && exit 1` to prevent future hardcoding

**Phase:** MQTT configurable phase. This IS the core task -- enumerate all locations first.

## Minor Pitfalls

### Pitfall 11: Config YAML Key Mismatch Between Install Script and Code

**What goes wrong:** The install script template (line 94) uses `solaredge:` as the YAML key, but `config.py` uses `inverter:`. Fresh installs from the script create configs that don't match what the code expects. The app falls back to defaults silently (because of the `data.get("inverter", {})` pattern), so it appears to work but uses the hardcoded default IP instead of what the user configured.

**Prevention:**
- Align the install script template with `config.py` field names immediately
- Add a startup log that prints the effective config: `log.info("loaded_config", inverter_host=config.inverter.host, ...)`
- Add a config validation step that warns about unknown top-level keys (e.g., `solaredge` is unknown)

**Phase:** Install script polish phase. Quick fix, do first.

---

### Pitfall 12: WebSocket Clients Miss Config Change Events

**What goes wrong:** When config is saved via the config page, the dashboard clients connected via WebSocket don't know the proxy is reconfiguring. They continue showing old data. If the new SolarEdge IP is unreachable, dashboard clients see stale data until the cache staleness timeout (30s) triggers.

**Prevention:**
- Broadcast a `{"type": "reconfiguring"}` message to all WebSocket clients when config save starts
- Broadcast `{"type": "reconfigured", "success": true/false}` when complete
- Config page and dashboard should both be WebSocket clients that react to these events

**Phase:** Config page phase.

---

### Pitfall 13: venus_mqtt_loop Task Is Fire-and-Forget

**What goes wrong:** The MQTT loop is started as `asyncio.create_task()` in `__main__.py` line 155, but the task reference (`venus_task`) is stored in a local variable, never in `shared_ctx`. To make MQTT reconfigurable (stop the old loop, start a new one with different host), you need a reference to cancel the task. Without it, you either leak tasks or have two MQTT loops running concurrently to the same broker.

**Prevention:**
- Store the task in `shared_ctx["venus_task"]` immediately after creation
- Add a `restart_mqtt(shared_ctx, new_host, new_portal_id)` helper that cancels the old task, waits for cancellation, and creates a new one
- Guard against concurrent restarts with a lock or a "restarting" flag

**Phase:** MQTT configurable phase. Prerequisite for MQTT hot-reload.

---

### Pitfall 14: Install Script Runs apt-get update on Every Update

**What goes wrong:** The install script always runs `apt-get update -qq` (line 47), even on updates where dependencies haven't changed. On slow connections or rate-limited mirrors, this adds 30-60s to every update. On airgapped or custom-repo systems, it can fail entirely.

**Prevention:**
- Skip `apt-get update` if all required packages are already installed: `dpkg -l python3 python3-venv git 2>/dev/null | grep -q "^ii" && skip_apt=true`
- Add a `--skip-deps` flag for updates
- Better: separate "install" and "update" code paths in the script

**Phase:** Install script polish phase.

---

### Pitfall 15: Service User Permissions for New Config Files

**What goes wrong:** Adding new files to `/etc/venus-os-fronius-proxy/` (like `mqtt_state.json`, auto-discovered settings) may fail if the `fronius-proxy` service user doesn't have write permissions. The install script sets `chown -R` (line 121) at install time but not after updates add new file patterns.

**Prevention:**
- Ensure the service user owns the config directory itself (not just existing files)
- Use the existing `tempfile.mkstemp(dir=config_dir)` pattern from `save_config()` for all new state files
- The existing `last_limit.json` and `ui_state.json` already write to this directory -- verify they work after a fresh install

**Phase:** Install script polish phase.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Config page with defaults | In-memory config mutation without rollback (Pitfall 1) | Atomic config swap pattern |
| Config page live bobble | False positive status during transients (Pitfall 5) | Debounce + timestamps |
| Config page save | Venus OS writes during reconfigure (Pitfall 7) | Queue writes, return "device busy" |
| Config page save | WebSocket clients unaware of reconfigure (Pitfall 12) | Broadcast reconfigure events |
| Venus OS auto-discovery | Race between Modbus detect and MQTT ready (Pitfall 3) | Detect -> suggest -> test -> confirm flow |
| MQTT configurable | Silent subscription failure on wrong portal ID (Pitfall 6) | Auto-detect portal ID via wildcard |
| MQTT configurable | CONNACK not parsed, silent failure (Pitfall 2) | Parse return code before declaring connected |
| MQTT configurable | Three hardcoded IPs, two hardcoded portal IDs (Pitfall 10) | Enumerate all, make first-class config |
| MQTT configurable | Fire-and-forget task not cancellable (Pitfall 13) | Store task ref in shared_ctx |
| MQTT configurable | Blocking sockets in async loop (Pitfall 9) | Use executor or asyncio streams for new code |
| MQTT setup guide + greyed-out | UI flicker on MQTT reconnect (Pitfall 8) | Stable-connection threshold (10s + 3 messages) |
| Install script polish | Config schema drift on updates (Pitfall 4) | Keep code defaults, log missing sections |
| Install script polish | YAML key mismatch solaredge vs inverter (Pitfall 11) | Fix immediately, add unknown-key warning |
| Install script polish | apt-get on every update (Pitfall 14) | Skip if deps present |
| Install script polish | Permissions for new config files (Pitfall 15) | chown directory, use tempfile pattern |

## Codebase-Specific Observations

Patterns in the existing code that will interact with v3.0 features:

1. **`shared_ctx` is an untyped dict:** As more features add keys (`mqtt_connected`, `setup_state`, `venus_host`, `venus_task`), this becomes error-prone. Consider a `@dataclass SharedContext` before adding more keys. Every v3.0 feature adds at least one new key.

2. **No config change notification mechanism:** The webapp holds `app["config"]` as a direct reference. There is no observer pattern for "config changed." When MQTT config is added, the venus_reader needs to know config changed. Currently the only way is to cancel and recreate the task.

3. **`_mqtt_write_venus` is a synchronous blocking function** (webapp.py lines 625-655) that creates a new TCP connection for every single Venus OS dbus write, including a `time.sleep(0.5)`. This blocks the aiohttp event loop for 500ms+ per write. It should be wrapped in `run_in_executor` or rewritten to use the existing MQTT connection from `venus_reader`.

4. **Dual MQTT paths exist:** `venus_reader.py` maintains a long-lived MQTT connection for reading. `_mqtt_write_venus` in `webapp.py` creates a new throwaway connection for each write. Making MQTT configurable means both paths need the same host/portal_id. Consider consolidating into a single MQTT client that handles both reads and writes.

## Sources

- Direct code analysis of the existing codebase (HIGH confidence -- primary source)
- `venus_reader.py`: raw socket MQTT implementation, reconnection logic, hardcoded constants
- `webapp.py`: config save handler, status handler, venus_dbus_handler, MQTT write function
- `config.py`: dataclass schema, save_config atomic write, validation
- `control.py`: ControlState, lock, clamp, persist patterns
- `proxy.py`: StalenessAwareSlaveContext, poll loop, shared_ctx population
- `__main__.py`: task creation, shutdown handling, task lifecycle
- `install.sh`: install/update flow, config template, permissions
- `config.example.yaml`: config schema (vs install script template mismatch)
- MQTT 3.1.1 specification for CONNACK return codes (HIGH confidence)
- asyncio documentation for blocking call patterns (HIGH confidence)
