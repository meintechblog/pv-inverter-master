# Requirements: Venus OS Fronius Proxy

**Defined:** 2026-03-17
**Core Value:** Venus OS muss den SolarEdge-Inverter genauso erkennen und steuern können wie einen echten Fronius-Inverter

## v1 Requirements

### Protocol Research & Validation

- [ ] **PROTO-01**: dbus-fronius Source Code analysiert — exakte Fronius-Erwartungen (Discovery, Manufacturer-String, SunSpec Models) dokumentiert
- [ ] **PROTO-02**: SolarEdge SE30K Register-Map per Modbus TCP live ausgelesen und validiert
- [ ] **PROTO-03**: Register-Mapping-Spezifikation erstellt (SolarEdge → Fronius SunSpec Translation Table)

### Modbus Proxy Core

- [ ] **PROXY-01**: Modbus TCP Server läuft und akzeptiert Verbindungen von Venus OS
- [ ] **PROXY-02**: SunSpec Common Model (Model 1) korrekt bereitgestellt mit Fronius-Manufacturer-String
- [ ] **PROXY-03**: SunSpec Inverter Model 103 (three-phase) korrekt bereitgestellt mit Live-Daten vom SE30K
- [ ] **PROXY-04**: SunSpec Nameplate Model (Model 120) korrekt bereitgestellt
- [ ] **PROXY-05**: SunSpec Model Chain korrekt aufgebaut (Header → Common → Inverter → Nameplate → End)
- [ ] **PROXY-06**: SolarEdge Register werden per Modbus TCP Client async gepollt
- [ ] **PROXY-07**: Venus OS wird aus Register-Cache bedient (nicht synchron durch-proxied)
- [ ] **PROXY-08**: Scale Factors korrekt übersetzt zwischen SolarEdge und Fronius SunSpec-Profil
- [ ] **PROXY-09**: Venus OS erkennt und zeigt den Proxy als Fronius Inverter an

### Steuerung (Control Path)

- [ ] **CTRL-01**: Venus OS kann Leistungsbegrenzung (Active Power Limit) setzen via SunSpec Model 123
- [ ] **CTRL-02**: Leistungsbegrenzung wird korrekt an SolarEdge SE30K weitergeleitet
- [ ] **CTRL-03**: Steuerungsbefehle werden validiert bevor sie an den Inverter gesendet werden

### Webapp

- [ ] **WEB-01**: Webapp erreichbar über HTTP im LAN
- [ ] **WEB-02**: SolarEdge IP-Adresse und Modbus-Port konfigurierbar über UI
- [ ] **WEB-03**: Verbindungsstatus zu SolarEdge und Venus OS live angezeigt
- [ ] **WEB-04**: Service-Health-Status angezeigt (uptime, letzte erfolgreiche Polls)
- [ ] **WEB-05**: Register-Viewer zeigt Live Modbus Register (SolarEdge-Quell- und Fronius-Ziel-Register)

### Deployment & Betrieb

- [ ] **DEPL-01**: Läuft als systemd Service mit Auto-Start und Restart-on-Failure
- [ ] **DEPL-02**: Automatische Reconnection bei Verbindungsabbruch zum SolarEdge
- [ ] **DEPL-03**: Graceful Handling wenn Inverter offline (Nacht/Wartung) — keine Crash-Loops
- [ ] **DEPL-04**: Strukturiertes Logging (JSON) für systemd Journal

### Architektur

- [ ] **ARCH-01**: Plugin-Interface definiert für Inverter-Marken (SolarEdge als erstes Plugin)
- [ ] **ARCH-02**: Register-Mapping als austauschbares Modul (nicht hardcoded)

## v2 Requirements

### Multi-Inverter

- **MULTI-01**: Mehrere SolarEdge-Inverter gleichzeitig proxyen
- **MULTI-02**: Andere Inverter-Marken als Plugins (Huawei, SMA, etc.)

### Erweiterte Steuerung

- **CTRL-10**: Einspeiseregelung mit konfigurierbarer Ramp-Rate
- **CTRL-11**: Scheduled Power Limiting (zeitgesteuerte Begrenzung)

### Webapp Erweiterungen

- **WEB-10**: Log-Viewer in Webapp
- **WEB-11**: Multi-Inverter Management UI
- **WEB-12**: Auto-Discovery von Invertern im Netzwerk

## Out of Scope

| Feature | Reason |
|---------|--------|
| TLS/Auth für Webapp | Alles im selben LAN, kein Sicherheits-Overhead gewünscht |
| Mobile App | Webapp reicht, responsive Design genügt |
| Historische Datenbank | Venus OS macht Langzeit-Logging selbst |
| Docker/Container-Orchestrierung | Direktes Deployment auf LXC (Debian 13) |
| Andere Inverter-Marken in v1 | Nur SolarEdge SE30K, aber Architektur vorbereitet |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROTO-01 | — | Pending |
| PROTO-02 | — | Pending |
| PROTO-03 | — | Pending |
| PROXY-01 | — | Pending |
| PROXY-02 | — | Pending |
| PROXY-03 | — | Pending |
| PROXY-04 | — | Pending |
| PROXY-05 | — | Pending |
| PROXY-06 | — | Pending |
| PROXY-07 | — | Pending |
| PROXY-08 | — | Pending |
| PROXY-09 | — | Pending |
| CTRL-01 | — | Pending |
| CTRL-02 | — | Pending |
| CTRL-03 | — | Pending |
| WEB-01 | — | Pending |
| WEB-02 | — | Pending |
| WEB-03 | — | Pending |
| WEB-04 | — | Pending |
| WEB-05 | — | Pending |
| DEPL-01 | — | Pending |
| DEPL-02 | — | Pending |
| DEPL-03 | — | Pending |
| DEPL-04 | — | Pending |
| ARCH-01 | — | Pending |
| ARCH-02 | — | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 0
- Unmapped: 26 (will be mapped during roadmap creation)

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after initial definition*
