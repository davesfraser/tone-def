"""Tests for tonedef.crp_lookup."""

from __future__ import annotations

from tonedef.crp_lookup import format_crp_reference, load_crp_enums


def test_load_crp_enums_has_three_sections() -> None:
    enums = load_crp_enums()
    assert "cabinets" in enums
    assert "microphones" in enums
    assert "mic_positions" in enums


def test_load_crp_enums_cabinet_count() -> None:
    enums = load_crp_enums()
    assert len(enums["cabinets"]) == 29  # 0-28


def test_load_crp_enums_mic_count() -> None:
    enums = load_crp_enums()
    assert len(enums["microphones"]) == 5  # 0-4


def test_load_crp_enums_mpos_count() -> None:
    enums = load_crp_enums()
    assert len(enums["mic_positions"]) == 3  # 0-2


def test_load_crp_enums_contiguous_keys() -> None:
    enums = load_crp_enums()
    for label, data in enums.items():
        expected = {str(i) for i in range(len(data))}
        assert set(data.keys()) == expected, f"{label}: non-contiguous keys"


def test_load_crp_enums_entries_have_name_and_description() -> None:
    enums = load_crp_enums()
    for section_name, data in enums.items():
        for key, entry in data.items():
            assert "name" in entry, f"{section_name}[{key}] missing 'name'"
            assert "description" in entry, f"{section_name}[{key}] missing 'description'"


def test_format_crp_reference_includes_all_sections() -> None:
    result = format_crp_reference()
    assert "CABINETS" in result
    assert "MICROPHONES" in result
    assert "MIC POSITIONS" in result


def test_format_crp_reference_includes_specific_entries() -> None:
    result = format_crp_reference()
    assert "DI Box" in result
    assert "2x12 AC Blue" in result
    assert "Dyn 57" in result
    assert "Cap Edge" in result


def test_format_crp_reference_uses_integer_keys() -> None:
    result = format_crp_reference()
    assert " 0 = DI Box" in result
    assert "28 = 4x12 Rammfire" in result
