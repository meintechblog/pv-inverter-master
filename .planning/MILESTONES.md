# Milestones

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

