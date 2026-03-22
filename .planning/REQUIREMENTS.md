# Requirements: Venus OS Fronius Proxy

**Defined:** 2026-03-22
**Core Value:** Venus OS muss alle PV-Inverter als einen virtuellen Fronius-Inverter erkennen und steuern koennen

## v5.0 Requirements

Requirements for MQTT Data Publishing milestone. Each maps to roadmap phases.

### MQTT Publishing

- [ ] **PUB-01**: Proxy publisht Inverter-Daten (Leistung, Spannung, Strom, Temperatur, Status) pro Device an MQTT Broker
- [ ] **PUB-02**: Proxy publisht aggregierte Virtual-PV-Daten (Gesamtleistung, Contributions) an MQTT Broker
- [ ] **PUB-03**: Publish-Intervall ist konfigurierbar (Default: 5s)
- [ ] **PUB-04**: Publisher nutzt Change-based Optimization — kein Publish wenn Daten unveraendert
- [ ] **PUB-05**: Publisher nutzt LWT fuer Online/Offline-Availability-Tracking
- [ ] **PUB-06**: Device-Status-Messages sind retained fuer neue Subscriber

### Home Assistant Integration

- [ ] **HA-01**: Publisher sendet MQTT Auto-Discovery Config Payloads fuer alle Sensoren
- [ ] **HA-02**: Sensoren haben korrekte device_class und state_class fuer HA Energy Dashboard
- [ ] **HA-03**: Inverter erscheinen als gruppierte Devices in HA (Manufacturer, Model, SW Version)
- [ ] **HA-04**: Availability-Entity pro Device reagiert auf LWT

### Broker Connectivity

- [ ] **CONN-01**: MQTT Broker Host/Port ist konfigurierbar (Default: mqtt-master.local:1883)
- [ ] **CONN-02**: Publisher reconnected automatisch mit Exponential Backoff bei Verbindungsverlust
- [ ] **CONN-03**: mDNS Autodiscovery findet MQTT Broker im LAN
- [ ] **CONN-04**: Broker-Konfiguration ist hot-reloadable ohne Service-Restart

### Webapp Config

- [ ] **UI-01**: Config-Seite zeigt MQTT Publishing Settings (Enable/Disable, Broker, Port, Intervall)
- [ ] **UI-02**: mDNS Discovery Button findet Broker im LAN und fuellt Formular
- [ ] **UI-03**: Connection-Status-Dot zeigt ob MQTT Publisher verbunden ist
- [ ] **UI-04**: Topic-Preview zeigt die generierten MQTT Topics

## Future Requirements

### Advanced MQTT

- **ADV-01**: MQTT Username/Password Authentication
- **ADV-02**: TLS-verschluesselte MQTT Verbindung
- **ADV-03**: Custom Topic Templates (User-definierbare Topic-Struktur)

## Out of Scope

| Feature | Reason |
|---------|--------|
| MQTT Bridge/Relay | Proxy ist Publisher, kein Broker |
| Bidirektionale MQTT Steuerung | Steuerung laeuft ueber Venus OS, nicht MQTT |
| InfluxDB/Grafana direkt | MQTT ist der Transport, Consumers bauen Dritte |
| Refactor venus_reader.py MQTT | Bestehender Venus OS MQTT Client bleibt wie er ist |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PUB-01 | TBD | Pending |
| PUB-02 | TBD | Pending |
| PUB-03 | TBD | Pending |
| PUB-04 | TBD | Pending |
| PUB-05 | TBD | Pending |
| PUB-06 | TBD | Pending |
| HA-01 | TBD | Pending |
| HA-02 | TBD | Pending |
| HA-03 | TBD | Pending |
| HA-04 | TBD | Pending |
| CONN-01 | TBD | Pending |
| CONN-02 | TBD | Pending |
| CONN-03 | TBD | Pending |
| CONN-04 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |

**Coverage:**
- v5.0 requirements: 18 total
- Mapped to phases: 0
- Unmapped: 18

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after initial definition*
