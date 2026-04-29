"""Backward-compatible imports for structured ToneDef models."""

from __future__ import annotations

from tonedef.schemas import ComponentOutput, validate_component_against_schema

__all__ = ["ComponentOutput", "validate_component_against_schema"]
