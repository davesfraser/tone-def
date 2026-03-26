"""
Tests for tonedef.component_mapper

LLM calls (map_components) are not tested here — they require a live API key.
All pure functions are covered with synthetic in-memory data.
"""

from __future__ import annotations

import pytest

from tonedef.component_mapper import (
    _find_amp_name,
    _make_matched_cabinet_pro,
    build_cabinet_lookup_context,
    build_component_schema_context,
    build_manual_reference_context,
    fill_defaults,
)

# ---------------------------------------------------------------------------
# build_manual_reference_context
# ---------------------------------------------------------------------------

_MANUAL_RESULTS = [
    {
        "component_name": "Spring Reverb",
        "category": "Reverb",
        "text": "A lush spring reverb unit.",
    },
    {
        "component_name": "Tweed Delight",
        "category": "Amps",
        "text": "Warm clean amp.",
    },
]


def test_manual_reference_context_includes_names() -> None:
    result = build_manual_reference_context(_MANUAL_RESULTS)
    assert "Spring Reverb" in result
    assert "Tweed Delight" in result


def test_manual_reference_context_includes_category() -> None:
    result = build_manual_reference_context(_MANUAL_RESULTS)
    assert "Reverb" in result
    assert "Amps" in result


def test_manual_reference_context_deduplicates() -> None:
    dupes = [*_MANUAL_RESULTS, _MANUAL_RESULTS[0]]
    result = build_manual_reference_context(dupes)
    assert result.count("[Spring Reverb]") == 1


def test_manual_reference_context_truncates_long_text() -> None:
    long = [{"component_name": "Amp", "category": "Amps", "text": "A" * 800}]
    result = build_manual_reference_context(long)
    assert "..." in result


def test_manual_reference_context_empty() -> None:
    result = build_manual_reference_context([])
    assert "no manual" in result.lower()


# ---------------------------------------------------------------------------
# build_component_schema_context
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
    result = build_component_schema_context(["Tweed Delight"], _SCHEMA)
    assert "Tweed Delight" in result
    assert "79000" in result


def test_build_component_schema_context_includes_param() -> None:
    result = build_component_schema_context(["Tweed Delight"], _SCHEMA)
    assert "vb" in result
    assert "Bright" in result


def test_build_component_schema_context_empty_names() -> None:
    result = build_component_schema_context([], _SCHEMA)
    assert "no schema" in result.lower()


def test_build_component_schema_context_missing_name() -> None:
    result = build_component_schema_context(["Unknown"], _SCHEMA)
    assert "no schema" in result.lower()


# ---------------------------------------------------------------------------
# build_cabinet_lookup_context
# ---------------------------------------------------------------------------

_AMP_CABINET_LOOKUP = {
    "Lead 800": {
        "cabinet_component_name": "Matched Cabinet Pro",
        "cabinet_component_id": 156000,
        "cab_value": 10,
        "evidence_count": 5,
        "evidence_total": 5,
    },
    "AC Box XV": {
        "cabinet_component_name": "Matched Cabinet Pro",
        "cabinet_component_id": 156000,
        "cab_value": 0,
        "evidence_count": 3,
        "evidence_total": 3,
    },
}


def test_cabinet_lookup_context_includes_amp() -> None:
    result = build_cabinet_lookup_context(_AMP_CABINET_LOOKUP)
    assert "Lead 800" in result
    assert "AC Box XV" in result


def test_cabinet_lookup_context_includes_cab_id() -> None:
    result = build_cabinet_lookup_context(_AMP_CABINET_LOOKUP)
    assert "156000" in result


def test_cabinet_lookup_context_includes_cab_value() -> None:
    result = build_cabinet_lookup_context(_AMP_CABINET_LOOKUP)
    # Lead 800 has cab_value=10
    assert "| 10" in result


def test_cabinet_lookup_context_empty() -> None:
    result = build_cabinet_lookup_context({})
    assert "no cabinet" in result.lower()


# ---------------------------------------------------------------------------
# _find_amp_name
# ---------------------------------------------------------------------------


def test_find_amp_name_case_insensitive() -> None:
    components = [{"component_name": "lead 800"}]
    result = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    assert result == "Lead 800"


def test_find_amp_name_exact_case() -> None:
    components = [{"component_name": "AC Box XV"}]
    result = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    assert result == "AC Box XV"


def test_find_amp_name_no_match() -> None:
    components = [{"component_name": "Cat Distortion"}]
    result = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    assert result is None


def test_find_amp_name_empty_components() -> None:
    result = _find_amp_name([], _AMP_CABINET_LOOKUP)
    assert result is None


# ---------------------------------------------------------------------------
# _make_matched_cabinet_pro
# ---------------------------------------------------------------------------

_SCHEMA_WITH_CABINET = {
    "Matched Cabinet Pro": {
        "component_id": 156000,
        "parameters": [
            {"param_id": "Vol", "param_name": "Volume", "default_value": 0.7},
            {"param_id": "Cab", "param_name": "Cabinet", "default_value": 0},
        ],
    }
}


def test_make_matched_cabinet_pro_component_id() -> None:
    result = _make_matched_cabinet_pro(
        "Lead 800", _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, "preset"
    )
    assert result["component_id"] == 156000


def test_make_matched_cabinet_pro_name() -> None:
    result = _make_matched_cabinet_pro(
        "Lead 800", _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, "preset"
    )
    assert result["component_name"] == "Matched Cabinet Pro"


def test_make_matched_cabinet_pro_sets_cab_from_lookup() -> None:
    result = _make_matched_cabinet_pro(
        "Lead 800", _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, "preset"
    )
    assert result["parameters"]["Cab"] == 10


def test_make_matched_cabinet_pro_defaults_when_no_amp() -> None:
    result = _make_matched_cabinet_pro(None, _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, "preset")
    assert result["parameters"]["Vol"] == 0.7
    assert result["parameters"]["Cab"] == 0


def test_make_matched_cabinet_pro_empty_schema() -> None:
    result = _make_matched_cabinet_pro(None, _AMP_CABINET_LOOKUP, {}, "preset")
    assert result["component_id"] == 156000
    assert result["parameters"] == {}


def test_make_matched_cabinet_pro_base_exemplar() -> None:
    result = _make_matched_cabinet_pro(
        "Lead 800", _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, "my preset"
    )
    assert result["base_exemplar"] == "my preset"


# ---------------------------------------------------------------------------
# fill_defaults
# ---------------------------------------------------------------------------

_FILL_SCHEMA = {
    "Tweed Delight": {
        "parameters": [
            {
                "param_id": "vb",
                "param_name": "Bright",
                "default_value": 0.5,
                "stats": {"min": 0.0, "max": 1.0},
            },
            {
                "param_id": "vo",
                "param_name": "Volume",
                "default_value": 0.7,
                "stats": {"min": 0.0, "max": 1.0},
            },
        ]
    },
    "Matched Cabinet Pro": {
        "parameters": [
            {
                "param_id": "Vol",
                "param_name": "Volume",
                "default_value": 0.7,
                "stats": {"min": 0.0, "max": 1.0},
            },
            {
                "param_id": "Cab",
                "param_name": "Cabinet",
                "default_value": 18.0,
                "stats": {"min": 0.0, "max": 25.0},
            },
        ]
    },
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


def test_fill_defaults_cab_param_not_clamped() -> None:
    """Cab is an integer enum (0-25+), not a normalised float — must not be clamped to [0, 1]."""
    components = [
        {
            "component_name": "Matched Cabinet Pro",
            "component_id": 156000,
            "parameters": {"Cab": 10},
        }
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"]["Cab"] == 10


def test_fill_defaults_cab_param_cast_to_int() -> None:
    """Cab values from the LLM may arrive as floats — ensure they're cast to int."""
    components = [
        {
            "component_name": "Matched Cabinet Pro",
            "component_id": 156000,
            "parameters": {"Cab": 10.0},
        }
    ]
    result = fill_defaults(components, _FILL_SCHEMA)
    assert result[0]["parameters"]["Cab"] == 10
    assert isinstance(result[0]["parameters"]["Cab"], int)
