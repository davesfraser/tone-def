"""
Tests for tonedef.component_mapper

LLM calls (map_components) are not tested here — they require a live API key.
All pure functions are covered with synthetic in-memory data.
"""

from __future__ import annotations

import pytest

from tonedef.component_mapper import (
    _build_component_candidates_context,
    _build_component_schema_context,
    _build_hardware_mapping_context,
    _build_retrieved_candidates_context,
    _extract_tonal_description,
    build_hardware_index,
    extract_hardware_names,
    fill_defaults,
    lookup_hardware,
)

# ---------------------------------------------------------------------------
# build_hardware_index
# ---------------------------------------------------------------------------

_MAPPING = [
    {
        "hardware_name": "Fender Tweed Deluxe",
        "component_name": "Tweed Delight",
        "component_id": 79000,
        "confidence": "high",
    },
    {
        "hardware_name": "Dallas Arbiter Fuzz Face",
        "component_name": "Fuzz Face",
        "component_id": 10000,
        "confidence": "high",
    },
    {
        "hardware_name": "Fender Tweed Deluxe",
        "component_name": "Tweed Amp Alt",
        "component_id": 79001,
        "confidence": "medium",
    },
]


def test_build_hardware_index_keys_are_lowercase() -> None:
    index = build_hardware_index(_MAPPING)
    assert all(k == k.lower() for k in index)


def test_build_hardware_index_groups_multiple_rows() -> None:
    index = build_hardware_index(_MAPPING)
    assert len(index["fender tweed deluxe"]) == 2


def test_build_hardware_index_single_row() -> None:
    index = build_hardware_index(_MAPPING)
    assert len(index["dallas arbiter fuzz face"]) == 1


def test_build_hardware_index_empty_mapping() -> None:
    assert build_hardware_index([]) == {}


# ---------------------------------------------------------------------------
# lookup_hardware
# ---------------------------------------------------------------------------


def test_lookup_hardware_exact_match() -> None:
    index = build_hardware_index(_MAPPING)
    result = lookup_hardware("Fender Tweed Deluxe", index)
    assert len(result) == 2


def test_lookup_hardware_case_insensitive() -> None:
    index = build_hardware_index(_MAPPING)
    result = lookup_hardware("FENDER TWEED DELUXE", index)
    assert len(result) == 2


def test_lookup_hardware_fuzzy_match() -> None:
    index = build_hardware_index(_MAPPING)
    # Close enough to trigger fuzzy match
    result = lookup_hardware("Fender Tweed Dlx", index)
    assert len(result) > 0


def test_lookup_hardware_no_match_returns_empty() -> None:
    index = build_hardware_index(_MAPPING)
    result = lookup_hardware("Completely Unrelated XYZ Widget", index)
    assert result == []


# ---------------------------------------------------------------------------
# extract_hardware_names
# ---------------------------------------------------------------------------

_SIGNAL_CHAIN_WITH_HARDWARE = """\
The rig consists of:

[ Fender Tweed Deluxe — amplifier ] [DOCUMENTED]
[ Dallas Arbiter Fuzz Face — overdrive/fuzz ] [INFERRED]
[ Grampian Type 636 — spring reverb ] [ESTIMATED]
"""

_SIGNAL_CHAIN_EMPTY = "No recognisable hardware described."


def test_extract_hardware_names_returns_list() -> None:
    result = extract_hardware_names(_SIGNAL_CHAIN_WITH_HARDWARE)
    assert isinstance(result, list)


def test_extract_hardware_names_finds_three_names() -> None:
    result = extract_hardware_names(_SIGNAL_CHAIN_WITH_HARDWARE)
    assert len(result) == 3


def test_extract_hardware_names_correct_names() -> None:
    result = extract_hardware_names(_SIGNAL_CHAIN_WITH_HARDWARE)
    assert "Fender Tweed Deluxe" in result
    assert "Dallas Arbiter Fuzz Face" in result
    assert "Grampian Type 636" in result


def test_extract_hardware_names_excludes_provenance_labels() -> None:
    result = extract_hardware_names(_SIGNAL_CHAIN_WITH_HARDWARE)
    for name in result:
        assert name.upper() not in ("DOCUMENTED", "INFERRED", "ESTIMATED")


def test_extract_hardware_names_empty_string() -> None:
    result = extract_hardware_names("")
    assert result == []


def test_extract_hardware_names_no_hardware_pattern() -> None:
    result = extract_hardware_names(_SIGNAL_CHAIN_EMPTY)
    assert result == []


# ---------------------------------------------------------------------------
# _build_hardware_mapping_context
# ---------------------------------------------------------------------------


def test_build_hardware_mapping_context_formats_rows() -> None:
    rows = [
        {
            "hardware_name": "Fuzz Face",
            "component_name": "Fuzz Unit",
            "component_id": 1,
            "confidence": "high",
        }
    ]
    result = _build_hardware_mapping_context(rows)
    assert "Fuzz Face" in result
    assert "Fuzz Unit" in result
    assert "high" in result


def test_build_hardware_mapping_context_empty() -> None:
    result = _build_hardware_mapping_context([])
    assert "no matches" in result.lower()


# ---------------------------------------------------------------------------
# _build_component_candidates_context
# ---------------------------------------------------------------------------

_MANUAL_CHUNKS = {
    "Tweed Delight": {"text": "A warm clean amp modelled after a vintage Tweed Deluxe."},
}


def test_build_component_candidates_context_includes_description() -> None:
    result = _build_component_candidates_context(["Tweed Delight"], _MANUAL_CHUNKS)
    assert "warm clean amp" in result


def test_build_component_candidates_context_empty_names() -> None:
    result = _build_component_candidates_context([], _MANUAL_CHUNKS)
    assert "no" in result.lower()


def test_build_component_candidates_context_missing_chunk() -> None:
    result = _build_component_candidates_context(["Unknown Component"], _MANUAL_CHUNKS)
    assert "no" in result.lower()


def test_build_component_candidates_context_truncates_long_text() -> None:
    long_chunks = {"Amp": {"text": "A" * 600}}
    result = _build_component_candidates_context(["Amp"], long_chunks)
    assert "..." in result


# ---------------------------------------------------------------------------
# _build_retrieved_candidates_context
# ---------------------------------------------------------------------------

_RETRIEVED = [
    {"component_name": "Spring Reverb", "category": "Reverb", "text": "A lush spring reverb unit."},
]


def test_build_retrieved_candidates_context_includes_name() -> None:
    result = _build_retrieved_candidates_context(_RETRIEVED)
    assert "Spring Reverb" in result


def test_build_retrieved_candidates_context_includes_category() -> None:
    result = _build_retrieved_candidates_context(_RETRIEVED)
    assert "Reverb" in result


def test_build_retrieved_candidates_context_empty() -> None:
    result = _build_retrieved_candidates_context([])
    assert "no candidates" in result.lower()


# ---------------------------------------------------------------------------
# _build_component_schema_context
# ---------------------------------------------------------------------------

_SCHEMA = {
    "Tweed Delight": {
        "component_id": 79000,
        "parameters": [
            {"param_id": "vb", "param_name": "Bright", "default_value": 0.5},
        ],
    }
}


def test_build_component_schema_context_includes_component() -> None:
    result = _build_component_schema_context(["Tweed Delight"], _SCHEMA)
    assert "Tweed Delight" in result
    assert "79000" in result


def test_build_component_schema_context_includes_param() -> None:
    result = _build_component_schema_context(["Tweed Delight"], _SCHEMA)
    assert "vb" in result
    assert "Bright" in result


def test_build_component_schema_context_empty_names() -> None:
    result = _build_component_schema_context([], _SCHEMA)
    assert "no schema" in result.lower()


def test_build_component_schema_context_missing_name() -> None:
    result = _build_component_schema_context(["Unknown"], _SCHEMA)
    assert "no schema" in result.lower()


# ---------------------------------------------------------------------------
# _extract_tonal_description
# ---------------------------------------------------------------------------


def test_extract_tonal_description_after_closing_tag() -> None:
    text = "some stuff</signal_chain>\n\nWarm and bluesy."
    result = _extract_tonal_description(text)
    assert result == "Warm and bluesy."


def test_extract_tonal_description_no_tag_returns_full() -> None:
    text = "A warm clean tone with reverb."
    result = _extract_tonal_description(text)
    assert result == text.strip()


def test_extract_tonal_description_strips_whitespace() -> None:
    text = "stuff</signal_chain>   \n  Bright and clean.   "
    result = _extract_tonal_description(text)
    assert result == "Bright and clean."


# ---------------------------------------------------------------------------
# fill_defaults
# ---------------------------------------------------------------------------

_FILL_SCHEMA = {
    "Tweed Delight": {
        "parameters": [
            {"param_id": "vb", "param_name": "Bright", "default_value": 0.5},
            {"param_id": "vo", "param_name": "Volume", "default_value": 0.7},
        ]
    }
}


def test_fill_defaults_adds_missing_param() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": 0.8}}
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert "vo" in result[0]["parameters"]
    assert result[0]["parameters"]["vo"] == pytest.approx(0.7)


def test_fill_defaults_does_not_overwrite_existing() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": 0.9}}
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"]["vb"] == pytest.approx(0.9)


def test_fill_defaults_clamps_above_one() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": 1.5}}
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"]["vb"] == pytest.approx(1.0)


def test_fill_defaults_clamps_below_zero() -> None:
    components = [
        {"component_name": "Tweed Delight", "component_id": 79000, "parameters": {"vb": -0.2}}
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"]["vb"] == pytest.approx(0.0)


def test_fill_defaults_unknown_component_untouched() -> None:
    components = [{"component_name": "Unknown", "component_id": 0, "parameters": {"xx": 0.5}}]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"] == {"xx": 0.5}


def test_fill_defaults_returns_list() -> None:
    result = fill_defaults([], _FILL_SCHEMA)
    assert result == []
