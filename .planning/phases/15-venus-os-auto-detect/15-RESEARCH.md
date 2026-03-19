# Phase 15: Venus OS Auto-Detect - Research

**Researched:** 2026-03-19
**Domain:** Modbus TCP write interception, frontend notification banners, config auto-population
**Confidence:** HIGH

## Summary

This phase adds Venus OS auto-detection to the proxy. When Venus OS connects to the proxy's Modbus TCP server and sends its first write (to Model 123 registers), the config page shows a banner indicating Venus OS is connected and prompts the user to enter the Venus OS IP for MQTT configuration.

The implementation is straightforward because the existing `StalenessAwareSlaveContext.async_setValues` already intercepts every Modbus write. We need to: (1) add a detection flag in `shared_ctx` when the first Model 123 write arrives, (2) expose this via a new or existing API endpoint, and (3) add a banner in the frontend config page with a "Test & Apply" flow for the Venus OS IP. Critically, auto-detect must NOT auto-save config -- user must confirm.

**Primary recommendation:** Detect Venus OS by flagging the first incoming Modbus write to Model 123 in the existing `async_setValues` path, surface via `/api/status`, and show a config page banner with pre-populated Venus OS IP field and explicit "Test & Apply" button.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SETUP-01 | Venus OS Auto-Config -- Proxy erkennt eingehende Modbus-Verbindung und legt Venus OS Config-Eintrag mit Connection-Bobble an | Detection via `async_setValues` interception in proxy.py; status exposed via `/api/status`; frontend banner with config form on config page |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pymodbus | 3.12.1 | Modbus TCP server (already in use) | Existing dependency, provides `async_setValues` hook |
| aiohttp | (existing) | REST API + WebSocket | Existing dependency for webapp |

### Supporting
No new libraries needed. This phase is purely additive to existing code.

## Architecture Patterns

### Detection Architecture

The detection mechanism is simple and leverages existing code:

```
Venus OS (Modbus client)
    |
    | Modbus TCP write to Model 123 (WMaxLimPct or WMaxLim_Ena)
    v
StalenessAwareSlaveContext.async_setValues()
    |
    | Sets shared_ctx["venus_os_detected"] = True
    | Sets shared_ctx["venus_os_detected_ts"] = time.time()
    v
/api/status endpoint
    |
    | Returns {"venus_os_detected": true, ...}
    v
Frontend (config page)
    |
    | Shows banner: "Venus OS connected! Enter IP to enable MQTT."
    v
User enters Venus OS IP -> "Test & Apply" button
    |
    | POST /api/config with venus.host populated
    v
Config saved, MQTT loop starts
```

### Key Design Decisions

1. **Detection point:** `async_setValues` in `StalenessAwareSlaveContext` -- this is where ALL incoming Modbus writes are intercepted. Any write to Model 123 registers (the only writable registers) means Venus OS is connected.

2. **Detection is sticky until MQTT is configured:** Once `venus_os_detected` is set to `True`, it stays `True` until the user configures venus.host in config. This ensures the banner persists across page loads.

3. **No auto-save:** The detection only sets a flag. The user must explicitly enter the Venus OS IP and click "Test & Apply" to save. This matches the success criteria.

4. **Detection does NOT need client IP from Modbus TCP:** pymodbus 3.12.1's `trace_connect` callback provides a boolean only, not the client address. However, we don't need the client IP -- Venus OS's Modbus client IP is the same machine the user configures for MQTT. The user knows the IP.

5. **Reads also indicate Venus OS presence:** Venus OS reads SunSpec registers before writing. However, reads are harder to distinguish from other clients (e.g., monitoring tools). Writes to Model 123 are the definitive signal since only Venus OS writes power control registers.

### Pattern: Backend Detection Flag

```python
# In proxy.py StalenessAwareSlaveContext.async_setValues:
async def async_setValues(self, fc_as_hex, address, values):
    # Flag Venus OS detection on any Model 123 write
    if (
        self._shared_ctx is not None
        and self._control is not None
        and self._plugin is not None
        and self._control.is_model_123_address(address, len(values))
        and not self._shared_ctx.get("venus_os_detected")
    ):
        self._shared_ctx["venus_os_detected"] = True
        self._shared_ctx["venus_os_detected_ts"] = time.time()
        logger.info("Venus OS detected: first Modbus write to Model 123")

    # ... existing write handling continues
```

### Pattern: Status Endpoint Extension

```python
# In webapp.py status_handler, add to response:
"venus_os_detected": shared_ctx.get("venus_os_detected", False),
```

### Pattern: Frontend Banner (Config Page)

```html
<!-- In index.html, inside #page-config before the form -->
<div id="venus-auto-detect-banner" class="ve-hint-card ve-hint-card--success" style="display:none">
    <div class="ve-hint-header">
        <svg><!-- checkmark icon --></svg>
        <h3>Venus OS Detected</h3>
    </div>
    <p>Venus OS is sending Modbus commands to this proxy.
       Enter the Venus OS IP below to enable MQTT monitoring and control.</p>
</div>
```

### Pattern: WebSocket-Driven Banner Updates

The banner visibility should be driven by WebSocket snapshots (not polling), following the existing pattern for MQTT setup guide and config bobbles. Add `venus_os_detected` to the snapshot broadcast.

```javascript
// In app.js, extend handleSnapshot:
function updateAutoDetectBanner(snapshot) {
    var banner = document.getElementById('venus-auto-detect-banner');
    if (!banner) return;
    var venusHost = document.getElementById('venus-host');
    var hostConfigured = venusHost && venusHost.value.trim() !== '';
    // Show banner only when detected AND venus not yet configured
    if (snapshot.venus_os_detected && !hostConfigured) {
        banner.style.display = '';
    } else {
        banner.style.display = 'none';
    }
}
```

### Anti-Patterns to Avoid

- **Do NOT use `trace_connect` callback:** It only provides a boolean (connected/disconnected), not client IP. And reads from any Modbus client would trigger it (not specific to Venus OS).
- **Do NOT auto-populate the Venus OS IP from the Modbus client IP:** pymodbus 3.12.1 does not expose the client peer address in `async_setValues`. Even if it did, the Modbus TCP client IP might differ from the MQTT IP in complex network setups.
- **Do NOT auto-save config:** The requirement explicitly states "user must confirm before any configuration change takes effect."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting Venus OS | TCP connection sniffer / custom socket handler | `async_setValues` flag in existing write path | Already intercepting all writes; minimal code |
| Config form validation | Custom IP validation in JS | Existing `validate_venus_config` on backend | Already validates IP format and port range |
| Banner UI | Custom notification system | CSS class toggle like existing MQTT setup guide | Consistent with existing UI patterns |

## Common Pitfalls

### Pitfall 1: Banner shows even after MQTT is configured
**What goes wrong:** Banner keeps appearing after user has configured Venus OS MQTT.
**Why it happens:** `venus_os_detected` flag stays True.
**How to avoid:** Show banner only when `venus_os_detected && !venus.host_configured`. The banner disappears naturally once venus host is saved.
**Warning signs:** Banner visible on config page after successful MQTT setup.

### Pitfall 2: Detection resets on proxy restart
**What goes wrong:** Venus OS detection flag is in-memory only and lost on restart.
**Why it happens:** `shared_ctx` is ephemeral.
**How to avoid:** This is actually fine. If Venus OS is configured (venus.host in config.yaml), the banner is hidden. If not configured, Venus OS will write again within seconds of restart and re-trigger detection.
**Warning signs:** None -- this is acceptable behavior.

### Pitfall 3: Race between detection and snapshot broadcast
**What goes wrong:** Detection flag is set but not included in the current snapshot cycle.
**Why it happens:** `venus_os_detected` is set in `async_setValues` (server thread) while snapshot is collected in `_poll_loop`.
**How to avoid:** Include `venus_os_detected` in the status endpoint and also in WebSocket snapshots. The next snapshot cycle (1s) will include it.

### Pitfall 4: Non-Venus Modbus clients trigger detection
**What goes wrong:** A Modbus diagnostic tool writing to Model 123 triggers the banner.
**Why it happens:** Any Model 123 write sets the flag.
**How to avoid:** Acceptable false positive. Only Venus OS and intentional tools write to power control registers. The banner is informational and non-disruptive. User can simply ignore it.

## Code Examples

### Existing Write Interception (Source: proxy.py lines 104-126)

The `async_setValues` method already intercepts all writes and routes Model 123 writes to `_handle_control_write`. Adding detection here requires ~5 lines.

### Existing Status Endpoint (Source: webapp.py lines 186-203)

`status_handler` already returns `venus_os` status and `solaredge` state. Adding `venus_os_detected` is a single line.

### Existing Config Bobble Pattern (Source: app.js)

`updateConfigBobbles()` and `updateSetupGuide()` show how to conditionally display UI elements based on snapshot data. The auto-detect banner follows the same pattern.

### Existing MQTT Setup Guide (Source: index.html lines 285-300)

The `#mqtt-setup-guide` div is the template for the auto-detect banner styling. Same `ve-hint-card` class, same conditional display logic.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No Venus OS detection | Manual entry of Venus OS IP | Phase 14 | User must know Venus OS IP |
| -- | Auto-detect via Modbus write interception | Phase 15 (this) | Guides user to complete MQTT setup |

## Open Questions

1. **Should detection also trigger for Modbus reads (not just writes)?**
   - What we know: Venus OS reads SunSpec registers (model chain discovery) before writing Model 123.
   - What's unclear: Other tools also read registers. Reads are less specific than writes.
   - Recommendation: Stick with writes only. Model 123 writes are definitively Venus OS. Reads would produce false positives.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `.venv/bin/python -m pytest tests/ -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-01a | First Model 123 write sets venus_os_detected in shared_ctx | unit | `.venv/bin/python -m pytest tests/test_proxy.py::TestVenusAutoDetect -x` | No -- Wave 0 |
| SETUP-01b | /api/status includes venus_os_detected field | unit | `.venv/bin/python -m pytest tests/test_webapp.py::TestVenusAutoDetect -x` | No -- Wave 0 |
| SETUP-01c | Banner shows when detected and venus host empty | manual-only | Visual verification in browser | N/A |
| SETUP-01d | Banner hides after venus host configured and saved | manual-only | Visual verification in browser | N/A |
| SETUP-01e | Auto-detect does NOT auto-save config | unit | `.venv/bin/python -m pytest tests/test_webapp.py::TestVenusAutoDetectNoAutoSave -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_proxy.py tests/test_webapp.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_proxy.py::TestVenusAutoDetect` -- test that async_setValues sets detection flag
- [ ] `tests/test_webapp.py::TestVenusAutoDetect` -- test /api/status includes venus_os_detected
- [ ] `tests/test_webapp.py::TestVenusAutoDetectNoAutoSave` -- test detection does not modify config

## Sources

### Primary (HIGH confidence)
- Source code analysis: `proxy.py` -- `StalenessAwareSlaveContext.async_setValues` (lines 104-126)
- Source code analysis: `webapp.py` -- `status_handler` (lines 186-203), `config_save_handler` (lines 248-332)
- Source code analysis: `app.js` -- `updateSetupGuide`, `updateConfigBobbles` patterns
- pymodbus 3.12.1 server internals: `requesthandler.py`, `server.py`, `base.py`

### Secondary (MEDIUM confidence)
- pymodbus `trace_connect` callback: Confirmed to accept `bool` only, no client address info

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all existing code
- Architecture: HIGH - detection mechanism is trivial extension of existing write interception
- Pitfalls: HIGH - well-understood patterns, simple state management

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable, no external dependencies changing)
