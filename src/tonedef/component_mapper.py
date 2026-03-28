"""
component_mapper.py
--------------------
Runtime module that maps a Phase 1 signal chain to Guitar Rig 7 components.

Exemplar-first architecture:
  1. Retrieve tonally-similar factory presets (exemplars) via ChromaDB
  2. Retrieve manual descriptions for exemplar components + missing categories
  3. Load amp-to-cabinet lookup for deterministic cabinet assignment
  4. Assemble EXEMPLAR_REFINEMENT_PROMPT with all context
  5. Call the Anthropic API (Phase 2 LLM call)
  6. Parse and validate the JSON response
  7. Fill defaults for any omitted parameters from the schema
  8. Enforce correct cabinet inserted after amp via amp-to-cabinet lookup
  9. Return an ordered list of component dicts ready for xml_builder
"""

from __future__ import annotations

import json
import logging
import re

import anthropic
from pydantic import ValidationError

from tonedef.exemplar_store import format_exemplar_context
from tonedef.models import ComponentOutput
from tonedef.paths import DATA_PROCESSED
from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT
from tonedef.retriever import (
    get_manual_chunks_for_components,
    search_exemplars,
    search_manual_for_categories,
)
from tonedef.settings import settings
from tonedef.signal_chain_parser import ParsedSignalChain, format_tonal_target

_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_AMP_CABINET_LOOKUP_PATH = DATA_PROCESSED / "amp_cabinet_lookup.json"

_MATCHED_CABINET_PRO_ID = 156000
_MATCHED_CABINET_PRO_NAME = "Matched Cabinet Pro"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_schema() -> dict:
    """Load component_schema.json as a dict keyed by component_name."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_amp_cabinet_lookup() -> dict[str, dict]:
    """Load amp_cabinet_lookup.json as a dict keyed by amp component name."""
    with open(_AMP_CABINET_LOOKUP_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Prompt context builders
# ---------------------------------------------------------------------------


def build_manual_reference_context(manual_results: list[dict]) -> str:
    """Format manual chunk descriptions for the prompt.

    Args:
        manual_results: List of dicts with component_name, category, text.

    Returns:
        Formatted string for {{MANUAL_REFERENCE}} injection.
    """
    if not manual_results:
        return "(no manual descriptions available)"
    sections = []
    seen: set[str] = set()
    for r in manual_results:
        name = r["component_name"]
        if name in seen:
            continue
        seen.add(name)
        category = r.get("category", "")
        text = r.get("text", "")
        trimmed = text[:600].rstrip()
        if len(text) > 600:
            trimmed += " ..."
        sections.append(f"[{name}] ({category})\n{trimmed}")
    return "\n\n".join(sections) if sections else "(no manual descriptions available)"


def build_component_schema_context(
    component_names: list[str],
    schema: dict,
) -> str:
    """Format parameter definitions for candidate components.

    Args:
        component_names: List of component names to include.
        schema: Parsed component_schema.json.

    Returns:
        Formatted string for {{COMPONENT_SCHEMA}} injection.
    """
    if not component_names:
        return "(no schema available)"
    sections = []
    for name in component_names:
        if name not in schema:
            continue
        entry = schema[name]
        lines = [f"[{name}] (component_id: {entry['component_id']})"]
        for param in entry.get("parameters", []):
            lines.append(
                f"  {param['param_id']} | {param['param_name']} | default: {param['default_value']}"
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "(no schema available)"


def build_cabinet_lookup_context(amp_cabinet_lookup: dict[str, dict]) -> str:
    """Format the amp-to-cabinet lookup table for the prompt.

    Args:
        amp_cabinet_lookup: Output of load_amp_cabinet_lookup().

    Returns:
        Pipe-delimited table for {{CABINET_LOOKUP}} injection.
    """
    lines = []
    for amp_name, entry in sorted(amp_cabinet_lookup.items()):
        cab_name = entry["cabinet_component_name"]
        cab_id = entry["cabinet_component_id"]
        cab_val = int(entry["cab_value"])
        lines.append(f"{amp_name} | {cab_name} | {cab_id} | {cab_val}")
    return "\n".join(lines) if lines else "(no cabinet lookup available)"


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _find_amp_name(components: list[dict], amp_cabinet_lookup: dict[str, dict]) -> str | None:
    """Return the amp component name from the component list, if any."""
    lookup_lower = {k.lower(): k for k in amp_cabinet_lookup}
    for comp in components:
        cname = comp.get("component_name", "")
        if cname.lower() in lookup_lower:
            return lookup_lower[cname.lower()]
    return None


def _find_amp_index(components: list[dict], amp_cabinet_lookup: dict[str, dict]) -> int | None:
    """Return the list index of the amp component, or None if absent."""
    lookup_lower = {k.lower() for k in amp_cabinet_lookup}
    for idx, comp in enumerate(components):
        if comp.get("component_name", "").lower() in lookup_lower:
            return idx
    return None


def _extract_exemplar_cabinet_params(
    exemplars: list[dict],
) -> dict[str, float | int] | None:
    """Extract cabinet parameters from the top exemplar's actual preset data.

    Searches the first exemplar's component list for a Matched Cabinet Pro
    entry and returns its parameter dict.  Falls back through subsequent
    exemplars if the first has no cabinet.

    Args:
        exemplars: Exemplar records from the store (each has a ``components``
            list with ``{component_name, component_id, parameters}`` dicts).

    Returns:
        Parameter dict ``{param_id: value}`` from the exemplar's cabinet,
        or ``None`` if none of the exemplars contain a Matched Cabinet Pro.
    """
    for ex in exemplars:
        for comp in ex.get("components", []):
            if comp.get("component_name") == _MATCHED_CABINET_PRO_NAME:
                return dict(comp.get("parameters", {}))
    return None


def _make_matched_cabinet_pro(
    amp_name: str | None,
    amp_cabinet_lookup: dict[str, dict],
    schema: dict,
    base_exemplar: str,
    exemplar_cabinet_params: dict[str, float | int] | None = None,
    llm_cabinet_params: dict[str, float | int] | None = None,
) -> dict:
    """Build a Matched Cabinet Pro with three-tier parameter layering.

    Priority (highest wins):
      1. Cab — always from amp_cabinet_lookup (deterministic).
      2. LLM explicit — params the LLM set on its emitted cabinet,
         reflecting tonal-target decisions (e.g. more room for airy tones).
      3. Exemplar factory data — proven-good values from the base preset.
      4. Schema defaults — fallback for anything still missing.

    Args:
        amp_name: Amp component name from the lookup (or None).
        amp_cabinet_lookup: The amp-to-cabinet lookup table.
        schema: Parsed component_schema.json.
        base_exemplar: Name of the base exemplar preset.
        exemplar_cabinet_params: Parameter dict from the exemplar store's
            actual factory preset data.  Provides sensible base values
            for Volume, X-Fade etc. when the LLM omits them.
        llm_cabinet_params: Parameter dict the LLM explicitly emitted
            (extracted *before* fill_defaults).  These reflect tonal-target
            decisions and take priority over exemplar values.  Cab is always
            overridden by the lookup.

    Returns:
        Component dict for Matched Cabinet Pro.
    """
    # Layer 4: schema defaults
    params: dict[str, float | int] = {
        p["param_id"]: p["default_value"]
        for p in schema.get(_MATCHED_CABINET_PRO_NAME, {}).get("parameters", [])
    }
    # Layer 3: exemplar factory data
    if exemplar_cabinet_params:
        params.update(exemplar_cabinet_params)
    # Layer 2: LLM explicit choices (tonal-target informed)
    if llm_cabinet_params:
        params.update(llm_cabinet_params)
    # Layer 1: deterministic Cab from lookup (always wins)
    if amp_name and amp_name in amp_cabinet_lookup:
        params["Cab"] = int(amp_cabinet_lookup[amp_name]["cab_value"])

    return {
        "component_name": _MATCHED_CABINET_PRO_NAME,
        "component_id": _MATCHED_CABINET_PRO_ID,
        "base_exemplar": base_exemplar,
        "modification": "adjusted",
        "confidence": "documented",
        "parameters": params,
    }


def _is_integer_param(param_entry: dict) -> bool:
    """Detect integer-valued params from schema stats.

    A parameter is integer-valued when its default, observed min, and
    observed max are all whole numbers (e.g. cabinet selectors, mode
    switches, step counts, ratio selectors).
    """
    default = param_entry.get("default_value", 0.0)
    stats = param_entry.get("stats", {})
    lo = stats.get("min", 0.0)
    hi = stats.get("max", 0.0)
    return float(default) == int(default) and float(lo) == int(lo) and float(hi) == int(hi)


def fill_defaults(components: list[dict], schema: dict) -> list[dict]:
    """
    Ensure every parameter in the schema is present in each component's
    parameter dict. Missing parameters are filled with their default_value.

    Values are clamped to the observed [min, max] range from the schema.
    Integer-valued parameters (detected from schema stats) are preserved
    as ``int`` so that the XML builder writes them as bare integers,
    matching the factory preset format.

    Args:
        components: Component list from the LLM response.
        schema: Parsed component_schema.json.

    Returns:
        Component list with complete, range-checked parameter dicts.
    """
    for comp in components:
        comp_name = comp.get("component_name", "")
        params = comp.get("parameters", {})
        if comp_name in schema:
            for param_entry in schema[comp_name].get("parameters", []):
                pid = param_entry["param_id"]
                is_int = _is_integer_param(param_entry)
                stats = param_entry.get("stats", {})
                lo = stats.get("min", 0.0)
                hi = stats.get("max", 1.0)

                if pid not in params:
                    default = param_entry["default_value"]
                    params[pid] = int(default) if is_int else default
                else:
                    val = float(params[pid])
                    val = max(lo, min(hi, val))
                    params[pid] = int(val) if is_int else val
        comp["parameters"] = params
    return components


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def map_components(
    signal_chain: str,
    parsed: ParsedSignalChain,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """
    Map a Phase 1 signal chain to an ordered list of GR7 component dicts.

    Exemplar-first pipeline:
      1. Retrieve top-5 tonally similar factory presets
      2. Gather manual descriptions for exemplar components
      3. Retrieve manual descriptions for effect categories the exemplars lack
      4. Build prompt with exemplars, manual reference, schema, cabinet lookup
      5. Call the LLM with EXEMPLAR_REFINEMENT_PROMPT (compact tonal target)
      6. Parse JSON response, fill defaults, enforce cabinet

    Args:
        signal_chain: The raw Phase 1 signal chain text (used for ChromaDB
            manual retrieval where the verbose text aids embedding similarity).
        parsed: The structured Phase 1 output.  Tags and component names are
            extracted directly for exemplar scoring, and a compact tonal
            target is rendered for the Phase 2 prompt.
        client: An initialised anthropic.Anthropic client.
        model: Anthropic model identifier.

    Returns:
        Ordered list of component dicts, each with:
            component_name, component_id, base_exemplar,
            modification, confidence, parameters.

    Raises:
        ValueError: If the LLM response cannot be parsed as a JSON array.
    """
    schema = load_schema()
    amp_cabinet_lookup = load_amp_cabinet_lookup()

    # Pre-extract tags and component names from the already-parsed output
    pre_tags = parsed.tags_characters + parsed.tags_genres
    pre_components = [unit.name for section in parsed.sections for unit in section.units]

    # 1. Retrieve exemplars (structured scoring, no re-parsing needed)
    exemplars = search_exemplars(signal_chain, tags=pre_tags, components=pre_components)
    exemplar_context = format_exemplar_context(exemplars)

    # 2. Gather component names across all exemplars
    exemplar_component_names: set[str] = set()
    for ex in exemplars:
        for comp in ex.get("components", []):
            exemplar_component_names.add(comp["component_name"])

    # 3. Manual descriptions for exemplar components
    manual_for_exemplars = get_manual_chunks_for_components(exemplar_component_names)

    # 4. Manual descriptions for categories the exemplars may lack
    manual_for_additions = search_manual_for_categories(
        signal_chain, exclude_names=exemplar_component_names
    )

    # 5. Combine manual results
    all_manual = manual_for_exemplars + manual_for_additions

    # 6. Collect all component names that need schema entries
    all_component_names = list(
        exemplar_component_names
        | {r["component_name"] for r in manual_for_additions}
        | {_MATCHED_CABINET_PRO_NAME}
    )

    # 7. Build prompt — inject compact tonal target instead of raw text
    tonal_target = format_tonal_target(parsed)
    manual_context = build_manual_reference_context(all_manual)
    schema_context = build_component_schema_context(all_component_names, schema)
    cabinet_context = build_cabinet_lookup_context(amp_cabinet_lookup)

    prompt = (
        EXEMPLAR_REFINEMENT_PROMPT.replace("{{SIGNAL_CHAIN}}", tonal_target)
        .replace("{{EXEMPLAR_PRESETS}}", exemplar_context)
        .replace("{{MANUAL_REFERENCE}}", manual_context)
        .replace("{{COMPONENT_SCHEMA}}", schema_context)
        .replace("{{CABINET_LOOKUP}}", cabinet_context)
    )

    # 8. Phase 2 LLM call
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=settings.phase2_temperature,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if the model added them despite instructions
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    # Extract the JSON array even if the model prefixed it with reasoning prose.
    # Match '[ {' for the start and the last '} ]' for the end, tolerating whitespace.
    arr_start = re.search(r"\[\s*\{", raw)
    _arr_end = None
    for _arr_end in re.finditer(r"\}\s*\]", raw):
        pass  # advance to the last match
    if arr_start and _arr_end:
        raw = raw[arr_start.start() : _arr_end.end()]

    try:
        raw_list: list[dict] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Phase 2 LLM returned non-JSON response: {exc}\n\n{raw}") from exc

    if not isinstance(raw_list, list):
        raise ValueError(f"Phase 2 LLM returned non-array JSON: {type(raw_list)}")

    # Validate each component through Pydantic — catches bad enums,
    # missing fields, and coerces list-form parameters to dicts.
    _log = logging.getLogger(__name__)
    validated: list[ComponentOutput] = []
    for i, item in enumerate(raw_list):
        try:
            validated.append(ComponentOutput.model_validate(item))
        except ValidationError as exc:
            _log.warning("Phase 2 component %d failed validation: %s", i, exc)
            # Fall through — keep the raw dict so downstream still works

    # Use validated dicts where possible, fall back to raw dicts for
    # components that failed Pydantic validation.
    components: list[dict] = (
        [v.model_dump() for v in validated] if len(validated) == len(raw_list) else raw_list
    )

    # 9a. Extract LLM cabinet params BEFORE fill_defaults so we can
    # distinguish explicit LLM choices from schema-default backfills.
    llm_cab_params: dict[str, float | int] | None = None
    for c in components:
        if "cabinet" in c.get("component_name", "").lower():
            llm_cab_params = c.get("parameters", {})
            break

    components = fill_defaults(components, schema)

    # 9b. Enforce cabinet — three-tier param layering:
    #   schema defaults → exemplar factory data → LLM explicit → Cab lookup
    base_exemplar = components[0].get("base_exemplar", "") if components else ""
    exemplar_cab_params = _extract_exemplar_cabinet_params(exemplars)
    components = [c for c in components if "cabinet" not in c.get("component_name", "").lower()]
    amp_name = _find_amp_name(components, amp_cabinet_lookup)
    cabinet = _make_matched_cabinet_pro(
        amp_name,
        amp_cabinet_lookup,
        schema,
        base_exemplar,
        exemplar_cab_params,
        llm_cab_params,
    )
    amp_idx = _find_amp_index(components, amp_cabinet_lookup)
    if amp_idx is not None:
        components.insert(amp_idx + 1, cabinet)
    else:
        components.append(cabinet)

    return components
