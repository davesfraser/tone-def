"""
component_mapper.py
--------------------
Runtime module that maps a Phase 1 signal chain to Guitar Rig 7 components.

Exemplar-first architecture:
  1. Retrieve tonally-similar factory presets (exemplars) via the exemplar
     store (structured scoring)
  2. Retrieve manual descriptions for exemplar components + missing categories
  3. Load amp-to-cabinet lookup for cabinet reference
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

from tonedef.crp_lookup import format_crp_reference
from tonedef.exemplar_store import format_exemplar_context
from tonedef.models import ComponentOutput
from tonedef.paths import DATA_PROCESSED
from tonedef.prompts import EXEMPLAR_REFINEMENT_PROMPT
from tonedef.retriever import (
    get_manual_chunks_for_components,
    search_exemplars,
    search_manual_by_tonal_target,
    search_manual_for_categories,
)
from tonedef.settings import settings
from tonedef.signal_chain_parser import ParsedSignalChain, format_tonal_target
from tonedef.tonal_vocab import format_tonal_descriptors

_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_AMP_CABINET_LOOKUP_PATH = DATA_PROCESSED / "amp_cabinet_lookup.json"
_ANNOTATIONS_PATH = DATA_PROCESSED / "parameter_annotations.json"

_MATCHED_CABINET_PRO_ID = 156000
_MATCHED_CABINET_PRO_NAME = "Matched Cabinet Pro"

# Cabinet-type components that replace Matched Cabinet Pro in the chain.
# When ANY of these are present, Matched Cabinet Pro enforcement is skipped.
_CONTROL_ROOM_NAMES: frozenset[str] = frozenset(
    {
        "Control Room",
        "Control Room Pro",
    }
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_schema() -> dict:
    """Load component_schema.json as a dict keyed by component_name."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_amp_cabinet_lookup() -> dict[str, dict]:
    """Load amp_cabinet_lookup.json and return the amp entries dict.

    The JSON has top-level ``cabinet_component_name`` and
    ``cabinet_component_id`` metadata plus an ``amps`` mapping of
    amp name → ``{cab_value}``.  This function returns only the
    ``amps`` dict for backward-compatible keyed access.
    """
    with open(_AMP_CABINET_LOOKUP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("amps", data)


def load_annotations() -> dict[str, dict[str, dict]]:
    """Load parameter_annotations.json as a nested dict.

    Returns:
        ``{component_name: {param_id: {param_name, description?, boundary?, ...}}}``.
        Returns an empty dict if the file does not exist (graceful fallback).
    """
    if not _ANNOTATIONS_PATH.exists():
        return {}
    with open(_ANNOTATIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Prompt context builders
# ---------------------------------------------------------------------------


def _format_manual_section(manual_results: list[dict]) -> str:
    """Format a list of manual chunks into deduplicated text blocks.

    Full component text is included — manual chunks are already scoped
    per component and the Phase 2 context window can accommodate them.

    Args:
        manual_results: List of dicts with component_name, category, text.

    Returns:
        Formatted text, or empty string if no results.
    """
    sections: list[str] = []
    seen: set[str] = set()
    for r in manual_results:
        name = r["component_name"]
        if name in seen:
            continue
        seen.add(name)
        category = r.get("category", "")
        text = r.get("text", "")
        sections.append(f"[{name}] ({category})\n{text}")
    return "\n\n".join(sections)


def build_manual_reference_context(
    exemplar_chunks: list[dict],
    tonal_chunks: list[dict] | None = None,
    gap_chunks: list[dict] | None = None,
) -> str:
    """Format manual chunks into three labelled sections for the prompt.

    Args:
        exemplar_chunks: Manual docs for components in the exemplar presets.
        tonal_chunks: Manual docs for tonally relevant swap candidates.
        gap_chunks: Manual docs for gap-filling components from missing
            categories.

    Returns:
        Formatted string for ``{{MANUAL_REFERENCE}}`` injection with
        three clearly labelled sections.
    """
    parts: list[str] = []

    ex_text = _format_manual_section(exemplar_chunks)
    if ex_text:
        parts.append(f"--- COMPONENTS FROM EXEMPLARS ---\n{ex_text}")

    if tonal_chunks:
        tonal_text = _format_manual_section(tonal_chunks)
        if tonal_text:
            parts.append(f"--- TONALLY RELEVANT ALTERNATIVES ---\n{tonal_text}")

    if gap_chunks:
        gap_text = _format_manual_section(gap_chunks)
        if gap_text:
            parts.append(f"--- GAP-FILLING CANDIDATES ---\n{gap_text}")

    return "\n\n".join(parts) if parts else "(no manual descriptions available)"


def build_component_schema_context(
    component_names: list[str],
    schema: dict,
    annotations: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Format parameter definitions for candidate components.

    Each parameter line includes observed factory-preset stats and, when
    available, a brief description and boundary note from the parameter
    annotations.  This gives the Phase 2 LLM awareness of real-world
    ranges and critical off-boundary semantics (e.g. ``0.0 = filter off``).

    Args:
        component_names: List of component names to include.
        schema: Parsed component_schema.json.
        annotations: Output of :func:`load_annotations`.  ``None`` is
            treated as empty (graceful fallback).

    Returns:
        Formatted string for ``{{COMPONENT_SCHEMA}}`` injection.
    """
    if not component_names:
        return "(no schema available)"
    if annotations is None:
        annotations = {}

    sections = []
    for name in component_names:
        if name not in schema:
            continue
        entry = schema[name]
        lines = [f"[{name}] (component_id: {entry['component_id']})"]
        comp_anns = annotations.get(name, {})
        for param in entry.get("parameters", []):
            pid = param["param_id"]
            pname = param["param_name"]
            default = param["default_value"]
            stats = param.get("stats", {})
            lo = stats.get("min", 0.0)
            hi = stats.get("max", 1.0)
            median = stats.get("median", default)

            line = (
                f"  {pid} | {pname} | default: {default} | range: [{lo}, {hi}] | median: {median}"
            )

            ann = comp_anns.get(pid, {})
            suffix_parts: list[str] = []
            if "description" in ann:
                suffix_parts.append(ann["description"])
            if "boundary" in ann:
                suffix_parts.append(ann["boundary"])
            if suffix_parts:
                line += " | " + "; ".join(suffix_parts)

            lines.append(line)
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
        cab_val = int(entry["cab_value"])
        lines.append(
            f"{amp_name} | {_MATCHED_CABINET_PRO_NAME} | {_MATCHED_CABINET_PRO_ID} | {cab_val}"
        )
    return "\n".join(lines) if lines else "(no cabinet lookup available)"


# CRP integer-enum parameter IDs that must not be clamped to [0, 1].
_CRP_INTEGER_PARAMS: frozenset[str] = frozenset(
    {f"{prefix}{i}" for prefix in ("Cab", "Mic", "MPos") for i in range(1, 9)}
)

# Valid ranges for CRP cabinet/mic/position integer enums.
_CRP_CAB_MAX = 30
_CRP_MIC_MAX = 4
_CRP_MPOS_MAX = 2


def build_crp_reference_context() -> str:
    """Return CRP enum tables for Phase 2 prompt injection.

    Always returns the full tables so the LLM can choose Control Room Pro
    or Matched Cabinet Pro based on the tonal context rather than a
    prescriptive chain type.

    Returns:
        Formatted CRP enum tables.
    """
    return format_crp_reference()


def _validate_crp_params(components: list[dict]) -> None:
    """Log warnings for missing or out-of-range CRP Cab1/Mic1/MPos1 values.

    Does NOT override the LLM's choices — it selected them based on the
    tonal target's named cabinet and microphone suggestions.  This is a
    diagnostic safety net only.
    """
    _log = logging.getLogger(__name__)
    for comp in components:
        if comp.get("component_name") not in _CONTROL_ROOM_NAMES:
            continue
        params = comp.get("parameters", {})

        cab1 = params.get("Cab1")
        if cab1 is None:
            _log.warning("Control Room Pro missing Cab1 — cabinet selection may be wrong")
        elif not (0 <= int(cab1) <= _CRP_CAB_MAX):
            _log.warning("Control Room Pro Cab1=%s out of range 0-%d", cab1, _CRP_CAB_MAX)

        mic1 = params.get("Mic1")
        if mic1 is None:
            _log.warning("Control Room Pro missing Mic1 — microphone selection may be wrong")
        elif not (0 <= int(mic1) <= _CRP_MIC_MAX):
            _log.warning("Control Room Pro Mic1=%s out of range 0-%d", mic1, _CRP_MIC_MAX)

        mpos1 = params.get("MPos1")
        if mpos1 is None:
            _log.warning("Control Room Pro missing MPos1 — mic position may be wrong")
        elif not (0 <= int(mpos1) <= _CRP_MPOS_MAX):
            _log.warning("Control Room Pro MPos1=%s out of range 0-%d", mpos1, _CRP_MPOS_MAX)

        # Cast float → int for integer enum params
        for key in list(params):
            if key in _CRP_INTEGER_PARAMS and isinstance(params[key], float):
                params[key] = int(params[key])


def _validate_mcp_params(
    components: list[dict],
    amp_cabinet_lookup: dict[str, dict],
) -> None:
    """Log warnings for MCP Cab values that diverge from the reference lookup.

    Mirrors :func:`_validate_crp_params` — diagnostic only, does NOT
    override the LLM's choices.  Also casts Cab from float to int.
    """
    _log = logging.getLogger(__name__)
    amp_name = _find_amp_name(components, amp_cabinet_lookup)
    for comp in components:
        if comp.get("component_name") != _MATCHED_CABINET_PRO_NAME:
            continue
        params = comp.get("parameters", {})
        cab = params.get("Cab")
        if cab is not None:
            if isinstance(cab, float):
                params["Cab"] = int(cab)
                cab = params["Cab"]
            if amp_name and amp_name in amp_cabinet_lookup:
                expected = int(amp_cabinet_lookup[amp_name]["cab_value"])
                if int(cab) != expected:
                    _log.warning(
                        "Matched Cabinet Pro Cab=%s differs from reference %s for %s",
                        cab,
                        expected,
                        amp_name,
                    )


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _has_control_room(components: list[dict]) -> bool:
    """Return True if any component is a Control Room variant."""
    return any(c.get("component_name", "") in _CONTROL_ROOM_NAMES for c in components)


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
      1. LLM explicit — params the LLM set on its emitted cabinet,
         reflecting tonal-target decisions (e.g. more room for airy tones).
      2. Exemplar factory data — proven-good values from the base preset.
      3. Schema defaults — fallback for anything still missing.

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
            decisions and take priority over exemplar values.

    Returns:
        Component dict for Matched Cabinet Pro.
    """
    # Layer 3: schema defaults
    params: dict[str, float | int] = {
        p["param_id"]: p["default_value"]
        for p in schema.get(_MATCHED_CABINET_PRO_NAME, {}).get("parameters", [])
    }
    # Layer 2: exemplar factory data
    if exemplar_cabinet_params:
        params.update(exemplar_cabinet_params)
    # Layer 1: LLM explicit choices (tonal-target informed)
    if llm_cabinet_params:
        params.update(llm_cabinet_params)

    return {
        "component_name": _MATCHED_CABINET_PRO_NAME,
        "component_id": _MATCHED_CABINET_PRO_ID,
        "base_exemplar": base_exemplar,
        "modification": "adjusted",
        "confidence": "documented",
        "rationale": "Cabinet matched to the selected amp based on tonal target and reference data.",
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
) -> tuple[list[dict], list[dict]]:
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
        Tuple of (components, exemplars):
            components: Ordered list of component dicts, each with
                component_name, component_id, base_exemplar,
                modification, confidence, parameters.
            exemplars: List of exemplar dicts retrieved for this query.

    Raises:
        ValueError: If the LLM response cannot be parsed as a JSON array.
    """
    schema = load_schema()
    amp_cabinet_lookup = load_amp_cabinet_lookup()
    annotations = load_annotations()

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

    # 4b. Tonal similarity search — swap candidates across all categories
    manual_for_tonal = search_manual_by_tonal_target(
        signal_chain,
        top_n=5,
        exclude_names=exemplar_component_names,
    )

    # 5. Collect all component names that need schema entries
    all_component_names = list(
        exemplar_component_names
        | {r["component_name"] for r in manual_for_additions}
        | {r["component_name"] for r in manual_for_tonal}
        | {_MATCHED_CABINET_PRO_NAME}
        | _CONTROL_ROOM_NAMES
    )

    # 6. Build prompt — inject compact tonal target instead of raw text
    tonal_target = format_tonal_target(parsed)
    manual_context = build_manual_reference_context(
        exemplar_chunks=manual_for_exemplars,
        tonal_chunks=manual_for_tonal,
        gap_chunks=manual_for_additions,
    )
    schema_context = build_component_schema_context(all_component_names, schema, annotations)
    cabinet_context = build_cabinet_lookup_context(amp_cabinet_lookup)
    crp_context = build_crp_reference_context()
    tonal_descriptor_context = format_tonal_descriptors()

    prompt = (
        EXEMPLAR_REFINEMENT_PROMPT.replace("{{SIGNAL_CHAIN}}", tonal_target)
        .replace("{{EXEMPLAR_PRESETS}}", exemplar_context)
        .replace("{{MANUAL_REFERENCE}}", manual_context)
        .replace("{{COMPONENT_SCHEMA}}", schema_context)
        .replace("{{CABINET_LOOKUP}}", cabinet_context)
        .replace("{{CRP_REFERENCE}}", crp_context)
        .replace("{{TONAL_DESCRIPTORS}}", tonal_descriptor_context)
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

    # 9b. Cabinet handling.
    # Respect the LLM's cabinet choice:
    #   - If CRP is present → validate CRP params (integer enums).
    #   - If Matched Cabinet Pro is present (no CRP) → validate MCP params.
    #   - If neither → inject Matched Cabinet Pro as a safety fallback,
    #     then validate.
    has_crp = _has_control_room(components)
    has_mcp = any(c.get("component_name", "") == _MATCHED_CABINET_PRO_NAME for c in components)

    if has_crp:
        # CRP is present — validate Cab1/Mic1/MPos1 and cast to int.
        # Strip any MCP the LLM may have emitted alongside CRP.
        components = [
            c for c in components if c.get("component_name", "") != _MATCHED_CABINET_PRO_NAME
        ]
        _validate_crp_params(components)
    elif has_mcp:
        # LLM emitted MCP — validate Cab against reference but don't override.
        _validate_mcp_params(components, amp_cabinet_lookup)
    else:
        # No cabinet solution at all — inject Matched Cabinet Pro as fallback.
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
        _validate_mcp_params(components, amp_cabinet_lookup)

    return components, exemplars
