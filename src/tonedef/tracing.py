from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from tonedef.settings import settings


@contextmanager
def trace_llm_call(name: str, payload: Mapping[str, Any]) -> Iterator[None]:
    """Trace an LLM call when an optional observability backend is configured."""
    if not settings.trace_enabled or settings.trace_backend == "none":
        yield
        return

    if settings.trace_backend == "langfuse":
        try:
            from langfuse import get_client

            client = get_client()
            with client.start_as_current_span(name=name) as span:
                span.update(input=dict(payload))
                yield
                return
        except Exception:
            yield
            return

    if settings.trace_backend == "logfire":
        try:
            import logfire

            with logfire.span(name):
                yield
                return
        except Exception:
            yield
            return

    _ = name, payload
    yield
