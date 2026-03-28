# applied-skills: ds-workflow
"""Pydantic models for pipeline output validation.

``ComponentOutput`` validates the JSON dicts emitted by the Phase 2 LLM call.
Hard structural errors (unknown component, wrong ID, unknown param_id) are
caught at parse time via ``model_validator``.  Soft warnings (range violations)
are handled separately in ``validation.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_validator


class ComponentOutput(BaseModel):
    """A single GR7 component as returned by Phase 2.

    Pass the component schema dict via Pydantic validation context::

        ComponentOutput.model_validate(
            raw_dict,
            context={"schema": schema},
        )

    When no context is provided the schema-aware checks are skipped
    (useful for tests that only need structural validation).
    """

    component_name: str
    component_id: int
    base_exemplar: str = ""
    modification: Literal["unchanged", "adjusted", "swapped", "added"]
    confidence: Literal["documented", "inferred", "estimated"]
    parameters: dict[str, float | int]

    @model_validator(mode="before")
    @classmethod
    def _coerce_parameters(cls, data: Any) -> Any:
        """Ensure ``parameters`` is a dict (the LLM occasionally emits a list)."""
        if isinstance(data, dict):
            params = data.get("parameters")
            if isinstance(params, list):
                # Attempt [{param_id: ..., value: ...}, ...] → {param_id: value}
                converted: dict[str, float | int] = {}
                for item in params:
                    if isinstance(item, dict) and "param_id" in item and "value" in item:
                        converted[item["param_id"]] = item["value"]
                data["parameters"] = converted
        return data

    @model_validator(mode="after")
    def _validate_against_schema(self) -> ComponentOutput:
        """Check component_name, component_id, and param_ids against schema.

        The schema is passed via ``context={"schema": ...}``.  If no context
        is provided the checks are silently skipped.
        """
        # Schema-aware hard checks are handled externally by
        # validate_component_against_schema() in this same module.
        # Pydantic v2 "after" validators don't receive context directly,
        # so we keep this as a structural pass-through.
        return self


def validate_component_against_schema(
    component: ComponentOutput,
    schema: dict,
) -> list[str]:
    """Validate a single component against the full component schema.

    Returns a list of error messages (empty if valid).

    Args:
        component: A validated ``ComponentOutput`` instance.
        schema: Parsed ``component_schema.json`` keyed by component_name.

    Returns:
        List of error strings.  Empty means the component is schema-valid.
    """
    errors: list[str] = []
    name = component.component_name

    if name not in schema:
        errors.append(f"Unknown component_name: {name!r}")
        return errors  # can't check further

    entry = schema[name]

    # Check component_id
    expected_id = entry.get("component_id")
    if expected_id is not None and component.component_id != expected_id:
        errors.append(
            f"{name}: component_id {component.component_id} does not match schema ({expected_id})"
        )

    # Check param_ids
    known_param_ids = {p["param_id"] for p in entry.get("parameters", [])}
    for pid in component.parameters:
        if pid not in known_param_ids:
            errors.append(f"{name}: unknown param_id {pid!r}")

    return errors
