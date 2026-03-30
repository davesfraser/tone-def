"""Tests for tonedef.prompts -- prompt content assertions."""

from __future__ import annotations

from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT, SYSTEM_PROMPT

# -------------------------------------------------------------------
# SYSTEM_PROMPT modifier mapping
# -------------------------------------------------------------------


def test_modifier_mapping_mentions_mcp_for_mic_placement() -> None:
    assert "Matched Cabinet Pro" in SYSTEM_PROMPT
    assert "X-Fade" in SYSTEM_PROMPT


def test_modifier_mapping_mentions_crp_for_full_production() -> None:
    assert "Control Room Pro" in SYSTEM_PROMPT


# -------------------------------------------------------------------
# EXEMPLAR_REFINEMENT_PROMPT constraints
# -------------------------------------------------------------------


def test_constraints_mention_crp_integer_enums() -> None:
    assert "Cab1" in EXEMPLAR_REFINEMENT_PROMPT
    assert "Mic1" in EXEMPLAR_REFINEMENT_PROMPT
    assert "MPos1" in EXEMPLAR_REFINEMENT_PROMPT


def test_constraints_mention_level_fader_note() -> None:
    """g1-g8 bridge note explains they are level faders, not gain."""
    assert "NOT gain boosts" in EXEMPLAR_REFINEMENT_PROMPT


# -------------------------------------------------------------------
# CRP example includes room params
# -------------------------------------------------------------------


def test_crp_example_includes_room_params() -> None:
    assert '"r1": 0.25' in EXEMPLAR_REFINEMENT_PROMPT
    assert '"a": 0.15' in EXEMPLAR_REFINEMENT_PROMPT
    assert '"b": 0.5' in EXEMPLAR_REFINEMENT_PROMPT
    assert '"t": 0.5' in EXEMPLAR_REFINEMENT_PROMPT
    assert '"st": 1.0' in EXEMPLAR_REFINEMENT_PROMPT


def test_crp_example_g1_is_strong_level() -> None:
    assert '"g1": 0.85' in EXEMPLAR_REFINEMENT_PROMPT


# -------------------------------------------------------------------
# MCP example annotation explains c parameter
# -------------------------------------------------------------------


def test_mcp_example_annotation_explains_xfade() -> None:
    assert "c=0.2" in EXEMPLAR_REFINEMENT_PROMPT
    assert "mic slightly back" in EXEMPLAR_REFINEMENT_PROMPT


# -------------------------------------------------------------------
# Output schema includes rationale field
# -------------------------------------------------------------------


def test_output_schema_includes_rationale() -> None:
    assert '"rationale"' in EXEMPLAR_REFINEMENT_PROMPT


def test_examples_include_rationale() -> None:
    """Both examples in the prompt must contain rationale fields."""
    # Count occurrences of "rationale" in the examples section
    examples_start = EXEMPLAR_REFINEMENT_PROMPT.index("<examples>")
    examples_section = EXEMPLAR_REFINEMENT_PROMPT[examples_start:]
    assert examples_section.count('"rationale"') >= 2


# -------------------------------------------------------------------
# Output schema includes description field
# -------------------------------------------------------------------


def test_output_schema_includes_description() -> None:
    assert '"description"' in EXEMPLAR_REFINEMENT_PROMPT


def test_examples_include_description() -> None:
    """Both examples in the prompt must contain description fields."""
    examples_start = EXEMPLAR_REFINEMENT_PROMPT.index("<examples>")
    examples_section = EXEMPLAR_REFINEMENT_PROMPT[examples_start:]
    assert examples_section.count('"description"') >= 2
