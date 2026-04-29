from __future__ import annotations

import pytest
from pydantic import ValidationError

from tonedef.schemas import ExtractedEntity


def test_extracted_entity_is_strict() -> None:
    entity = ExtractedEntity(name="LiteLLM", category="library", confidence=0.95)

    assert entity.name == "LiteLLM"


def test_extracted_entity_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        ExtractedEntity(name="LiteLLM", category="library", confidence=2.0)
