#!/usr/bin/env python3
"""
Validate SolarEdge SE30K register layout via Modbus TCP.

Connects to the SE30K at 192.168.3.18:1502 and validates:
1. SunSpec header ("SunS") at register 40000
2. Common Model (Model 1) at register 40002
3. Inverter Model at register 40069
4. Model chain walk to discover all available models
5. Summary of PASS/FAIL results

Part of PROTO-02 validation for the Venus OS Fronius Proxy project.
"""

from pymodbus.client import ModbusTcpClient
import struct
import sys
from datetime import datetime, timezone

SE_HOST = "192.168.3.18"
SE_PORT = 1502
SE_UNIT = 1

STATUS_NAMES = {
    1: "OFF", 2: "SLEEPING", 3: "STARTING", 4: "MPPT",
    5: "THROTTLED", 6: "SHUTTING_DOWN", 7: "FAULT", 8: "STANDBY"
}


def regs_to_string(registers):
    """Convert register list to ASCII string, stripping null bytes."""
    raw = b''.join(r.to_bytes(2, 'big') for r in registers)
    return raw.decode('ascii', errors='replace').rstrip('\x00').strip()


def to_int16(value):
    """Convert unsigned uint16 to signed int16."""
    return struct.unpack('>h', struct.pack('>H', value))[0]


def to_uint32(high, low):
    """Convert two uint16 registers to uint32 (big-endian)."""
    return (high << 16) | low


def main():
    results = {}  # test_name -> (pass_bool, detail_string)

    print("=" * 60)
    print("SolarEdge SE30K Live Register Validation")
    print(f"Target: {SE_HOST}:{SE_PORT} (unit ID {SE_UNIT})")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print()

    # ── 1. Connection Test ──────────────────────────────────────
    print("── 1. Connection Test ──")
    client = ModbusTcpClient(SE_HOST, port=SE_PORT, timeout=10)
    connected = client.connect()
    if not connected:
        print(f"FAIL: Could not connect to {SE_HOST}:{SE_PORT}")
        print("The SolarEdge inverter may be offline (nighttime/maintenance).")
        results["Connection"] = (False, "Could not connect")
        print_summary(results, [], None)
        sys.exit(1)
    print(f"Connected to {SE_HOST}:{SE_PORT} — PASS")
    results["Connection"] = (True, "Connected")
    print()

    # ── 2. SunSpec Header Validation ────────────────────────────
    print("── 2. SunSpec Header Validation ──")
    try:
        result = client.read_holding_registers(40000, count=2, slave=SE_UNIT)
        if result.isError():
            print(f"FAIL: Modbus error reading registers 40000-40001: {result}")
            results["SunSpec Header"] = (False, f"Modbus error: {result}")
        else:
            header_bytes = struct.pack('>HH', *result.registers)
            header_str = header_bytes.decode('ascii', errors='replace')
            is_suns = header_bytes == b'SunS'
            status = "PASS" if is_suns else "FAIL"
            print(f"SunSpec Header: {header_bytes!r} ({header_str}) — {status}")
            results["SunSpec Header"] = (is_suns, f"{header_bytes!r}")
    except Exception as e:
        print(f"FAIL: Exception reading SunSpec header: {e}")
        results["SunSpec Header"] = (False, str(e))
    print()

    # ── 3. Common Model (Model 1) Validation ────────────────────
    print("── 3. Common Model (Model 1) Validation ──")
    try:
        result = client.read_holding_registers(40002, count=67, slave=SE_UNIT)
        if result.isError():
            print(f"FAIL: Modbus error reading Common Model: {result}")
            results["Common Model"] = (False, f"Modbus error: {result}")
        else:
            regs = result.registers
            did = regs[0]
            length = regs[1]

            # Extract string fields
            manufacturer = regs_to_string(regs[2:18])    # 16 regs = 32 bytes
            model = regs_to_string(regs[18:34])           # 16 regs = 32 bytes
            version = regs_to_string(regs[42:50])         # 8 regs = 16 bytes
            serial = regs_to_string(regs[50:66])          # 16 regs = 32 bytes
            device_addr = regs[66]                        # 1 reg

            print(f"  DID: {did} (expect 1)")
            print(f"  Length: {length} (expect 65)")
            print(f"  C_Manufacturer: \"{manufacturer}\"")
            print(f"  C_Model: \"{model}\"")
            print(f"  C_Version: \"{version}\"")
            print(f"  C_SerialNumber: \"{serial}\"")
            print(f"  C_DeviceAddress: {device_addr}")

            common_pass = (did == 1 and length == 65)
            status = "PASS" if common_pass else "FAIL"
            print(f"Common Model: DID={did}, Length={length} — {status}")
            results["Common Model"] = (common_pass, f"DID={did}, Length={length}, Mfr={manufacturer}")
    except Exception as e:
        print(f"FAIL: Exception reading Common Model: {e}")
        results["Common Model"] = (False, str(e))
    print()

    # ── 4. Inverter Model Validation ────────────────────────────
    print("── 4. Inverter Model Validation ──")
    inv_length = None
    try:
        # Read header (DID + Length)
        result = client.read_holding_registers(40069, count=2, slave=SE_UNIT)
        if result.isError():
            print(f"FAIL: Modbus error reading Inverter Model header: {result}")
            results["Inverter Model"] = (False, f"Modbus error: {result}")
        else:
            inv_did = result.registers[0]
            inv_length = result.registers[1]
            print(f"  Inverter Model: DID={inv_did}, Length={inv_length}")

            inv_valid = inv_did in (101, 102, 103)
            if not inv_valid:
                print(f"  FAIL: DID {inv_did} is not 101, 102, or 103")
                results["Inverter Model"] = (False, f"DID={inv_did}")
            else:
                status = "PASS"
                print(f"  DID check: {inv_did} (three-phase={inv_did == 103}) — {status}")

                # Read full model data
                result = client.read_holding_registers(40071, count=inv_length, slave=SE_UNIT)
                if result.isError():
                    print(f"  FAIL: Could not read inverter data: {result}")
                    results["Inverter Model"] = (False, f"Data read error: {result}")
                else:
                    regs = result.registers

                    # I_AC_Current (offset 0 from 40071) with SF (offset 4)
                    ac_current_raw = regs[0]
                    ac_current_sf = to_int16(regs[4])
                    ac_current = ac_current_raw * (10 ** ac_current_sf)
                    print(f"  AC Current: {ac_current_raw} * 10^{ac_current_sf} = {ac_current} A")

                    # I_AC_Power (offset 12 from 40071 = 40083) with SF (offset 13 = 40084)
                    ac_power_raw = to_int16(regs[12])
                    ac_power_sf = to_int16(regs[13])
                    ac_power = ac_power_raw * (10 ** ac_power_sf)
                    print(f"  AC Power: {ac_power_raw} * 10^{ac_power_sf} = {ac_power} W")

                    # I_AC_Frequency (offset 14 = 40085) with SF (offset 15 = 40086)
                    ac_freq_raw = regs[14]
                    ac_freq_sf = to_int16(regs[15])
                    ac_freq = ac_freq_raw * (10 ** ac_freq_sf)
                    print(f"  Frequency: {ac_freq_raw} * 10^{ac_freq_sf} = {ac_freq} Hz")

                    # I_AC_Energy_WH (offset 22-23 = 40093-40094, acc32) with SF (offset 24 = 40095)
                    energy_raw = to_uint32(regs[22], regs[23])
                    energy_sf = to_int16(regs[24])
                    energy = energy_raw * (10 ** energy_sf)
                    print(f"  Lifetime Energy: {energy_raw} * 10^{energy_sf} = {energy} Wh")

                    # I_DC_Voltage (offset 27 = 40098) with SF (offset 28 = 40099)
                    dc_voltage_raw = regs[27]
                    dc_voltage_sf = to_int16(regs[28])
                    dc_voltage = dc_voltage_raw * (10 ** dc_voltage_sf)
                    print(f"  DC Voltage: {dc_voltage_raw} * 10^{dc_voltage_sf} = {dc_voltage} V")

                    # I_DC_Power (offset 29 = 40100) with SF (offset 30 = 40101)
                    dc_power_raw = to_int16(regs[29])
                    dc_power_sf = to_int16(regs[30])
                    dc_power = dc_power_raw * (10 ** dc_power_sf)
                    print(f"  DC Power: {dc_power_raw} * 10^{dc_power_sf} = {dc_power} W")

                    # I_Status (offset 36 = 40107)
                    i_status = regs[36]
                    status_name = STATUS_NAMES.get(i_status, "UNKNOWN")
                    print(f"  Status: {i_status} ({status_name})")

                    # I_Status_Vendor (offset 37 = 40108)
                    vendor_status = regs[37]
                    print(f"  Vendor Status: {vendor_status}")

                    results["Inverter Model"] = (True, f"DID={inv_did}, Len={inv_length}, Power={ac_power}W, Status={status_name}")
    except Exception as e:
        print(f"FAIL: Exception reading Inverter Model: {e}")
        results["Inverter Model"] = (False, str(e))
    print()

    # ── 5. Model Chain Walk ─────────────────────────────────────
    print("── 5. Model Chain Walk ──")
    model_dids = []
    try:
        if inv_length is None:
            print("  SKIP: Inverter model length unknown, cannot walk chain")
            results["Model Chain"] = (False, "Inverter length unknown")
        else:
            # Start after inverter model: 40069 (header start) + 2 (header) + inv_length (data)
            addr = 40069 + 2 + inv_length
            chain_pass = True

            while True:
                result = client.read_holding_registers(addr, count=2, slave=SE_UNIT)
                if result.isError():
                    print(f"  Error reading model at {addr}: {result}")
                    chain_pass = False
                    break

                m_did = result.registers[0]
                m_len = result.registers[1]
                print(f"  Model at {addr}: DID={m_did}, Length={m_len}")

                if m_did == 0xFFFF:
                    print("  End of model chain")
                    break

                model_dids.append(m_did)
                addr += 2 + m_len

                # Safety: don't walk more than 20 models
                if len(model_dids) > 20:
                    print("  WARNING: More than 20 models found, stopping walk")
                    break

            chain_str = " -> ".join(str(d) for d in model_dids)
            if model_dids:
                print(f"  Model chain (after inverter): {chain_str} -> END")
            else:
                print("  Model chain (after inverter): END (no additional models)")
            results["Model Chain"] = (chain_pass, chain_str if model_dids else "empty")
    except Exception as e:
        print(f"FAIL: Exception walking model chain: {e}")
        results["Model Chain"] = (False, str(e))
    print()

    # Close connection
    client.close()

    # ── 6. Summary ──────────────────────────────────────────────
    print_summary(results, model_dids, inv_length)

    # Exit code
    critical_tests = ["Connection", "SunSpec Header", "Common Model", "Inverter Model"]
    all_pass = all(results.get(t, (False,))[0] for t in critical_tests)
    sys.exit(0 if all_pass else 1)


def print_summary(results, model_dids, inv_length):
    """Print summary table with PASS/FAIL results and model analysis."""
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    print(f"{'Test':<25} {'Result':<8} {'Detail'}")
    print("-" * 60)
    for name, (passed, detail) in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{name:<25} {status:<8} {detail}")
    print()

    # Model 120 analysis
    has_120 = 120 in model_dids
    if has_120:
        print("Model 120 (Nameplate): PRESENT in SE30K model chain")
    else:
        print("Model 120 (Nameplate): NOT FOUND — Proxy must SYNTHESIZE Model 120")

    # Model 123 analysis
    has_123 = 123 in model_dids
    if has_123:
        print("Model 123 (Controls): PRESENT in SE30K model chain")
    else:
        print("Model 123 (Controls): NOT FOUND — Proxy must SYNTHESIZE Model 123 and translate writes to 0xF300/0xF322")

    # Model chain end address
    if inv_length is not None:
        chain_end = 40069 + 2 + inv_length
        for did in model_dids:
            # We don't have lengths here, but the walk printed them
            pass
        print(f"\nInverter model ends at register {40069 + 2 + inv_length - 1} (address {40069 + 2 + inv_length} is next)")

    print()


if __name__ == "__main__":
    main()
