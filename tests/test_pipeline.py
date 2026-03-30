"""Tests for tonedef.pipeline.compose_query."""

from __future__ import annotations

from tonedef.pipeline import compose_query


def test_compose_query_no_modifiers_returns_text() -> None:
    assert compose_query("Hendrix fuzz", []) == "Hendrix fuzz"


def test_compose_query_with_modifiers_appends() -> None:
    result = compose_query("Hendrix fuzz", ["grittier", "saggy", "roomy"])
    assert result == "Hendrix fuzz\n\nTonal modifiers: grittier, saggy, roomy"


def test_compose_query_single_modifier() -> None:
    result = compose_query("warm jazz", ["darker"])
    assert result == "warm jazz\n\nTonal modifiers: darker"
