from __future__ import annotations

from tonedef.settings import settings
from tonedef.tracing import trace_llm_call


def test_trace_llm_call_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trace_enabled", False)
    monkeypatch.setattr(settings, "trace_backend", "none")

    with trace_llm_call("test.trace", {"input": "value"}):
        marker = "ran"

    assert marker == "ran"


def test_trace_llm_call_tolerates_unknown_backend(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trace_enabled", True)
    monkeypatch.setattr(settings, "trace_backend", "unknown")

    with trace_llm_call("test.trace", {"input": "value"}):
        marker = "ran"

    assert marker == "ran"
