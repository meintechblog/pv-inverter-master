# Technology Stack

**Project:** Venus OS Fronius Proxy v2.1 Dashboard Redesign & Polish
**Researched:** 2026-03-18
**Scope:** Stack additions for CSS animations, toast notifications, Venus OS info widget, Apple-style toggles, peak statistics. Zero new dependencies.

## Recommended Stack

### No New Dependencies Required

The entire v2.1 feature set is implementable with the existing stack. No new Python packages, no new JS libraries, no build tools. This section documents the **patterns and techniques** to use within the existing stack.

### Existing Stack (Unchanged)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Python | 3.12 | Backend runtime | Keep |
| pymodbus | 3.8+ | Modbus TCP client/server | Keep |
| aiohttp | latest | HTTP + WebSocket server | Keep |
| structlog | latest | Structured logging | Keep |
| PyYAML | latest | Config file parsing | Keep |
| Vanilla JS | ES6+ | Frontend (zero deps) | Keep |
| CSS3 | Modern | Styling + animations | **Extend** |

## CSS Animations & Transitions

**Confidence: HIGH** (well-documented browser standards, verified with MDN and multiple 2025/2026 guides)

### GPU-Accelerated Properties Only

Animate ONLY these properties for 60fps performance -- they run on the GPU compositor thread without triggering layout or paint:

| Property | Use Case | Why GPU-Safe |
|----------|----------|--------------|
| `transform` | Gauge needle rotation, slide-in/out, scale effects | Compositor-only, no reflow |
| `opacity` | Fade in/out toasts, page transitions, pulse effects | Compositor-only, no repaint |
| `filter` | Blur effects (sparingly) | GPU-accelerated in modern browsers |

**NEVER animate:** `width`, `height`, `top`, `left`, `margin`, `padding`, `border-width`, `font-size`. These trigger layout recalculation and are slow.

### CSS Custom Properties for Animation Control

Use existing CSS custom properties (`--ve-*`) to parameterize animations. Add new animation-specific variables:

```css
:root {
    /* Animation timing */
    --ve-duration-fast: 150ms;
    --ve-duration-normal: 300ms;
    --ve-duration-slow: 600ms;
    --ve-easing-default: cubic-bezier(0.4, 0, 0.2, 1);  /* Material ease */
    --ve-easing-spring: cubic-bezier(0.34, 1.56, 0.64, 1);  /* Overshoot */
    --ve-easing-out: cubic-bezier(0, 0, 0.2, 1);
}
```

### Specific Animation Techniques

#### 1. Gauge Arc Animation (Already Partially Done)

The existing `#gauge-fill` uses `transition: stroke-dashoffset 0.8s ease-out, stroke 0.5s ease` which is correct. Enhance with:

```css
#gauge-fill {
    transition: stroke-dashoffset 0.8s var(--ve-easing-default),
                stroke 0.5s ease;
    will-change: stroke-dashoffset;  /* Hint to browser for GPU layer */
}
```

`will-change` promotes the element to its own compositor layer. Use sparingly (only on elements that actually animate frequently).

#### 2. Page/Section Transitions

Current page switching is `display: none/block` (instant). For smooth transitions:

```css
.page {
    opacity: 0;
    transform: translateY(8px);
    transition: opacity var(--ve-duration-normal) var(--ve-easing-out),
                transform var(--ve-duration-normal) var(--ve-easing-out);
    pointer-events: none;
}
.page.active {
    opacity: 1;
    transform: translateY(0);
    pointer-events: auto;
}
```

**Caveat:** Cannot use `display: none` with transitions. Must switch to `visibility: hidden` + `position: absolute` or use a class-based approach where inactive pages are off-screen. Alternative: use a simple fade with JS controlling `requestAnimationFrame`.

#### 3. Widget Entrance Animations (Staggered)

```css
@keyframes ve-slide-up {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}

.ve-card {
    animation: ve-slide-up var(--ve-duration-normal) var(--ve-easing-out) both;
}

/* Stagger with nth-child or custom property */
.ve-dashboard-grid .ve-card:nth-child(1) { animation-delay: 0ms; }
.ve-dashboard-grid .ve-card:nth-child(2) { animation-delay: 50ms; }
.ve-dashboard-grid .ve-card:nth-child(3) { animation-delay: 100ms; }
.ve-dashboard-grid .ve-card:nth-child(4) { animation-delay: 150ms; }
```

#### 4. Value Change Flash (Already Done, Enhance)

The existing `flashValue()` JS function adds/removes `ve-value-flash` class. The existing `ve-flash` keyframe animation is correct. No changes needed -- this pattern works well.

#### 5. `prefers-reduced-motion` Respect

```css
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

**Always include this.** Accessibility requirement.

### Performance Notes

- `will-change` should be applied via JS just before animation starts, removed after. Or applied statically only to elements that animate constantly (gauge).
- `transform: translateZ(0)` or `translate3d(0,0,0)` forces GPU layer -- use as fallback if `will-change` is insufficient.
- Avoid animating more than ~5 elements simultaneously on low-power devices (Raspberry Pi browser).

## Toast Notification System

**Confidence: HIGH** (vanilla JS pattern, well-established, existing basic implementation already in codebase)

### Current State

The codebase already has a basic `showToast(message, type)` function (app.js line 670-678) and CSS styling (style.css line 957-990). It works but is minimal:
- Single toast at a time (new one replaces old)
- No stacking
- No dismiss button
- No exit animation
- Fixed 3-second timeout

### Enhanced Pattern (Vanilla JS, No Dependencies)

```javascript
// Toast container for stacking
const toastContainer = document.createElement('div');
toastContainer.className = 've-toast-container';
document.body.appendChild(toastContainer);

function showToast(message, type, duration) {
    duration = duration || 4000;
    const toast = document.createElement('div');
    toast.className = 've-toast ve-toast--' + (type || 'info');
    toast.textContent = message;

    // Insert at top for newest-first stacking
    toastContainer.prepend(toast);

    // Auto-dismiss with exit animation
    const timer = setTimeout(function() { dismissToast(toast); }, duration);

    // Click to dismiss
    toast.addEventListener('click', function() {
        clearTimeout(timer);
        dismissToast(toast);
    });
}

function dismissToast(toast) {
    toast.classList.add('ve-toast--exiting');
    toast.addEventListener('animationend', function() {
        toast.remove();
    });
}
```

### Toast CSS

```css
.ve-toast-container {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
    max-width: 380px;
}

.ve-toast {
    pointer-events: auto;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.9em;
    font-weight: 500;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    cursor: pointer;
    animation: ve-toast-in 0.3s var(--ve-easing-out) forwards;
}

.ve-toast--exiting {
    animation: ve-toast-out 0.25s var(--ve-easing-default) forwards;
}

@keyframes ve-toast-in {
    from { opacity: 0; transform: translateX(100%); }
    to   { opacity: 1; transform: translateX(0); }
}

@keyframes ve-toast-out {
    from { opacity: 1; transform: translateX(0); }
    to   { opacity: 0; transform: translateX(100%); }
}

/* Warning variant for temperature/night mode */
.ve-toast--warning {
    background: rgba(240, 150, 46, 0.95);
    color: #000;
}
```

### Toast Types for v2.1

| Type | Color | Trigger |
|------|-------|---------|
| `success` | Green (`--ve-green`) | Power limit applied, config saved |
| `error` | Red (`--ve-red`) | Venus OS override, connection lost, fault |
| `warning` | Orange (`--ve-orange`) | Temperature warning, night mode transition |
| `info` | Blue (`--ve-blue`) | Override event, status change |

## Apple-Style Toggle Switch

**Confidence: HIGH** (pure CSS technique, well-documented, no JS needed for the toggle itself)

### CSS-Only Implementation

Uses a hidden checkbox + styled label with `::before` pseudo-element as the sliding dot:

```css
/* Toggle switch container */
.ve-toggle {
    position: relative;
    display: inline-block;
    width: 52px;
    height: 28px;
}

.ve-toggle input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
}

.ve-toggle-track {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background: var(--ve-border);
    border-radius: 28px;
    transition: background var(--ve-duration-normal) var(--ve-easing-default);
}

.ve-toggle-track::before {
    content: '';
    position: absolute;
    height: 22px;
    width: 22px;
    left: 3px;
    bottom: 3px;
    background: var(--ve-text);
    border-radius: 50%;
    transition: transform var(--ve-duration-normal) var(--ve-easing-spring);
    /* Spring easing gives the Apple bounce feel */
}

.ve-toggle input:checked + .ve-toggle-track {
    background: var(--ve-blue);
}

.ve-toggle input:checked + .ve-toggle-track::before {
    transform: translateX(24px);
}

.ve-toggle input:disabled + .ve-toggle-track {
    opacity: 0.4;
    cursor: not-allowed;
}
```

### HTML Pattern

```html
<label class="ve-toggle">
    <input type="checkbox" id="venus-lock-toggle">
    <span class="ve-toggle-track"></span>
</label>
```

### Integration with Venus OS Lock

The toggle JS handler sends a WebSocket command or REST API call. The toggle is purely visual; actual lock state is managed server-side. The `checked` state reflects whether Venus OS control is allowed (checked = allowed, unchecked = locked out).

## Venus OS Info Widget -- Modbus Register Addresses

**Confidence: MEDIUM** (registers verified via community implementations and partial official docs, but not from the official Excel spreadsheet directly)

### Architecture Decision: Read from Venus OS via Modbus TCP

The proxy currently only communicates with the SolarEdge inverter. To show Venus OS system info, the proxy needs a **new Modbus TCP client** connection to Venus OS at `192.168.3.146:502`.

**Important:** Venus OS must have Modbus TCP enabled: Settings -> Services -> Modbus TCP -> Enabled.

### Venus OS System Registers (Unit ID 100)

| Register | Description | D-Bus Path | Type | Scale | Unit |
|----------|-------------|------------|------|-------|------|
| 840 | Battery Voltage | /Dc/Battery/Voltage | uint16 | 10 | V DC |
| 841 | Battery Current | /Dc/Battery/Current | int16 | 10 | A DC |
| 842 | Battery Power | /Dc/Battery/Power | int16 | 1 | W |
| 843 | Battery SOC | /Dc/Battery/Soc | uint16 | 1 | % |
| 844 | Battery State | /Dc/Battery/State | uint16 | 1 | 0=idle, 1=charging, 2=discharging |
| 817 | AC Consumption L1 | /Ac/Consumption/L1/Power | uint16 | 1 | W |
| 818 | AC Consumption L2 | /Ac/Consumption/L2/Power | uint16 | 1 | W |
| 819 | AC Consumption L3 | /Ac/Consumption/L3/Power | uint16 | 1 | W |
| 820 | Grid Power L1 | /Ac/Grid/L1/Power | int16 | 1 | W |
| 821 | Grid Power L2 | /Ac/Grid/L2/Power | int16 | 1 | W |
| 822 | Grid Power L3 | /Ac/Grid/L3/Power | int16 | 1 | W |
| 850 | PV on DC (MPPT) | /Dc/Pv/Power | uint16 | 1 | W |
| 806 | Relay 0 State | /Relay/0/State | uint16 | 1 | 0=open, 1=closed |
| 807 | Relay 1 State | /Relay/1/State | uint16 | 1 | 0=open, 1=closed |

**Sources:**
- [Victron Community: Home Assistant Modbus Tutorial](https://communityarchive.victronenergy.com/questions/78971/home-assistant-modbus-integration-tutorial.html) (register addresses verified)
- [Victron GX Modbus-TCP Manual](https://www.victronenergy.com/live/ccgx:modbustcp_faq) (Unit ID 100 documentation)
- [victron-system-monitor GitHub](https://github.com/rbritton/victron-system-monitor/blob/master/app/ModbusRegister.php) (PHP implementation with register maps)
- [php-victron-cerbogx-modbus-tcp GitHub](https://github.com/datjan/php-victron-cerbogx-modbus-tcp) (register 843 SOC, 844 state confirmed)

### DVCC Status

**Confidence: LOW** -- DVCC enable/disable is a settings register, not a system register. The CCGX register list Excel file would have the exact address. The proxy can detect DVCC indirectly: if Venus OS writes WMaxLimPct to the proxy's Model 123, DVCC with "Limit charge power" or ESS is active. This is already tracked via `control_state.last_source == "venus_os"`.

**Recommendation:** Do NOT try to read DVCC settings registers. Instead, display whether Venus OS is actively controlling the inverter (already tracked) and show connection status to Venus OS (already tracked via the Modbus server's client connections).

### Implementation: Venus OS Client

Use the existing `pymodbus.client.AsyncModbusTcpClient` (already a dependency) to read from Venus OS:

```python
from pymodbus.client import AsyncModbusTcpClient

class VenusOSClient:
    """Read system registers from Venus OS GX device."""

    UNIT_ID = 100
    SYSTEM_REGISTERS = {
        'battery_voltage': (840, 'uint16', 10),   # V
        'battery_current': (841, 'int16', 10),     # A
        'battery_power':   (842, 'int16', 1),      # W
        'battery_soc':     (843, 'uint16', 1),     # %
        'battery_state':   (844, 'uint16', 1),     # enum
        'grid_l1':         (820, 'int16', 1),       # W
        'grid_l2':         (821, 'int16', 1),       # W
        'grid_l3':         (822, 'int16', 1),       # W
        'pv_power':        (850, 'uint16', 1),      # W
    }

    def __init__(self, host: str, port: int = 502):
        self._client = AsyncModbusTcpClient(host, port=port, timeout=5)

    async def poll(self) -> dict | None:
        """Read system registers, return decoded dict or None on failure."""
        ...
```

**Polling:** Every 5-10 seconds (system data changes slowly). Do NOT poll every 1s like the SE30K -- Venus OS Modbus TCP service is not designed for high-frequency reads.

### Venus OS Connection Info (No Modbus Needed)

Some Venus OS info is available WITHOUT reading from Venus OS:

| Info | Source | Already Available |
|------|--------|-------------------|
| Venus OS IP | Config file | Yes (hardcoded 192.168.3.146) |
| Last Venus OS contact | Modbus server write detection | Yes (control_state.last_change_ts) |
| Venus OS override active | control_state.last_source | Yes |
| Venus OS firmware version | Would need Modbus read from Venus OS | No |

**Recommendation for MVP:** Start with the already-available data (override status, last contact time). Add Venus OS Modbus client as a separate optional feature that can be enabled in config.

## Peak Statistics Tracking

**Confidence: HIGH** (simple in-memory data structure, no external deps needed)

### Implementation Pattern

Track peaks in-memory, reset daily (or on restart). No persistence needed (PROJECT.md explicitly scopes out persistent DB).

```python
import time
from dataclasses import dataclass, field

@dataclass
class PeakStats:
    """Track daily peak statistics in-memory."""
    peak_power_w: float = 0.0
    peak_power_ts: float = 0.0
    first_production_ts: float | None = None
    last_production_ts: float | None = None
    _last_reset_day: int = field(default=0, repr=False)

    def update(self, power_w: float) -> None:
        now = time.time()
        today = time.localtime(now).tm_yday

        # Auto-reset on day change
        if today != self._last_reset_day:
            self.peak_power_w = 0.0
            self.peak_power_ts = 0.0
            self.first_production_ts = None
            self.last_production_ts = None
            self._last_reset_day = today

        if power_w > self.peak_power_w:
            self.peak_power_w = power_w
            self.peak_power_ts = now

        if power_w > 50:  # Threshold for "producing"
            if self.first_production_ts is None:
                self.first_production_ts = now
            self.last_production_ts = now

    @property
    def operating_hours(self) -> float:
        """Hours of production today."""
        if self.first_production_ts and self.last_production_ts:
            return (self.last_production_ts - self.first_production_ts) / 3600
        return 0.0

    def to_dict(self) -> dict:
        return {
            'peak_power_w': self.peak_power_w,
            'peak_power_ts': self.peak_power_ts,
            'operating_hours': round(self.operating_hours, 1),
        }
```

Integrate into `DashboardCollector.collect()` -- call `peak_stats.update(power_w)` and include `peak_stats.to_dict()` in the snapshot.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Animations | CSS `transform` + `opacity` | GSAP / anime.js | Zero-dependency constraint. CSS is sufficient for these effects. |
| Toast system | Vanilla JS (enhance existing) | Toastify / notyf | Zero-dependency constraint. Existing pattern just needs stacking + exit animation. |
| Toggle switch | CSS-only checkbox hack | JS toggle component | CSS-only is simpler, more performant, accessible by default. |
| Venus OS data | pymodbus AsyncModbusTcpClient | MQTT / D-Bus | Modbus TCP is simpler (already using pymodbus), MQTT requires mosquitto setup, D-Bus requires local access to Venus OS. |
| Peak tracking | In-memory dataclass | SQLite / Redis | Out-of-scope per PROJECT.md. In-memory is sufficient for daily peaks. |

## Anti-Patterns to Avoid

| Anti-Pattern | Why Bad | Do This Instead |
|--------------|---------|-----------------|
| `will-change` on everything | Creates too many compositor layers, wastes GPU memory | Only on elements that animate frequently (gauge arc) |
| Animating `height`/`width` | Triggers layout recalc every frame, janky on RPi | Use `transform: scaleY()` or `max-height` with fixed value |
| JS-driven animations via `setInterval` | Misses frames, fights with browser scheduler | Use CSS transitions/animations or `requestAnimationFrame` |
| Toast notifications via `alert()` | Blocks thread, terrible UX | DOM-based toasts with CSS animations |
| Reading Venus OS registers every 1s | Overloads Venus OS Modbus TCP service | Poll every 5-10s, system data is slow-changing |
| Storing peaks in file/DB | Over-engineering, adds failure modes | In-memory with daily auto-reset |

## Installation

No changes to installation. Zero new dependencies.

```bash
# Existing installation is sufficient
pip install -e .

# No additional packages needed for v2.1
```

## Sources

### CSS Animations
- [CSS GPU Acceleration Guide (2025)](https://www.lexo.ch/blog/2025/01/boost-css-performance-with-will-change-and-transform-translate3d-why-gpu-acceleration-matters/) -- will-change and GPU layer promotion
- [CSS Animation Performance (2025)](https://www.usefulfunctions.co.uk/2025/11/08/css-animation-performance-gpu-acceleration-techniques/) -- GPU acceleration techniques
- [CSS Animations Complete Guide (2026)](https://devtoolbox.dedyn.io/blog/css-animations-complete-guide) -- individual transform properties
- [CSS Transforms & Transitions Guide (2026)](https://devtoolbox.dedyn.io/blog/css-transforms-transitions-guide) -- comprehensive transform reference
- [Smashing Magazine: GPU Animation](https://www.smashingmagazine.com/2016/12/gpu-animation-doing-it-right/) -- foundational GPU compositor concepts

### Venus OS Modbus TCP
- [Victron GX Modbus-TCP Manual](https://www.victronenergy.com/live/ccgx:modbustcp_faq) -- official documentation, Unit ID 100
- [CCGX-Modbus-TCP-register-list.xlsx (GitHub)](https://github.com/victronenergy/dbus_modbustcp/blob/master/CCGX-Modbus-TCP-register-list.xlsx) -- official register list (Excel)
- [CCGX-Modbus-TCP-register-list-3.70.xlsx](https://www.victronenergy.com/upload/documents/CCGX-Modbus-TCP-register-list-3.70.xlsx) -- latest version for Venus OS 3.70
- [Victron Community: HA Modbus Tutorial](https://communityarchive.victronenergy.com/questions/78971/home-assistant-modbus-integration-tutorial.html) -- practical register usage examples
- [victron-system-monitor (GitHub)](https://github.com/rbritton/victron-system-monitor/blob/master/app/ModbusRegister.php) -- comprehensive register mapping in PHP
- [php-victron-cerbogx-modbus-tcp (GitHub)](https://github.com/datjan/php-victron-cerbogx-modbus-tcp) -- register 843/844 confirmed
- [Victron Modbus TCP Examples (GitHub)](https://github.com/optio50/Victron_Modbus_TCP) -- Python examples

### Toggle Switch
- [Apple-style toggle implementations](https://freefrontend.com/css-theme-switches/) -- CSS-only patterns
- [Josh W. Comeau: CSS Transitions](https://www.joshwcomeau.com/animation/css-transitions/) -- spring easing, transition best practices
