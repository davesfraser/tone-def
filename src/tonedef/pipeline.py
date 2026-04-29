# applied-skills: streamlit
"""Thin orchestration layer for the two-phase tone generation pipeline.

Phase 1: natural language query → signal chain recommendation (text).
Phase 2: signal chain recommendation → GR7 component list (JSON), handled
by :func:`tonedef.component_mapper.map_components`.
"""

from __future__ import annotations

import logging

from tonedef import client as llm_client
from tonedef.prompt_templates import render_prompt
from tonedef.settings import settings

_log = logging.getLogger(__name__)


def compose_query(text: str, modifiers: list[str]) -> str:
    """Assemble a Phase 1 query from user text and tonal modifiers.

    Args:
        text: The user's tone description.
        modifiers: List of selected tonal descriptor terms (may be empty).

    Returns:
        Combined query string.  If *modifiers* is empty the original
        *text* is returned unchanged.
    """
    if not modifiers:
        return text
    modifier_str = ", ".join(modifiers)
    return f"{text}\n\nTonal modifiers: {modifier_str}"


def generate_signal_chain(
    query: str,
    model: str | None = None,
) -> str:
    """Run Phase 1: convert a natural language tone query to a signal chain.

    Args:
        query: The user's tone description.
        model: Provider/model identifier. Defaults to ``settings.default_model``.

    Returns:
        The raw Phase 1 signal chain text.
    """
    system = render_prompt("system_prompt", TAVILY_RESULTS="No context retrieved.")
    resolved_model = model or settings.default_model

    _log.info("Phase 1 LLM call: model=%s, query_length=%d", resolved_model, len(query))
    return llm_client.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        model=resolved_model,
        max_tokens=2000,
        temperature=settings.phase1_temperature,
    )
