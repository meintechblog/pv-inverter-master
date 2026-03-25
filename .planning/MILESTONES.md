# Milestones

## v6.0 Shelly Plugin (Shipped: 2026-03-25)

**Phases completed:** 10 phases, 12 plans, 23 tasks

**Key accomplishments:**

- ShellyPlugin with Gen1/Gen2 profile system polling Shelly devices via REST API and encoding data to SunSpec Model 103 registers
- Shelly relay on/off control wired from webapp REST API through ShellyPlugin.switch() to profile-level HTTP commands, with throttle_enabled=False default for Shelly devices
- mDNS discovery and HTTP probe endpoints for Shelly device detection with Gen1/Gen2/Gen3 support and dedup filtering
- Shelly add-device flow with type card, probe-on-add with hint-card feedback, mDNS discovery, and Shelly-specific config page fields
- ThrottleCaps frozen dataclass with scoring function on InverterPlugin ABC -- SolarEdge 9.7, OpenDTU 7.0, Shelly 2.9
- Device list and snapshot REST APIs enriched with throttle_score (0-10 float) and throttle_mode via compute_throttle_score from plugin layer
- Binary relay dispatch with 300s cooldown hysteresis, startup grace period, and reverse-order re-enable for Shelly devices in PowerLimitDistributor
- Score-based waterfall ordering with convergence tracking and measured response time feedback for auto-throttle mode
- Wired convergence tracking into live poll loop via _extract_ac_power helper and exposed auto_throttle state through virtual snapshot, WebSocket broadcast, and config APIs
- Config-driven convergence presets (aggressive/balanced/conservative) with enriched virtual contributions exposing throttle_score, throttle_mode, throttle_state, relay_on, and measured_response_time_s per device
- Auto-throttle toggle, preset selector, state-colored contribution bar, enhanced 6-column throttle table, and per-device throttle info cards in vanilla JS dashboard
- Wire PowerLimitDistributor into AppContext and DeviceRegistry, fix DC voltage averaging to exclude Shelly zero-DC devices

---

## v4.0 Multi-Source Virtual Inverter (Shipped: 2026-03-21)

**Phases completed:** 4 phases, 8 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v3.1 Auto-Discovery & Inverter Management (Shipped: 2026-03-20)

**Phases completed:** 4 phases, 7 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v3.0 Setup & Onboarding (Shipped: 2026-03-19)

**Phases completed:** 4 phases, 6 plans, 0 tasks

**Key accomplishments:**

- (none recorded)

---

## v2.1 Dashboard Redesign & Polish (Shipped: 2026-03-18)

**Phases:** 9-12 (4 phases, 7 plans)
**Commits:** 34 | **LOC:** +1,223/-79 | **Timeline:** ~2 hours
**Git range:** `feat(09-01)` → `feat(12-01)`

**Key accomplishments:**

1. CSS animation foundation: gauge 0.5s + deadband, entrance animations, prefers-reduced-motion
2. Toast notification system: stacking (max 4), exit animations, click-to-dismiss, duplicate suppression
3. Peak statistics: peak kW, operating hours (MPPT), efficiency indicator with dashboard card
4. Smart event notifications: override, fault, temperature (75C), night mode transitions
5. Venus OS Widget: connection status, Apple-style lock toggle (900s safety cap), confirmation dialog
6. Unified single-page dashboard: inline power control, collapsible override log, 2-row bottom grid

**Requirements:** 19/19 complete (4 ANIM, 5 NOTIF, 3 STATS, 4 VENUS, 3 LAYOUT)

---

## v2.0 Dashboard & Power Control (Shipped: 2026-03-18)

**Phases:** 5-8 (4 phases, 7 plans)
**Commits:** 39 | **LOC:** +3,471/-466 | **Timeline:** ~3 hours
**Git range:** `feat(05-01)` → `feat(08-01)`

**Key accomplishments:**

1. DashboardCollector backend with decoded Modbus registers & 60-min TimeSeriesBuffer
2. Venus OS themed 3-file frontend (HTML/CSS/JS) with sidebar navigation
3. WebSocket push infrastructure for real-time updates without polling
4. Live dashboard: SVG power gauge, 3-phase cards, sparkline chart
5. Power Control page: slider with confirmation, Venus OS override detection, EDPC refresh
6. Inverter status panel with daily energy counter, DC values, temperature display

**Requirements:** 18/18 complete (6 DASH, 7 CTRL, 5 INFRA)

---

## v1.0 Venus OS Fronius Proxy (Shipped: 2026-03-18)

**Phases:** 1-4 (4 phases, 9 plans)

**Key accomplishments:**

1. Modbus TCP proxy translating SolarEdge SE30K to Fronius SunSpec profile
2. Venus OS native recognition as "Fronius SE30K-RW00IBNM4"
3. Bidirectional control: power limiting via Model 123 → SE EDPC translation
4. Plugin architecture for future inverter brands
5. Configuration webapp with register viewer and connection status
6. systemd service with auto-start, night mode state machine

---
