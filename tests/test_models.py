"""Tests for tonedef.models — Pydantic ComponentOutput + schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tonedef.models import ComponentOutput, validate_component_against_schema

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SCHEMA = {
    "Tweed Delight": {
        "component_name": "Tweed Delight",
        "component_id": 79000,
        "parameters": [
            {"param_id": "vb", "param_name": "Bright", "default_value": 0.5},
            {"param_id": "vo", "param_name": "Volume", "default_value": 0.7},
        ],
    },
    "Lead 800": {
        "component_name": "Lead 800",
        "component_id": 42000,
        "parameters": [
            {"param_id": "Gn", "param_name": "Gain", "default_value": 0.6},
        ],
    },
}

_VALID_DICT: dict = {
    "component_name": "Tweed Delight",
    "component_id": 79000,
    "base_exemplar": "My Preset",
    "modification": "adjusted",
    "confidence": "documented",
    "rationale": "Classic Fender-voiced amp for warm cleans.",
    "parameters": {"vb": 0.8, "vo": 0.5},
}


# ---------------------------------------------------------------------------
# ComponentOutput — basic structural validation
# ---------------------------------------------------------------------------


class TestComponentOutputValid:
    def test_parses_valid_dict(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        assert comp.component_name == "Tweed Delight"
        assert comp.component_id == 79000
        assert comp.modification == "adjusted"
        assert comp.confidence == "documented"

    def test_default_base_exemplar(self) -> None:
        d = {**_VALID_DICT}
        del d["base_exemplar"]
        comp = ComponentOutput.model_validate(d)
        assert comp.base_exemplar == ""

    def test_rationale_preserved(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        assert comp.rationale == "Classic Fender-voiced amp for warm cleans."

    def test_default_rationale(self) -> None:
        d = {**_VALID_DICT}
        del d["rationale"]
        comp = ComponentOutput.model_validate(d)
        assert comp.rationale == ""

    def test_description_preserved(self) -> None:
        d = {**_VALID_DICT, "description": "Warm tube amplifier."}
        comp = ComponentOutput.model_validate(d)
        assert comp.description == "Warm tube amplifier."

    def test_default_description(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        assert comp.description == ""

    def test_parameters_preserved(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        assert comp.parameters == {"vb": 0.8, "vo": 0.5}


class TestComponentOutputEnumValidation:
    def test_bad_modification_raises(self) -> None:
        d = {**_VALID_DICT, "modification": "deleted"}
        with pytest.raises(ValidationError, match="modification"):
            ComponentOutput.model_validate(d)

    def test_bad_confidence_raises(self) -> None:
        d = {**_VALID_DICT, "confidence": "guessed"}
        with pytest.raises(ValidationError, match="confidence"):
            ComponentOutput.model_validate(d)

    def test_all_modification_values(self) -> None:
        for mod in ("unchanged", "adjusted", "swapped", "added"):
            d = {**_VALID_DICT, "modification": mod}
            comp = ComponentOutput.model_validate(d)
            assert comp.modification == mod

    def test_all_confidence_values(self) -> None:
        for conf in ("documented", "inferred", "estimated"):
            d = {**_VALID_DICT, "confidence": conf}
            comp = ComponentOutput.model_validate(d)
            assert comp.confidence == conf


class TestComponentOutputCoercion:
    def test_list_parameters_coerced_to_dict(self) -> None:
        """LLM occasionally emits params as a list of {param_id, value}."""
        d = {
            **_VALID_DICT,
            "parameters": [
                {"param_id": "vb", "value": 0.9},
                {"param_id": "vo", "value": 0.3},
            ],
        }
        comp = ComponentOutput.model_validate(d)
        assert comp.parameters == {"vb": 0.9, "vo": 0.3}

    def test_empty_list_parameters_coerced(self) -> None:
        d = {**_VALID_DICT, "parameters": []}
        comp = ComponentOutput.model_validate(d)
        assert comp.parameters == {}


class TestComponentOutputMissingFields:
    def test_missing_component_name_raises(self) -> None:
        d = {**_VALID_DICT}
        del d["component_name"]
        with pytest.raises(ValidationError, match="component_name"):
            ComponentOutput.model_validate(d)

    def test_missing_component_id_raises(self) -> None:
        d = {**_VALID_DICT}
        del d["component_id"]
        with pytest.raises(ValidationError, match="component_id"):
            ComponentOutput.model_validate(d)

    def test_missing_modification_raises(self) -> None:
        d = {**_VALID_DICT}
        del d["modification"]
        with pytest.raises(ValidationError, match="modification"):
            ComponentOutput.model_validate(d)

    def test_missing_confidence_raises(self) -> None:
        d = {**_VALID_DICT}
        del d["confidence"]
        with pytest.raises(ValidationError, match="confidence"):
            ComponentOutput.model_validate(d)


# ---------------------------------------------------------------------------
# validate_component_against_schema
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_valid_component_no_errors(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        errors = validate_component_against_schema(comp, _SCHEMA)
        assert errors == []

    def test_unknown_component_name(self) -> None:
        d = {**_VALID_DICT, "component_name": "Fantasy Amp"}
        comp = ComponentOutput.model_validate(d)
        errors = validate_component_against_schema(comp, _SCHEMA)
        assert any("Unknown component_name" in e for e in errors)

    def test_wrong_component_id(self) -> None:
        d = {**_VALID_DICT, "component_id": 99999}
        comp = ComponentOutput.model_validate(d)
        errors = validate_component_against_schema(comp, _SCHEMA)
        assert any("does not match schema" in e for e in errors)

    def test_unknown_param_id(self) -> None:
        d = {**_VALID_DICT, "parameters": {"vb": 0.8, "UNKNOWN": 0.5}}
        comp = ComponentOutput.model_validate(d)
        errors = validate_component_against_schema(comp, _SCHEMA)
        assert any("unknown param_id" in e for e in errors)

    def test_multiple_errors(self) -> None:
        d = {
            **_VALID_DICT,
            "component_id": 99999,
            "parameters": {"vb": 0.8, "BAD1": 0.1, "BAD2": 0.2},
        }
        comp = ComponentOutput.model_validate(d)
        errors = validate_component_against_schema(comp, _SCHEMA)
        # wrong ID + 2 unknown params
        assert len(errors) == 3

    def test_empty_schema_all_unknown(self) -> None:
        comp = ComponentOutput.model_validate(_VALID_DICT)
        errors = validate_component_against_schema(comp, {})
        assert any("Unknown component_name" in e for e in errors)

    def test_model_dump_roundtrip(self) -> None:
        """model_dump() produces a dict that matches the original structure."""
        comp = ComponentOutput.model_validate(_VALID_DICT)
        d = comp.model_dump()
        assert d["component_name"] == "Tweed Delight"
        assert d["parameters"]["vb"] == 0.8
