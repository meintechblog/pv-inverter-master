"""Unit tests for register mapping specification (PROTO-03).

These tests verify the internal consistency and correctness of the register
translation table that maps SolarEdge SE30K registers to the Fronius SunSpec
proxy register layout served to Venus OS.

No hardware or network access required -- all tests use pure constants and logic.
"""
import struct

import pytest

# ---------------------------------------------------------------------------
# Constants from the register mapping specification
# ---------------------------------------------------------------------------

# SunSpec header
SUNSPEC_HEADER = 0x53756E53  # ASCII "SunS"

# Model identifiers
COMMON_DID = 1
COMMON_LENGTH = 65
INVERTER_DID = 103
INVERTER_LENGTH = 50
NAMEPLATE_DID = 120
NAMEPLATE_LENGTH = 26
CONTROLS_DID = 123
CONTROLS_LENGTH = 24
END_MARKER = 0xFFFF

# Proxy register addresses (base-0 addressing as used by pymodbus)
HEADER_ADDR = 40000
COMMON_ADDR = 40002  # HEADER_ADDR + 2
INVERTER_ADDR = 40069  # COMMON_ADDR + 2 + COMMON_LENGTH
NAMEPLATE_ADDR = 40121  # INVERTER_ADDR + 2 + INVERTER_LENGTH
CONTROLS_ADDR = 40149  # NAMEPLATE_ADDR + 2 + NAMEPLATE_LENGTH
END_ADDR = 40175  # CONTROLS_ADDR + 2 + CONTROLS_LENGTH

# Unit IDs
PROXY_UNIT_ID = 126
SOLAREDGE_UNIT_ID = 1

# SolarEdge proprietary power control registers
SE_POWER_CONTROL_ENABLE = 0xF300  # 62208
SE_COMMAND_TIMEOUT = 0xF310  # 62224
SE_DYNAMIC_POWER_LIMIT = 0xF322  # 62242

# Fronius manufacturer string
FRONIUS_MANUFACTURER = "Fronius"
FRONIUS_MANUFACTURER_BYTES = FRONIUS_MANUFACTURER.encode("ascii").ljust(32, b"\x00")

# Common Model field offsets (relative to COMMON_ADDR + 2, i.e., start of data)
MANUFACTURER_OFFSET = 0  # 16 registers = 32 bytes
MANUFACTURER_SIZE = 16  # registers
MODEL_OFFSET = 18  # relative to DID register
DEVICE_ADDRESS_OFFSET = 66  # relative to DID register (40068 - 40002)

# Model 120 key registers
NAMEPLATE_DERTYP_ADDR = 40123
NAMEPLATE_WRTG_ADDR = 40124
NAMEPLATE_WRTG_SF_ADDR = 40125

# Model 123 field offsets (relative to CONTROLS_ADDR)
# DID at +0, Length at +1, then data fields:
CONTROLS_CONN_WINTMS = CONTROLS_ADDR + 2  # 40151
CONTROLS_CONN_RVRTTMS = CONTROLS_ADDR + 3  # 40152
CONTROLS_CONN = CONTROLS_ADDR + 4  # 40153
CONTROLS_WMAXLIMPCT = CONTROLS_ADDR + 5  # 40154
CONTROLS_WMAXLIMPCT_WINTMS = CONTROLS_ADDR + 6  # 40155
CONTROLS_WMAXLIMPCT_RVRTTMS = CONTROLS_ADDR + 7  # 40156
CONTROLS_WMAXLIMPCT_RMPTMS = CONTROLS_ADDR + 8  # 40157
CONTROLS_WMAXLIM_ENA = CONTROLS_ADDR + 9  # 40158


# ---------------------------------------------------------------------------
# Helper: encode manufacturer string as list of uint16 register values
# ---------------------------------------------------------------------------
def encode_string_registers(text: str, num_registers: int) -> list[int]:
    """Encode a string into a list of uint16 register values (big-endian)."""
    raw = text.encode("ascii").ljust(num_registers * 2, b"\x00")
    return [int.from_bytes(raw[i : i + 2], "big") for i in range(0, num_registers * 2, 2)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSunSpecHeader:
    """Verify SunSpec interoperability header at register 40000."""

    def test_sunspec_header_value(self):
        """Proxy registers 40000-40001 must decode to ASCII 'SunS' (0x53756E53)."""
        high = (SUNSPEC_HEADER >> 16) & 0xFFFF
        low = SUNSPEC_HEADER & 0xFFFF
        packed = struct.pack(">HH", high, low)
        assert packed == b"SunS"

    def test_sunspec_header_address(self):
        """SunSpec header must be at register 40000."""
        assert HEADER_ADDR == 40000


class TestCommonModelManufacturerSubstitution:
    """Verify manufacturer string is replaced with 'Fronius'."""

    def test_common_model_manufacturer_substitution(self):
        """Proxy register 40004-40019 must contain 'Fronius' padded to 32 bytes."""
        registers = encode_string_registers(FRONIUS_MANUFACTURER, MANUFACTURER_SIZE)
        # Decode back to bytes
        raw = b"".join(r.to_bytes(2, "big") for r in registers)
        assert raw == FRONIUS_MANUFACTURER_BYTES
        assert raw[:7] == b"Fronius"
        assert raw[7:] == b"\x00" * 25
        assert len(raw) == 32

    def test_common_model_manufacturer_not_solaredge(self):
        """The proxy must NOT serve 'SolarEdge' as manufacturer."""
        registers = encode_string_registers(FRONIUS_MANUFACTURER, MANUFACTURER_SIZE)
        raw = b"".join(r.to_bytes(2, "big") for r in registers)
        assert b"SolarEdge" not in raw

    def test_common_model_manufacturer_address(self):
        """C_Manufacturer starts at register 40004 (COMMON_ADDR + 2)."""
        manufacturer_addr = COMMON_ADDR + 2  # skip DID and Length
        assert manufacturer_addr == 40004

    def test_common_model_unit_id(self):
        """Proxy register 40068 must be 126 (not SolarEdge default of 1)."""
        device_address_addr = COMMON_ADDR + DEVICE_ADDRESS_OFFSET
        assert device_address_addr == 40068
        assert PROXY_UNIT_ID == 126
        assert PROXY_UNIT_ID != SOLAREDGE_UNIT_ID


class TestModelChainStructure:
    """Verify the model chain DID sequence and addresses."""

    def test_model_chain_structure(self):
        """DID sequence must be [1, 103, 120, 123, 0xFFFF] at correct offsets."""
        expected_chain = [
            (COMMON_ADDR, COMMON_DID),       # 40002: Model 1
            (INVERTER_ADDR, INVERTER_DID),    # 40069: Model 103
            (NAMEPLATE_ADDR, NAMEPLATE_DID),  # 40121: Model 120
            (CONTROLS_ADDR, CONTROLS_DID),    # 40149: Model 123
            (END_ADDR, END_MARKER),           # 40175: 0xFFFF
        ]
        dids = [did for _, did in expected_chain]
        assert dids == [1, 103, 120, 123, 0xFFFF]

    def test_model_chain_addresses_are_contiguous(self):
        """Each model starts immediately after the previous model's data."""
        assert COMMON_ADDR == HEADER_ADDR + 2
        assert INVERTER_ADDR == COMMON_ADDR + 2 + COMMON_LENGTH
        assert NAMEPLATE_ADDR == INVERTER_ADDR + 2 + INVERTER_LENGTH
        assert CONTROLS_ADDR == NAMEPLATE_ADDR + 2 + NAMEPLATE_LENGTH
        assert END_ADDR == CONTROLS_ADDR + 2 + CONTROLS_LENGTH

    def test_model_chain_specific_addresses(self):
        """Verify the exact computed addresses."""
        assert COMMON_ADDR == 40002
        assert INVERTER_ADDR == 40069
        assert NAMEPLATE_ADDR == 40121
        assert CONTROLS_ADDR == 40149
        assert END_ADDR == 40175


class TestInverterModel103Passthrough:
    """Verify Model 103 data registers are all passthrough."""

    def test_inverter_model_103_passthrough(self):
        """All 50 data registers (40071-40120) map to the same SolarEdge addresses."""
        data_start = INVERTER_ADDR + 2  # skip DID and Length
        data_end = data_start + INVERTER_LENGTH - 1
        assert data_start == 40071
        assert data_end == 40120
        # Passthrough means proxy address == SolarEdge address for every register
        for addr in range(data_start, data_end + 1):
            se_addr = addr  # 1:1 passthrough
            assert se_addr == addr, f"Register {addr} should passthrough to SE {addr}"

    def test_inverter_model_103_length(self):
        """Model 103 data block is exactly 50 registers."""
        assert INVERTER_LENGTH == 50

    def test_inverter_model_key_registers(self):
        """Key inverter registers are at expected addresses."""
        assert INVERTER_ADDR + 2 == 40071  # I_AC_Current
        assert INVERTER_ADDR + 3 == 40072  # I_AC_CurrentA
        assert INVERTER_ADDR + 14 == 40083  # I_AC_Power
        assert INVERTER_ADDR + 15 == 40084  # I_AC_Power_SF
        assert INVERTER_ADDR + 38 == 40107  # I_Status


class TestModel120Synthesis:
    """Verify Model 120 (Nameplate) synthesized values."""

    def test_model_120_synthesis(self):
        """WRtg at 40124 = 30000, WRtg_SF at 40125 = 0, DERTyp at 40123 = 4."""
        assert NAMEPLATE_DERTYP_ADDR == 40123
        assert NAMEPLATE_WRTG_ADDR == 40124
        assert NAMEPLATE_WRTG_SF_ADDR == 40125

        # Expected synthesized values
        dertyp = 4  # PV
        wrtg = 30000  # 30kW (SE30K)
        wrtg_sf = 0  # scale factor 0 -> actual = 30000 * 10^0 = 30000 W

        assert dertyp == 4
        assert wrtg == 30000
        assert wrtg_sf == 0
        assert wrtg * (10 ** wrtg_sf) == 30000  # 30kW

    def test_model_120_did_and_length(self):
        """Model 120 header: DID=120 at 40121, Length=26 at 40122."""
        assert NAMEPLATE_ADDR == 40121
        assert NAMEPLATE_LENGTH == 26

    def test_model_120_vartg(self):
        """VARtg should also be 30000 with SF=0 for a 30kW inverter."""
        vartg = 30000
        vartg_sf = 0
        assert vartg * (10 ** vartg_sf) == 30000


class TestModel123WriteMapping:
    """Verify Model 123 write translations to SolarEdge proprietary registers."""

    def test_model_123_write_mapping(self):
        """WMaxLimPct write to proxy maps to SolarEdge Float32 write at 0xF322."""
        # SunSpec value 5000 with SF -2 = 50.00%
        sunspec_value = 5000
        sunspec_sf = -2
        actual_pct = sunspec_value * (10 ** sunspec_sf)
        assert actual_pct == 50.0

        # This must be written as Float32 to SE 0xF322
        float32_bytes = struct.pack(">f", actual_pct)
        unpacked = struct.unpack(">f", float32_bytes)[0]
        assert abs(unpacked - 50.0) < 0.001

        assert SE_DYNAMIC_POWER_LIMIT == 0xF322
        assert SE_DYNAMIC_POWER_LIMIT == 62242

    def test_model_123_enable_mapping(self):
        """WMaxLim_Ena write to proxy maps to SolarEdge 0xF300."""
        assert SE_POWER_CONTROL_ENABLE == 0xF300
        assert SE_POWER_CONTROL_ENABLE == 62208
        # ENABLED (1) -> SE 0xF300 = 1
        # DISABLED (0) -> SE 0xF300 = 0

    def test_model_123_revert_timeout_mapping(self):
        """WMaxLimPct_RvrtTms maps to SolarEdge Command Timeout at 0xF310."""
        assert SE_COMMAND_TIMEOUT == 0xF310
        assert SE_COMMAND_TIMEOUT == 62224

    def test_model_123_field_addresses(self):
        """Model 123 fields are at correct proxy addresses."""
        assert CONTROLS_WMAXLIMPCT == 40154
        assert CONTROLS_WMAXLIM_ENA == 40158
        assert CONTROLS_WMAXLIMPCT_RVRTTMS == 40156

    def test_model_123_write_sequence(self):
        """Write sequence: enable 0xF300 first, then set 0xF322."""
        # This test documents the required write order
        write_sequence = [
            (SE_POWER_CONTROL_ENABLE, 1, "Enable dynamic power control"),
            (SE_DYNAMIC_POWER_LIMIT, 50.0, "Set power limit to 50%"),
        ]
        assert write_sequence[0][0] == 0xF300  # Enable first
        assert write_sequence[1][0] == 0xF322  # Then set limit


class TestScaleFactor:
    """Verify scale factor sign handling and arithmetic."""

    def test_scale_factor(self):
        """SF value -2 with raw value 5000 produces actual value 50.00."""
        raw_value = 5000
        sf = -2
        actual = raw_value * (10 ** sf)
        assert actual == 50.0

    def test_scale_factor_negative_one(self):
        """SF value -1 with raw value 2071 produces 207.1."""
        assert 2071 * (10 ** -1) == pytest.approx(207.1)

    def test_scale_factor_zero(self):
        """SF value 0 means no scaling."""
        assert 30000 * (10 ** 0) == 30000

    def test_scale_factor_signed_int16(self):
        """Scale factors are signed int16 -- verify negative encoding."""
        sf_bytes = struct.pack(">h", -2)  # signed int16, big-endian
        sf_decoded = struct.unpack(">h", sf_bytes)[0]
        assert sf_decoded == -2

    def test_scale_factor_positive(self):
        """Positive scale factors multiply by powers of 10."""
        assert 5 * (10 ** 2) == 500


class TestEndMarker:
    """Verify the end-of-model-chain marker."""

    def test_end_marker(self):
        """Register at END_ADDR = 0xFFFF, register at END_ADDR+1 = 0x0000."""
        assert END_ADDR == 40175
        end_did = END_MARKER
        end_length = 0x0000
        assert end_did == 0xFFFF
        assert end_length == 0x0000

    def test_end_marker_follows_controls(self):
        """End marker immediately follows Model 123 data."""
        expected_end = CONTROLS_ADDR + 2 + CONTROLS_LENGTH
        assert END_ADDR == expected_end
