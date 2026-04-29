"""Tests for tonedef.pipeline.compose_query."""

from __future__ import annotations

from tonedef import pipeline
from tonedef.pipeline import compose_query
from tonedef.settings import settings


def test_compose_query_no_modifiers_returns_text() -> None:
    assert compose_query("Hendrix fuzz", []) == "Hendrix fuzz"


def test_compose_query_with_modifiers_appends() -> None:
    result = compose_query("Hendrix fuzz", ["grittier", "saggy", "roomy"])
    assert result == "Hendrix fuzz\n\nTonal modifiers: grittier, saggy, roomy"


def test_compose_query_single_modifier() -> None:
    result = compose_query("warm jazz", ["darker"])
    assert result == "warm jazz\n\nTonal modifiers: darker"


def test_generate_signal_chain_uses_rendered_prompt_and_shared_client(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_render_prompt(name: str, **context: object) -> str:
        assert name == "system_prompt"
        assert context == {"TAVILY_RESULTS": "No context retrieved."}
        return "rendered system"

    def fake_complete(messages: list[dict[str, str]], **kwargs: object) -> str:
        calls.append({"messages": messages, **kwargs})
        return "<signal_chain>ok</signal_chain>"

    monkeypatch.setattr(pipeline, "render_prompt", fake_render_prompt)
    monkeypatch.setattr(pipeline.llm_client, "complete", fake_complete)

    result = pipeline.generate_signal_chain("warm clean tone", model="test/model")

    assert result == "<signal_chain>ok</signal_chain>"
    assert calls == [
        {
            "messages": [
                {"role": "system", "content": "rendered system"},
                {"role": "user", "content": "warm clean tone"},
            ],
            "model": "test/model",
            "max_tokens": 2000,
            "temperature": settings.phase1_temperature,
        }
    ]
