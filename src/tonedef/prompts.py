# NOTE: The MODIFIER MAPPING inside <sonic_analysis> (~lines 30-78 of this
# string) mirrors the zone/group structure in tonal_descriptors.json.
# Phase 1 uses it as a conceptual taxonomy (which zone does this modifier
# target?); Phase 2 injects numeric parameter deltas dynamically via
# tonal_vocab.format_tonal_descriptors().  The two serve different purposes
# and don't need term-level parity, but if the zone/group *structure*
# changes in the JSON, review the MODIFIER MAPPING here too.
# See also: tonal_vocab.py

from __future__ import annotations

from tonedef.prompt_templates import load_prompt_source

SYSTEM_PROMPT = load_prompt_source("system_prompt")
EXEMPLAR_REFINEMENT_PROMPT = load_prompt_source("exemplar_refinement_prompt")
