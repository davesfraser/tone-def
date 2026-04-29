from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BaseResponse(BaseModel):
    """Strict base class for future structured LLM outputs."""

    model_config = ConfigDict(strict=True)


class ExtractedEntity(BaseResponse):
    """Example schema for Instructor-backed structured extraction."""

    name: str = Field(description="The entity name exactly as it appears in the source text.")
    category: str = Field(description="A short category label for the entity.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0 to 1.")


class ComponentOutput(BaseResponse):
    """A single Guitar Rig 7 component emitted by the Phase 2 LLM."""

    component_name: str = Field(
        description="Canonical Guitar Rig component name from the component schema."
    )
    component_id: int = Field(description="Numeric Guitar Rig component identifier.")
    base_exemplar: str = Field(
        default="",
        description="Factory preset or exemplar that grounded this component choice.",
    )
    modification: Literal["unchanged", "adjusted", "swapped", "added"] = Field(
        description="How this component differs from the grounding exemplar."
    )
    confidence: Literal["documented", "inferred", "estimated"] = Field(
        description="Evidence level supporting the selected component and settings."
    )
    rationale: str = Field(
        default="",
        description="Brief tonal reason for choosing this component or setting change.",
    )
    description: str = Field(
        default="",
        description="Short user-facing summary of the component's role in the chain.",
    )
    parameters: dict[str, float | int] = Field(
        description="Mapping of schema parameter IDs to numeric values."
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_parameters(cls, data: Any) -> Any:
        """Ensure ``parameters`` is a dict when the LLM emits list-form params."""
        if isinstance(data, dict):
            params = data.get("parameters")
            if isinstance(params, list):
                converted: dict[str, float | int] = {}
                for item in params:
                    if isinstance(item, dict) and "param_id" in item and "value" in item:
                        converted[item["param_id"]] = item["value"]
                data["parameters"] = converted
        return data

    @model_validator(mode="after")
    def _validate_against_schema(self) -> ComponentOutput:
        """Schema-aware hard checks are handled by ``validate_component_against_schema``."""
        return self


def validate_component_against_schema(
    component: ComponentOutput,
    schema: dict,
) -> list[str]:
    """Validate a single component against the full component schema."""
    errors: list[str] = []
    name = component.component_name

    if name not in schema:
        errors.append(f"Unknown component_name: {name!r}")
        return errors

    entry = schema[name]
    expected_id = entry.get("component_id")
    if expected_id is not None and component.component_id != expected_id:
        errors.append(
            f"{name}: component_id {component.component_id} does not match schema ({expected_id})"
        )

    known_param_ids = {p["param_id"] for p in entry.get("parameters", [])}
    for pid in component.parameters:
        if pid not in known_param_ids:
            errors.append(f"{name}: unknown param_id {pid!r}")

    return errors
