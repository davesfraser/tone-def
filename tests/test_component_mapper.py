"""
Tests for tonedef.component_mapper

LLM calls (map_components) are not tested here — they require a live API key.
All pure functions are covered with synthetic in-memory data.
"""

from __future__ import annotations

import pytest

from tonedef.component_mapper import (
    _extract_exemplar_cabinet_params,
    _find_amp_index,
    _find_amp_name,
    _make_matched_cabinet_pro,
    _validate_crp_params,
    build_cabinet_lookup_context,
    build_component_schema_context,
    build_crp_reference_context,
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
    result = build_manual_reference_context(exemplar_chunks=_MANUAL_RESULTS)
    assert "Spring Reverb" in result
    assert "Tweed Delight" in result


def test_manual_reference_context_includes_category() -> None:
    result = build_manual_reference_context(exemplar_chunks=_MANUAL_RESULTS)
    assert "Reverb" in result
    assert "Amps" in result


def test_manual_reference_context_deduplicates() -> None:
    dupes = [*_MANUAL_RESULTS, _MANUAL_RESULTS[0]]
    result = build_manual_reference_context(exemplar_chunks=dupes)
    assert result.count("[Spring Reverb]") == 1


def test_manual_reference_context_truncates_long_text() -> None:
    long = [{"component_name": "Amp", "category": "Amps", "text": "A" * 800}]
    result = build_manual_reference_context(exemplar_chunks=long)
    assert "..." in result


def test_manual_reference_context_empty() -> None:
    result = build_manual_reference_context(exemplar_chunks=[])
    assert "no manual" in result.lower()


def test_manual_reference_context_three_sections() -> None:
    tonal = [{"component_name": "Lead 800", "category": "Amps", "text": "Marshall tone."}]
    gap = [{"component_name": "Tube Comp", "category": "Dynamics", "text": "Compressor."}]
    result = build_manual_reference_context(
        exemplar_chunks=_MANUAL_RESULTS,
        tonal_chunks=tonal,
        gap_chunks=gap,
    )
    assert "COMPONENTS FROM EXEMPLARS" in result
    assert "TONALLY RELEVANT ALTERNATIVES" in result
    assert "GAP-FILLING CANDIDATES" in result
    assert "Lead 800" in result
    assert "Tube Comp" in result


def test_manual_reference_context_omits_empty_sections() -> None:
    result = build_manual_reference_context(
        exemplar_chunks=_MANUAL_RESULTS,
        tonal_chunks=[],
        gap_chunks=None,
    )
    assert "COMPONENTS FROM EXEMPLARS" in result
    assert "TONALLY RELEVANT" not in result
    assert "GAP-FILLING" not in result


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


def test_make_matched_cabinet_pro_carries_forward_exemplar_params() -> None:
    """Non-Cab params from the LLM-emitted cabinet override schema defaults."""
    exemplar_params = {"Vol": 0.45, "Cab": 99}
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=exemplar_params,
    )
    # Vol carried forward from exemplar
    assert result["parameters"]["Vol"] == pytest.approx(0.45)
    # Cab always overridden by lookup (Lead 800 → 10)
    assert result["parameters"]["Cab"] == 10


def test_make_matched_cabinet_pro_exemplar_params_no_amp() -> None:
    """Exemplar params still apply when no amp is found (Cab stays from exemplar)."""
    exemplar_params = {"Vol": 0.6, "Cab": 5}
    result = _make_matched_cabinet_pro(
        None,
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=exemplar_params,
    )
    assert result["parameters"]["Vol"] == pytest.approx(0.6)
    # No amp found, so Cab keeps exemplar value (not overridden)
    assert result["parameters"]["Cab"] == 5


def test_make_matched_cabinet_pro_none_exemplar_params_uses_defaults() -> None:
    """When no exemplar cabinet existed, schema defaults are used."""
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=None,
    )
    assert result["parameters"]["Vol"] == pytest.approx(0.7)  # schema default
    assert result["parameters"]["Cab"] == 10  # lookup override


def test_make_matched_cabinet_pro_llm_overrides_exemplar() -> None:
    """LLM explicit choices beat exemplar values (e.g. airy tone → more room)."""
    exemplar_params = {"Vol": 0.45, "Cab": 99}
    llm_params = {"Vol": 0.6}  # LLM chose a different volume
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=exemplar_params,
        llm_cabinet_params=llm_params,
    )
    # LLM wins over exemplar for Vol
    assert result["parameters"]["Vol"] == pytest.approx(0.6)
    # Cab always from lookup
    assert result["parameters"]["Cab"] == 10


def test_make_matched_cabinet_pro_three_tier_layering() -> None:
    """Schema default < exemplar < LLM < Cab lookup — full chain."""
    # Schema has Vol=0.7, Cab=0
    exemplar_params = {"Vol": 0.45}  # overrides schema Vol
    llm_params = {"Vol": 0.8}  # overrides exemplar Vol
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=exemplar_params,
        llm_cabinet_params=llm_params,
    )
    assert result["parameters"]["Vol"] == pytest.approx(0.8)  # LLM wins
    assert result["parameters"]["Cab"] == 10  # lookup wins over everything


def test_make_matched_cabinet_pro_llm_only_no_exemplar() -> None:
    """LLM params work even when no exemplar cabinet exists."""
    llm_params = {"Vol": 0.55}
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=None,
        llm_cabinet_params=llm_params,
    )
    assert result["parameters"]["Vol"] == pytest.approx(0.55)
    assert result["parameters"]["Cab"] == 10


def test_make_matched_cabinet_pro_exemplar_fills_gaps_llm_missed() -> None:
    """Exemplar provides values for params the LLM didn't explicitly set."""
    # Schema has Vol=0.7 and Cab=0
    # Exemplar sets both
    exemplar_params = {"Vol": 0.45, "Cab": 23}
    # LLM only set Cab (which lookup will override anyway)
    llm_params = {"Cab": 15}
    result = _make_matched_cabinet_pro(
        "Lead 800",
        _AMP_CABINET_LOOKUP,
        _SCHEMA_WITH_CABINET,
        "preset",
        exemplar_cabinet_params=exemplar_params,
        llm_cabinet_params=llm_params,
    )
    # Vol from exemplar (LLM didn't touch it)
    assert result["parameters"]["Vol"] == pytest.approx(0.45)
    # Cab from lookup (always wins)
    assert result["parameters"]["Cab"] == 10


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


# ---------------------------------------------------------------------------
# _find_amp_index
# ---------------------------------------------------------------------------


def test_find_amp_index_returns_correct_position() -> None:
    components = [
        {"component_name": "Tube Screamer"},
        {"component_name": "Lead 800"},
        {"component_name": "Solid EQ"},
    ]
    result = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    assert result == 1


def test_find_amp_index_case_insensitive() -> None:
    components = [{"component_name": "lead 800"}]
    result = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    assert result == 0


def test_find_amp_index_no_match() -> None:
    components = [{"component_name": "Tube Screamer"}, {"component_name": "Solid EQ"}]
    result = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    assert result is None


def test_find_amp_index_empty_list() -> None:
    result = _find_amp_index([], _AMP_CABINET_LOOKUP)
    assert result is None


# ---------------------------------------------------------------------------
# _extract_exemplar_cabinet_params
# ---------------------------------------------------------------------------

_EXEMPLARS_WITH_CABINET = [
    {
        "preset_name": "800 Rocks",
        "tags": ["Distorted", "Rock"],
        "components": [
            {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {"Drv": 0.6}},
            {"component_name": "Lead 800", "component_id": 57000, "parameters": {"Gn": 0.7}},
            {
                "component_name": "Matched Cabinet Pro",
                "component_id": 156000,
                "parameters": {"Pwr": 1.0, "MV": 0.45, "c": 0.12, "Cab": 10.0, "V": 0.0, "st": 1.0},
            },
        ],
    },
]


def test_extract_exemplar_cabinet_params_returns_cabinet() -> None:
    result = _extract_exemplar_cabinet_params(_EXEMPLARS_WITH_CABINET)
    assert result is not None
    assert result["MV"] == pytest.approx(0.45)
    assert result["c"] == pytest.approx(0.12)


def test_extract_exemplar_cabinet_params_no_cabinet() -> None:
    exemplars = [
        {
            "preset_name": "Dry",
            "tags": [],
            "components": [
                {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {}},
            ],
        },
    ]
    result = _extract_exemplar_cabinet_params(exemplars)
    assert result is None


def test_extract_exemplar_cabinet_params_falls_through() -> None:
    """If the first exemplar has no cabinet, fall through to the next."""
    exemplars = [
        {
            "preset_name": "NoCab",
            "tags": [],
            "components": [
                {"component_name": "Lead 800", "component_id": 57000, "parameters": {}},
            ],
        },
        _EXEMPLARS_WITH_CABINET[0],
    ]
    result = _extract_exemplar_cabinet_params(exemplars)
    assert result is not None
    assert result["MV"] == pytest.approx(0.45)


def test_extract_exemplar_cabinet_params_empty() -> None:
    result = _extract_exemplar_cabinet_params([])
    assert result is None


def test_extract_exemplar_cabinet_params_returns_copy() -> None:
    """Returned dict must be a copy so mutations don't affect the exemplar store."""
    result = _extract_exemplar_cabinet_params(_EXEMPLARS_WITH_CABINET)
    assert result is not None
    result["MV"] = 999
    original = _EXEMPLARS_WITH_CABINET[0]["components"][2]["parameters"]["MV"]
    assert original == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# Cabinet insertion ordering
# ---------------------------------------------------------------------------


def test_cabinet_inserted_after_amp_not_at_end() -> None:
    """Post-cabinet effects must remain after the cabinet, not be displaced."""
    components = [
        {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {}},
        {"component_name": "Lead 800", "component_id": 57000, "parameters": {}},
        {"component_name": "Solid EQ", "component_id": 121000, "parameters": {}},
    ]
    # Simulate the enforcement logic from map_components
    base_exemplar = "test"
    components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]
    amp_name = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    cabinet = _make_matched_cabinet_pro(
        amp_name, _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, base_exemplar
    )
    amp_idx = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    if amp_idx is not None:
        components.insert(amp_idx + 1, cabinet)
    else:
        components.append(cabinet)

    names = [c["component_name"] for c in components]
    assert names == ["Tube Screamer", "Lead 800", "Matched Cabinet Pro", "Solid EQ"]


def test_cabinet_appended_when_no_amp() -> None:
    """When no amp is found, cabinet falls back to end of chain."""
    components = [
        {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {}},
        {"component_name": "Solid EQ", "component_id": 121000, "parameters": {}},
    ]
    base_exemplar = "test"
    components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]
    amp_name = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    cabinet = _make_matched_cabinet_pro(
        amp_name, _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, base_exemplar
    )
    amp_idx = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    if amp_idx is not None:
        components.insert(amp_idx + 1, cabinet)
    else:
        components.append(cabinet)

    names = [c["component_name"] for c in components]
    assert names == ["Tube Screamer", "Solid EQ", "Matched Cabinet Pro"]


def test_llm_emitted_cabinet_stripped_before_insertion() -> None:
    """Any cabinet the LLM emitted is removed; only the enforced one remains."""
    components = [
        {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {}},
        {"component_name": "Lead 800", "component_id": 57000, "parameters": {}},
        {"component_name": "Matched Cabinet Pro", "component_id": 156000, "parameters": {}},
        {"component_name": "Solid EQ", "component_id": 121000, "parameters": {}},
    ]
    base_exemplar = "test"
    components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]
    amp_name = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    cabinet = _make_matched_cabinet_pro(
        amp_name, _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, base_exemplar
    )
    amp_idx = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    if amp_idx is not None:
        components.insert(amp_idx + 1, cabinet)
    else:
        components.append(cabinet)

    names = [c["component_name"] for c in components]
    assert names == ["Tube Screamer", "Lead 800", "Matched Cabinet Pro", "Solid EQ"]
    # Only one cabinet total
    assert sum(1 for c in components if "cabinet" in c["component_name"].lower()) == 1


def test_cabinet_ordering_with_multiple_post_effects() -> None:
    """Multiple post-cabinet effects preserve their relative order."""
    components = [
        {"component_name": "Tube Screamer", "component_id": 73000, "parameters": {}},
        {"component_name": "Lead 800", "component_id": 57000, "parameters": {}},
        {"component_name": "Twin Delay", "component_id": 98000, "parameters": {}},
        {"component_name": "Studio Reverb", "component_id": 33000, "parameters": {}},
        {"component_name": "Solid Buscomp", "component_id": 122000, "parameters": {}},
    ]
    base_exemplar = "test"
    components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]
    amp_name = _find_amp_name(components, _AMP_CABINET_LOOKUP)
    cabinet = _make_matched_cabinet_pro(
        amp_name, _AMP_CABINET_LOOKUP, _SCHEMA_WITH_CABINET, base_exemplar
    )
    amp_idx = _find_amp_index(components, _AMP_CABINET_LOOKUP)
    if amp_idx is not None:
        components.insert(amp_idx + 1, cabinet)
    else:
        components.append(cabinet)

    names = [c["component_name"] for c in components]
    assert names == [
        "Tube Screamer",
        "Lead 800",
        "Matched Cabinet Pro",
        "Twin Delay",
        "Studio Reverb",
        "Solid Buscomp",
    ]


# ---------------------------------------------------------------------------
# build_crp_reference_context
# ---------------------------------------------------------------------------


def test_crp_reference_context_full_production() -> None:
    result = build_crp_reference_context("FULL_PRODUCTION")
    assert isinstance(result, str)
    assert "CABINETS" in result
    assert "MICROPHONES" in result
    assert "MIC POSITIONS" in result
    assert "DI Box" in result
    assert "Dyn 57" in result


def test_crp_reference_context_amp_only_omits_tables() -> None:
    result = build_crp_reference_context("AMP_ONLY")
    assert "CABINETS" not in result
    assert "Matched Cabinet Pro" in result


# ---------------------------------------------------------------------------
# _validate_crp_params
# ---------------------------------------------------------------------------


def _crp_component(
    cab1: float | int | None = 8,
    mic1: float | int | None = 1,
    mpos1: float | int | None = 0,
) -> dict:
    params: dict[str, float | int] = {"Pwr": 1.0, "v": 0.8}
    if cab1 is not None:
        params["Cab1"] = cab1
    if mic1 is not None:
        params["Mic1"] = mic1
    if mpos1 is not None:
        params["MPos1"] = mpos1
    return {"component_name": "Control Room Pro", "component_id": 119000, "parameters": params}


def test_validate_crp_params_casts_float_to_int() -> None:
    comps = [_crp_component(cab1=8.0, mic1=1.0, mpos1=2.0)]
    _validate_crp_params(comps)
    params = comps[0]["parameters"]
    assert isinstance(params["Cab1"], int)
    assert isinstance(params["Mic1"], int)
    assert isinstance(params["MPos1"], int)
    assert params["Cab1"] == 8
    assert params["Mic1"] == 1
    assert params["MPos1"] == 2


def test_validate_crp_params_valid_range_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    comps = [_crp_component(cab1=17, mic1=1, mpos1=0)]
    with caplog.at_level("WARNING"):
        _validate_crp_params(comps)
    assert caplog.text == ""


def test_validate_crp_params_missing_cab1_warns(caplog: pytest.LogCaptureFixture) -> None:
    comps = [_crp_component(cab1=None)]
    with caplog.at_level("WARNING"):
        _validate_crp_params(comps)
    assert "missing Cab1" in caplog.text


def test_validate_crp_params_missing_mic1_warns(caplog: pytest.LogCaptureFixture) -> None:
    comps = [_crp_component(mic1=None)]
    with caplog.at_level("WARNING"):
        _validate_crp_params(comps)
    assert "missing Mic1" in caplog.text


def test_validate_crp_params_missing_mpos1_warns(caplog: pytest.LogCaptureFixture) -> None:
    comps = [_crp_component(mpos1=None)]
    with caplog.at_level("WARNING"):
        _validate_crp_params(comps)
    assert "missing MPos1" in caplog.text


def test_validate_crp_params_out_of_range_cab1_warns(caplog: pytest.LogCaptureFixture) -> None:
    comps = [_crp_component(cab1=30)]
    with caplog.at_level("WARNING"):
        _validate_crp_params(comps)
    assert "out of range" in caplog.text


def test_validate_crp_params_skips_non_crp() -> None:
    """Non-CRP components are ignored by the validator."""
    comps = [{"component_name": "Tube Screamer", "parameters": {"Drv": 0.5}}]
    _validate_crp_params(comps)  # should not raise
