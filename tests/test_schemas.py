from __future__ import annotations

import pytest
from pydantic import ValidationError

from tonedef.models import ComponentOutput as CompatibilityComponentOutput
from tonedef.schemas import ComponentOutput, ExtractedEntity


def test_extracted_entity_is_strict() -> None:
    entity = ExtractedEntity(name="LiteLLM", category="library", confidence=0.95)

    assert entity.name == "LiteLLM"


def test_extracted_entity_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        ExtractedEntity(name="LiteLLM", category="library", confidence=2.0)


def test_component_output_is_strict() -> None:
    with pytest.raises(ValidationError):
        ComponentOutput.model_validate(
            {
                "component_name": "Lead 800",
                "component_id": "56000",
                "modification": "adjusted",
                "confidence": "documented",
                "parameters": {"vb": 0.7},
            }
        )


def test_component_output_schema_has_llm_field_descriptions() -> None:
    schema = ComponentOutput.model_json_schema()

    assert schema["properties"]["component_name"]["description"]
    assert schema["properties"]["parameters"]["description"]
    assert schema["properties"]["confidence"]["description"]


def test_component_output_compatibility_import_matches_schema() -> None:
    assert CompatibilityComponentOutput is ComponentOutput
