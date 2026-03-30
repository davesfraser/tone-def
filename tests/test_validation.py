"""Tests for tonedef.validation — all validate_* functions."""

from __future__ import annotations

from tonedef.models import ComponentOutput
from tonedef.signal_chain_parser import ParsedSignalChain, Section, Unit
from tonedef.validation import (
    ValidationResult,
    validate_phase1,
    validate_phase2,
    validate_pre_build,
    validate_retrieval,
    validate_signal_chain_order,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_comp(**overrides: object) -> ComponentOutput:
    """Build a minimal valid ComponentOutput with overrides."""
    defaults: dict = {
        "component_name": "Tweed Delight",
        "component_id": 79000,
        "base_exemplar": "preset",
        "modification": "adjusted",
        "confidence": "documented",
        "parameters": {"vb": 0.5},
    }
    defaults.update(overrides)
    return ComponentOutput.model_validate(defaults)


def _make_parsed(**overrides: object) -> ParsedSignalChain:
    """Build a minimal valid ParsedSignalChain with overrides."""
    defaults: dict = {
        "chain_type": "FULL_PRODUCTION",
        "chain_type_reason": "reason",
        "sections": [
            Section(
                title="Signal Chain",
                units=[Unit(name="Amp", unit_type="Amplifier", provenance="DOCUMENTED")],
            ),
            Section(
                title="Cabinet And Mic",
                units=[Unit(name="Cab", unit_type="Cabinet", provenance="DOCUMENTED")],
            ),
        ],
        "tags_characters": ["warm"],
        "tags_genres": ["rock"],
    }
    defaults.update(overrides)
    return ParsedSignalChain(**defaults)


_SCHEMA = {
    "Tweed Delight": {
        "component_name": "Tweed Delight",
        "component_id": 79000,
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
        ],
    },
    "Lead 800": {
        "component_name": "Lead 800",
        "component_id": 42000,
        "parameters": [
            {
                "param_id": "Gn",
                "param_name": "Gain",
                "default_value": 0.6,
                "stats": {"min": 0.0, "max": 1.0},
            },
        ],
    },
    "Matched Cabinet Pro": {
        "component_name": "Matched Cabinet Pro",
        "component_id": 156000,
        "parameters": [
            {
                "param_id": "Vol",
                "param_name": "Volume",
                "default_value": 0.7,
                "stats": {"min": 0.0, "max": 1.0},
            },
        ],
    },
}

_AMP_CAB_LOOKUP = {
    "Tweed Delight": {
        "cabinet_component_name": "Matched Cabinet Pro",
        "cabinet_component_id": 156000,
        "cab_value": 5,
    },
    "Lead 800": {
        "cabinet_component_name": "Matched Cabinet Pro",
        "cabinet_component_id": 156000,
        "cab_value": 10,
    },
}


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_empty_is_valid(self) -> None:
        vr = ValidationResult()
        assert vr.is_valid

    def test_warnings_still_valid(self) -> None:
        vr = ValidationResult(warnings=["something"])
        assert vr.is_valid

    def test_errors_not_valid(self) -> None:
        vr = ValidationResult(errors=["bad"])
        assert not vr.is_valid

    def test_str_no_issues(self) -> None:
        assert "No issues" in str(ValidationResult())

    def test_str_shows_errors(self) -> None:
        vr = ValidationResult(errors=["e1"])
        s = str(vr)
        assert "Errors" in s
        assert "e1" in s

    def test_str_shows_warnings(self) -> None:
        vr = ValidationResult(warnings=["w1"])
        s = str(vr)
        assert "Warnings" in s
        assert "w1" in s

    def test_merge(self) -> None:
        a = ValidationResult(errors=["e1"], warnings=["w1"])
        b = ValidationResult(errors=["e2"], warnings=["w2"])
        merged = a.merge(b)
        assert len(merged.errors) == 2
        assert len(merged.warnings) == 2
        # Originals unchanged
        assert len(a.errors) == 1


# ---------------------------------------------------------------------------
# validate_phase1
# ---------------------------------------------------------------------------


class TestValidatePhase1:
    def test_valid_full_production(self) -> None:
        result = validate_phase1(_make_parsed())
        assert result.is_valid
        assert not result.warnings

    def test_valid_amp_only(self) -> None:
        parsed = _make_parsed(
            chain_type="AMP_ONLY",
            sections=[
                Section(
                    title="Signal Chain",
                    units=[Unit(name="Amp", unit_type="Amplifier", provenance="DOCUMENTED")],
                )
            ],
        )
        result = validate_phase1(parsed)
        assert result.is_valid

    def test_empty_chain_type_error(self) -> None:
        parsed = _make_parsed(chain_type="")
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("signal chain type" in e for e in result.errors)

    def test_invalid_chain_type_error(self) -> None:
        parsed = _make_parsed(chain_type="WEIRD")
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("WEIRD" in e for e in result.errors)

    def test_no_sections_error(self) -> None:
        parsed = _make_parsed(sections=[])
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("No signal chain sections" in e for e in result.errors)

    def test_empty_units_error(self) -> None:
        parsed = _make_parsed(sections=[Section(title="Signal Chain", units=[])])
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("No gear" in e for e in result.errors)

    def test_empty_unit_name_error(self) -> None:
        parsed = _make_parsed(
            sections=[
                Section(
                    title="Signal Chain",
                    units=[Unit(name="", unit_type="Amp", provenance="DOCUMENTED")],
                )
            ]
        )
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("has no name" in e for e in result.errors)

    def test_empty_unit_type_error(self) -> None:
        parsed = _make_parsed(
            sections=[
                Section(
                    title="Signal Chain",
                    units=[Unit(name="Amp", unit_type="", provenance="DOCUMENTED")],
                )
            ]
        )
        result = validate_phase1(parsed)
        assert not result.is_valid
        assert any("no type specified" in e for e in result.errors)

    def test_full_production_missing_cabinet_warns(self) -> None:
        parsed = _make_parsed(
            sections=[
                Section(
                    title="Signal Chain",
                    units=[Unit(name="Amp", unit_type="Amplifier", provenance="DOCUMENTED")],
                )
            ]
        )
        result = validate_phase1(parsed)
        assert result.is_valid  # warning, not error
        assert any("cabinet and microphone" in w for w in result.warnings)

    def test_amp_only_no_cabinet_no_warning(self) -> None:
        parsed = _make_parsed(
            chain_type="AMP_ONLY",
            sections=[
                Section(
                    title="Signal Chain",
                    units=[Unit(name="Amp", unit_type="Amplifier", provenance="DOCUMENTED")],
                )
            ],
        )
        result = validate_phase1(parsed)
        assert not any("Cabinet" in w for w in result.warnings)

    def test_no_tags_warns(self) -> None:
        parsed = _make_parsed(tags_characters=[], tags_genres=[])
        result = validate_phase1(parsed)
        assert any("tags" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_retrieval
# ---------------------------------------------------------------------------


class TestValidateRetrieval:
    def test_good_retrieval(self) -> None:
        exemplars = [{"distance": 0.2}]  # score = 0.8
        result = validate_retrieval(exemplars)
        assert result.is_valid
        assert not result.warnings

    def test_empty_exemplars_warns(self) -> None:
        result = validate_retrieval([])
        assert result.is_valid  # warning, not error
        assert any("No similar factory presets" in w for w in result.warnings)

    def test_low_score_warns(self) -> None:
        exemplars = [{"distance": 0.95}]  # score = 0.05
        result = validate_retrieval(exemplars)
        assert any("weak" in w for w in result.warnings)

    def test_custom_threshold(self) -> None:
        exemplars = [{"distance": 0.7}]  # score = 0.3
        result = validate_retrieval(exemplars, min_score=0.5)
        assert any("weak" in w for w in result.warnings)

    def test_exact_threshold_passes(self) -> None:
        exemplars = [{"distance": 0.8}]  # score = 0.2
        result = validate_retrieval(exemplars, min_score=0.1)
        assert not result.warnings


# ---------------------------------------------------------------------------
# validate_phase2
# ---------------------------------------------------------------------------


class TestValidatePhase2:
    def test_valid_components(self) -> None:
        comp = _make_comp()
        result = validate_phase2([comp], _SCHEMA)
        assert result.is_valid

    def test_empty_list_error(self) -> None:
        result = validate_phase2([], _SCHEMA)
        assert not result.is_valid
        assert any("No components" in e for e in result.errors)

    def test_unknown_name_error(self) -> None:
        comp = _make_comp(component_name="Fantasy Amp")
        result = validate_phase2([comp], _SCHEMA)
        assert not result.is_valid
        assert any("Unknown" in e for e in result.errors)

    def test_wrong_id_error(self) -> None:
        comp = _make_comp(component_id=99999)
        result = validate_phase2([comp], _SCHEMA)
        assert not result.is_valid
        assert any("does not match" in e for e in result.errors)

    def test_unknown_param_error(self) -> None:
        comp = _make_comp(parameters={"vb": 0.5, "UNKNOWN": 0.1})
        result = validate_phase2([comp], _SCHEMA)
        assert not result.is_valid
        assert any("unknown param_id" in e for e in result.errors)

    def test_param_out_of_range_warns(self) -> None:
        comp = _make_comp(parameters={"vb": 1.5})
        result = validate_phase2([comp], _SCHEMA)
        assert result.is_valid  # schema errors are about value, not unknown
        assert any("outside observed range" in w for w in result.warnings)

    def test_param_below_range_warns(self) -> None:
        comp = _make_comp(parameters={"vb": -0.1})
        result = validate_phase2([comp], _SCHEMA)
        assert any("outside observed range" in w for w in result.warnings)

    def test_param_at_boundary_no_warning(self) -> None:
        comp = _make_comp(parameters={"vb": 0.0})
        result = validate_phase2([comp], _SCHEMA)
        assert not result.warnings


# ---------------------------------------------------------------------------
# validate_signal_chain_order
# ---------------------------------------------------------------------------


class TestValidateSignalChainOrder:
    def test_correct_order(self) -> None:
        comps = [
            _make_comp(component_name="Tweed Delight", component_id=79000),
            _make_comp(component_name="Matched Cabinet Pro", component_id=156000),
        ]
        result = validate_signal_chain_order(comps, _AMP_CAB_LOOKUP)
        assert result.is_valid
        assert not result.warnings

    def test_no_amp_error(self) -> None:
        comps = [_make_comp(component_name="Matched Cabinet Pro", component_id=156000)]
        result = validate_signal_chain_order(comps, _AMP_CAB_LOOKUP)
        assert not result.is_valid
        assert any("No amp" in e for e in result.errors)

    def test_no_cabinet_warns(self) -> None:
        comps = [_make_comp(component_name="Tweed Delight", component_id=79000)]
        result = validate_signal_chain_order(comps, _AMP_CAB_LOOKUP)
        assert result.is_valid
        assert any("No cabinet" in w for w in result.warnings)

    def test_cabinet_before_amp_warns(self) -> None:
        comps = [
            _make_comp(component_name="Matched Cabinet Pro", component_id=156000),
            _make_comp(component_name="Tweed Delight", component_id=79000),
        ]
        result = validate_signal_chain_order(comps, _AMP_CAB_LOOKUP)
        assert any("before the amplifier" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_pre_build
# ---------------------------------------------------------------------------


class TestValidatePreBuild:
    def test_valid_chain(self) -> None:
        comps = [
            _make_comp(component_name="Tweed Delight", component_id=79000),
            _make_comp(component_name="Matched Cabinet Pro", component_id=156000),
        ]
        result = validate_pre_build(comps)
        assert result.is_valid

    def test_empty_list_error(self) -> None:
        result = validate_pre_build([])
        assert not result.is_valid
        assert any("preset is empty" in e for e in result.errors)

    def test_no_cabinet_error(self) -> None:
        comps = [_make_comp(component_name="Tweed Delight", component_id=79000)]
        result = validate_pre_build(comps)
        assert not result.is_valid
        assert any("cabinet" in e.lower() for e in result.errors)

    def test_duplicate_ids_warns(self) -> None:
        comps = [
            _make_comp(component_name="Tweed Delight", component_id=79000),
            _make_comp(component_name="Matched Cabinet Pro", component_id=79000),
        ]
        result = validate_pre_build(comps)
        assert any("Duplicate" in w for w in result.warnings)
