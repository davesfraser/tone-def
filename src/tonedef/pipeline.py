# applied-skills: streamlit
"""Thin orchestration layer for the two-phase tone generation pipeline.

Phase 1: natural language query → signal chain recommendation (text).
Phase 2: signal chain recommendation → GR7 component list (JSON), handled
by :func:`tonedef.component_mapper.map_components`.
"""

from __future__ import annotations

import logging

import anthropic
from anthropic.types import TextBlock

from tonedef.prompts import SYSTEM_PROMPT
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
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Run Phase 1: convert a natural language tone query to a signal chain.

    Args:
        query: The user's tone description.
        client: An initialised Anthropic client.
        model: Anthropic model identifier.

    Returns:
        The raw Phase 1 signal chain text.
    """
    system = SYSTEM_PROMPT.replace("{{TAVILY_RESULTS}}", "No context retrieved.")

    _log.info("Phase 1 LLM call: model=%s, query_length=%d", model, len(query))
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=settings.phase1_temperature,
        system=system,
        messages=[{"role": "user", "content": query}],
    )
    _log.info(
        "Phase 1 complete: input_tokens=%s, output_tokens=%s",
        getattr(message.usage, "input_tokens", "?"),
        getattr(message.usage, "output_tokens", "?"),
    )

    block = message.content[0]
    if not isinstance(block, TextBlock) and not hasattr(block, "text"):
        msg = f"Expected TextBlock, got {type(block).__name__}"
        raise TypeError(msg)
    return block.text  # type: ignore[union-attr]
