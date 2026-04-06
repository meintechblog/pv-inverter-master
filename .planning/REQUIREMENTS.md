# Requirements: PV-Inverter-Master v7.0 — Sungrow SG-RT Plugin

**Defined:** 2026-04-06
**Core Value:** Venus OS muss alle PV-Inverter als einen virtuellen Fronius-Inverter erkennen und steuern koennen

## v7.0 Requirements

Requirements for Sungrow SG-RT Plugin milestone. Each maps to roadmap phases.

### Plugin Core

- [ ] **PLUG-01**: Sungrow plugin polls live data via Modbus TCP (AC power, voltage, current, frequency, DC MPPT1+MPPT2, temperature, energy counters, running state)
- [ ] **PLUG-02**: Plugin encodes polled data into SunSpec Model 103 registers (identical pattern to SolarEdge/OpenDTU)
- [ ] **PLUG-03**: Plugin supports reconfigure (host/port/unit_id change without restart)
- [ ] **PLUG-04**: Plugin declares ThrottleCaps (proportional mode, ~2s Modbus response time)

### Power Control

- [ ] **CTRL-01**: Plugin can write power limit (0-100%) via Sungrow Modbus holding registers
- [ ] **CTRL-02**: Power limit integrates with score-based waterfall distributor

### Dashboard

- [ ] **DASH-01**: Device dashboard shows Power Gauge with rated power
- [ ] **DASH-02**: 3-Phase AC table (L1/L2/L3 voltage, current, power)
- [ ] **DASH-03**: DC section shows MPPT1 and MPPT2 channels (voltage, current, power)
- [ ] **DASH-04**: Connection card shows inverter state (Run/Standby/Derating/Fault) and temperature
- [ ] **DASH-05**: Register viewer with Sungrow-specific register labels

### Add Device Flow

- [ ] **ADD-01**: Type card "Sungrow" als vierte Option neben SolarEdge/OpenDTU/Shelly
- [ ] **ADD-02**: Modbus TCP probe (read device type code + serial) before saving
- [ ] **ADD-03**: Auto-Discovery via Netzwerk-Scan (Port 502, Sungrow device type detection)

### Config & Integration

- [ ] **CFG-01**: Config form with Host, Port, Unit ID, Rated Power, Throttle Enabled
- [ ] **CFG-02**: Sungrow data flows into virtual PV inverter aggregation
- [ ] **CFG-03**: MQTT publisher includes Sungrow device data

## v8.0+ Requirements

Deferred to future release.

### Extended Sungrow Support

- **SGEXT-01**: Support for Sungrow hybrid inverters (SH-RT series with battery)
- **SGEXT-02**: Battery charge/discharge control via Modbus
- **SGEXT-03**: Support for multiple Sungrow inverters on same WiNet-S

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sungrow Cloud/iSolarCloud API | Nur lokale Modbus TCP, kein Cloud-Account noetig |
| WiNet-S HTTP API (WebSocket) | Modbus TCP ist zuverlaessiger und standardisierter |
| Battery management (SH-RT) | Nur PV-Inverter-Funktionalitaet, Battery ist separates Thema |
| Sungrow firmware updates | Ausserhalb des Proxy-Scope |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLUG-01 | Phase 38 | Pending |
| PLUG-02 | Phase 38 | Pending |
| PLUG-03 | Phase 38 | Pending |
| PLUG-04 | Phase 38 | Pending |
| CTRL-01 | Phase 41 | Pending |
| CTRL-02 | Phase 41 | Pending |
| DASH-01 | Phase 39 | Pending |
| DASH-02 | Phase 39 | Pending |
| DASH-03 | Phase 39 | Pending |
| DASH-04 | Phase 39 | Pending |
| DASH-05 | Phase 39 | Pending |
| ADD-01 | Phase 40 | Pending |
| ADD-02 | Phase 40 | Pending |
| ADD-03 | Phase 40 | Pending |
| CFG-01 | Phase 42 | Pending |
| CFG-02 | Phase 42 | Pending |
| CFG-03 | Phase 42 | Pending |

**Coverage:**
- v7.0 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-04-06*
*Last updated: 2026-04-06 after roadmap creation*
