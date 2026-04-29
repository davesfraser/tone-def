from __future__ import annotations

import pytest

from tonedef.prompt_templates import load_prompt_source, prompt_meta, render_prompt
from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT, SYSTEM_PROMPT


def test_prompt_constants_load_from_template_files() -> None:
    assert load_prompt_source("system_prompt") == SYSTEM_PROMPT
    assert load_prompt_source("exemplar_refinement_prompt") == EXEMPLAR_REFINEMENT_PROMPT


def test_prompt_sources_keep_existing_placeholders() -> None:
    assert "{{TAVILY_RESULTS}}" in SYSTEM_PROMPT
    assert "{{SIGNAL_CHAIN}}" in EXEMPLAR_REFINEMENT_PROMPT
    assert "{{COMPONENT_SCHEMA}}" in EXEMPLAR_REFINEMENT_PROMPT


def test_render_prompt_uses_strict_context() -> None:
    rendered = render_prompt("system_prompt", TAVILY_RESULTS="No context retrieved.")

    assert "No context retrieved." in rendered
    assert "{{TAVILY_RESULTS}}" not in rendered


def test_render_prompt_requires_context() -> None:
    with pytest.raises(Exception):  # noqa: B017 - Jinja raises a templating exception.
        render_prompt("system_prompt")


def test_render_exemplar_prompt_requires_all_context() -> None:
    with pytest.raises(Exception):  # noqa: B017 - Jinja raises a templating exception.
        render_prompt(
            "exemplar_refinement_prompt",
            SIGNAL_CHAIN="target",
            EXEMPLAR_PRESETS="exemplars",
        )


def test_prompt_meta_reads_header() -> None:
    meta = prompt_meta("system_prompt")

    assert meta.title == "ToneDef phase 1 system prompt"
    assert meta.version == "0.3.0"
    assert meta.eval_metric == "prompt_content_regression"
    assert meta.last_modified == "2026-04-29"
