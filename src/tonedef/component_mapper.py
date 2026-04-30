"""
component_mapper.py
--------------------
Runtime module that maps a Phase 1 signal chain to Guitar Rig 7 components.

Exemplar-first architecture:
  1. Retrieve tonally-similar factory presets (exemplars) via the exemplar
     store (structured scoring)
  2. Retrieve manual descriptions for exemplar components + missing categories
  3. Load amp-to-cabinet lookup for cabinet reference
  4. Render the exemplar refinement prompt with all context
  5. Call the shared LiteLLM client (Phase 2 LLM call)
  6. Parse and validate the JSON response
  7. Fill defaults for any omitted parameters from the schema
  8. Enforce correct cabinet inserted after amp via amp-to-cabinet lookup
  9. Return an ordered list of component dicts ready for xml_builder
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from tonedef import client as llm_client
from tonedef.crp_lookup import format_crp_reference
from tonedef.exemplar_store import format_exemplar_context
from tonedef.llm_usage import LLMContextBlockMetric, record_context_block
from tonedef.paths import DATA_PROCESSED
from tonedef.prompt_templates import render_prompt
from tonedef.retriever import (
    get_manual_chunks_for_components,
    search_exemplars,
    search_manual_by_tonal_target,
    search_manual_for_categories,
)
from tonedef.schemas import ComponentOutput
from tonedef.settings import settings
from tonedef.signal_chain_parser import ParsedSignalChain, format_tonal_target
from tonedef.tonal_vocab import format_tonal_descriptors

_log = logging.getLogger(__name__)

_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_AMP_CABINET_LOOKUP_PATH = DATA_PROCESSED / "amp_cabinet_lookup.json"
_ANNOTATIONS_PATH = DATA_PROCESSED / "parameter_annotations.json"

_MATCHED_CABINET_PRO_ID = 156000
_MATCHED_CABINET_PRO_NAME = "Matched Cabinet Pro"
_PHASE2_CONTEXT_OPERATION = "llm.phase2_context"
_PHASE2_TOKEN_CHAR_DIVISOR = 4
_MANUAL_COMPONENT_CHAR_LIMIT = 1600
_MANUAL_SECTION_CHAR_BUDGETS = {
    "exemplar": 12000,
    "tonal": 8000,
    "gap": 6000,
}
_GAP_SCHEMA_PER_CATEGORY = 1

# Cabinet-type components that replace Matched Cabinet Pro in the chain.
# When ANY of these are present, Matched Cabinet Pro enforcement is skipped.
_CONTROL_ROOM_NAMES: frozenset[str] = frozenset(
    {
        "Control Room",
        "Control Room Pro",
    }
)


# ---------------------------------------------------------------------------
# Component name resolution
# ---------------------------------------------------------------------------

# Manual-to-schema aliases for structural renames that normalisation alone
# cannot resolve (abbreviations, added/dropped suffixes, etc.).
_NAME_ALIASES: dict[str, str] = {
    "equalizergraphic": "EQ Graphic",
    "equalizerparametric": "EQ Parametric",
    "equalizershelving": "EQ Shelving",
    "demondistortion": "Demon",
    "volume": "Volume Pedal",
    "flangerchorus": "Flanger",
}

# Schema names whose manual headings differ enough that exact retrieval misses
# them.  The prompt still shows canonical schema names after retrieval.
_SCHEMA_TO_MANUAL_NAMES: dict[str, str] = {
    "Wahwah": "Wah Wah",
}


def _normalize_name(name: str) -> str:
    """Lowercase and strip spaces, hyphens, and apostrophes."""
    return re.sub(r"[\s\-']", "", name).lower()


def build_name_lookup(schema: dict) -> dict[str, str]:
    """Build a normalised-key → canonical-name lookup from schema keys."""
    lookup: dict[str, str] = {}
    for canonical in schema:
        lookup[_normalize_name(canonical)] = canonical
    # Layer aliases on top (aliases win when there's a conflict)
    lookup.update(_NAME_ALIASES)
    return lookup


def resolve_component_names(
    components: list[dict],
    lookup: dict[str, str],
) -> list[dict]:
    """Replace each component_name with its canonical schema name if found."""
    for comp in components:
        raw_name = comp.get("component_name", "")
        canonical = lookup.get(_normalize_name(raw_name))
        if canonical and canonical != raw_name:
            _log.info("Resolved component name %r → %r", raw_name, canonical)
            comp["component_name"] = canonical
    return components


def _schema_id_lookup(schema: dict) -> dict[int, str | None]:
    """Return component_id -> canonical name when the id is unique."""
    by_id: dict[int, str | None] = {}
    for name, entry in schema.items():
        component_id = entry.get("component_id")
        if not isinstance(component_id, int):
            continue
        if component_id in by_id:
            by_id[component_id] = None
        else:
            by_id[component_id] = name
    return by_id


def _known_param_ids(schema: dict, component_name: str) -> set[str]:
    entry = schema.get(component_name, {})
    return {str(p["param_id"]) for p in entry.get("parameters", [])}


def repair_component_identities(components: list[dict], schema: dict) -> list[dict]:
    """Repair unambiguous name/id/parameter drift in LLM component output.

    This is intentionally conservative: a component is renamed only when its
    emitted id uniquely identifies a schema component and the supplied parameter
    ids match that id's component better than the emitted component name.
    """
    id_lookup = _schema_id_lookup(schema)

    for comp in components:
        raw_id = comp.get("component_id")
        if not isinstance(raw_id, int):
            continue

        target_name = id_lookup.get(raw_id)
        current_name = str(comp.get("component_name", ""))
        if not target_name or target_name == current_name:
            continue

        param_ids = {str(pid) for pid in comp.get("parameters", {})}
        if not param_ids:
            continue

        target_score = len(param_ids & _known_param_ids(schema, target_name))
        current_score = len(param_ids & _known_param_ids(schema, current_name))
        if target_score > current_score and target_score > 0:
            _log.warning(
                "Repairing component identity %r/%s -> %r based on parameter ids",
                current_name,
                raw_id,
                target_name,
            )
            comp["component_name"] = target_name

    return components


def _expand_manual_lookup_names(component_names: set[str]) -> set[str]:
    """Include known manual headings alongside canonical schema names."""
    expanded = set(component_names)
    for name in component_names:
        alias = _SCHEMA_TO_MANUAL_NAMES.get(name)
        if alias:
            expanded.add(alias)
    return expanded


def _canonicalize_manual_chunk_names(chunks: list[dict], lookup: dict[str, str]) -> list[dict]:
    """Rewrite manual chunk names to canonical schema names when possible."""
    canonicalized: list[dict] = []
    for chunk in chunks:
        row = dict(chunk)
        raw_name = str(row.get("component_name", ""))
        canonical = lookup.get(_normalize_name(raw_name))
        if canonical:
            row["component_name"] = canonical
        canonicalized.append(row)
    return canonicalized


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_schema() -> dict:
    """Load component_schema.json as a dict keyed by component_name."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)
    return data


def load_amp_cabinet_lookup() -> dict[str, dict]:
    """Load amp_cabinet_lookup.json and return the amp entries dict.

    The JSON has top-level ``cabinet_component_name`` and
    ``cabinet_component_id`` metadata plus an ``amps`` mapping of
    amp name → ``{cab_value}``.  This function returns only the
    ``amps`` dict for backward-compatible keyed access.
    """
    with open(_AMP_CABINET_LOOKUP_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)
    result: dict[str, dict] = data.get("amps", data)
    return result


def load_annotations() -> dict[str, dict[str, dict]]:
    """Load parameter_annotations.json as a nested dict.

    Returns:
        ``{component_name: {param_id: {param_name, description?, boundary?, ...}}}``.
        Returns an empty dict if the file does not exist (graceful fallback).
    """
    if not _ANNOTATIONS_PATH.exists():
        return {}
    with open(_ANNOTATIONS_PATH, encoding="utf-8") as f:
        data: dict[str, dict[str, dict]] = json.load(f)
    return data


# ---------------------------------------------------------------------------
# Prompt context builders
# ---------------------------------------------------------------------------


def _truncate_text(text: str, limit: int) -> str:
    """Truncate text at a word boundary with a clear marker."""
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0].rstrip()
    return f"{truncated}\n[truncated for prompt budget]"


def _format_manual_section(
    manual_results: list[dict],
    *,
    component_char_limit: int | None = _MANUAL_COMPONENT_CHAR_LIMIT,
    section_char_budget: int | None = None,
    seen_names: set[str] | None = None,
) -> str:
    """Format a list of manual chunks into deduplicated text blocks.

    Full component text is included — manual chunks are already scoped
    per component and the Phase 2 context window can accommodate them.

    Args:
        manual_results: List of dicts with component_name, category, text.

    Returns:
        Formatted text, or empty string if no results.
    """
    sections: list[str] = []
    seen = seen_names if seen_names is not None else set()
    used_chars = 0
    for r in manual_results:
        name = r["component_name"]
        if name in seen:
            continue
        category = r.get("category", "")
        raw_text = str(r.get("text", ""))
        text = (
            _truncate_text(raw_text, component_char_limit)
            if component_char_limit is not None
            else raw_text
        )
        section = f"[{name}] ({category})\n{text}"
        if section_char_budget is not None and used_chars + len(section) > section_char_budget:
            remaining = section_char_budget - used_chars
            if remaining < 200:
                break
            section = _truncate_text(section, remaining)
        sections.append(section)
        seen.add(name)
        used_chars += len(section)
        if section_char_budget is not None and used_chars >= section_char_budget:
            break
    return "\n\n".join(sections)


def build_manual_reference_context(
    exemplar_chunks: list[dict],
    tonal_chunks: list[dict] | None = None,
    gap_chunks: list[dict] | None = None,
    *,
    budgeted: bool = True,
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
    seen_names: set[str] = set()

    ex_text = _format_manual_section(
        exemplar_chunks,
        component_char_limit=_MANUAL_COMPONENT_CHAR_LIMIT if budgeted else None,
        section_char_budget=_MANUAL_SECTION_CHAR_BUDGETS["exemplar"] if budgeted else None,
        seen_names=seen_names if budgeted else None,
    )
    if ex_text:
        parts.append(f"--- COMPONENTS FROM EXEMPLARS ---\n{ex_text}")

    if tonal_chunks:
        tonal_text = _format_manual_section(
            tonal_chunks,
            component_char_limit=_MANUAL_COMPONENT_CHAR_LIMIT if budgeted else None,
            section_char_budget=_MANUAL_SECTION_CHAR_BUDGETS["tonal"] if budgeted else None,
            seen_names=seen_names if budgeted else None,
        )
        if tonal_text:
            parts.append(f"--- TONALLY RELEVANT ALTERNATIVES ---\n{tonal_text}")

    if gap_chunks:
        gap_text = _format_manual_section(
            gap_chunks,
            component_char_limit=_MANUAL_COMPONENT_CHAR_LIMIT if budgeted else None,
            section_char_budget=_MANUAL_SECTION_CHAR_BUDGETS["gap"] if budgeted else None,
            seen_names=seen_names if budgeted else None,
        )
        if gap_text:
            parts.append(f"--- GAP-FILLING CANDIDATES ---\n{gap_text}")

    return "\n\n".join(parts) if parts else "(no manual descriptions available)"


def build_component_schema_context(
    component_names: list[str],
    schema: dict,
    annotations: dict[str, dict[str, dict]] | None = None,
    *,
    compact: bool = True,
    include_annotation_descriptions: bool = False,
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
        lines = [f"[{name}] id={entry['component_id']}"]
        comp_anns = annotations.get(name, {})
        for param in entry.get("parameters", []):
            pid = param["param_id"]
            pname = param["param_name"]
            default = param["default_value"]
            stats = param.get("stats", {})
            lo = stats.get("min", 0.0)
            hi = stats.get("max", 1.0)
            median = stats.get("median", default)

            if compact:
                line = f"  {pid} | default={default} | range={lo}..{hi} | median={median}"
            else:
                line = (
                    f"  {pid} | {pname} | default: {default} | "
                    f"range: [{lo}, {hi}] | median: {median}"
                )

            ann = comp_anns.get(pid, {})
            suffix_parts: list[str] = []
            if include_annotation_descriptions and "description" in ann:
                suffix_parts.append(ann["description"])
            if "boundary" in ann:
                suffix_parts.append(ann["boundary"])
            if suffix_parts:
                line += " | " + "; ".join(suffix_parts)

            lines.append(line)
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "(no schema available)"


def select_schema_component_names(
    *,
    exemplar_component_names: set[str],
    tonal_chunks: list[dict],
    gap_chunks: list[dict],
    parsed: ParsedSignalChain,
) -> list[str]:
    """Select high-value schema entries while capping broad gap-fill candidates."""
    selected: set[str] = set(exemplar_component_names)
    selected.update(str(r["component_name"]) for r in tonal_chunks)
    selected.update(
        unit.gr_equivalent
        for section in parsed.sections
        for unit in section.units
        if unit.gr_equivalent
    )
    selected.update({_MATCHED_CABINET_PRO_NAME, *_CONTROL_ROOM_NAMES})

    gap_by_category: dict[str, int] = {}
    for row in gap_chunks:
        category = str(row.get("category", ""))
        if gap_by_category.get(category, 0) >= _GAP_SCHEMA_PER_CATEGORY:
            continue
        selected.add(str(row["component_name"]))
        gap_by_category[category] = gap_by_category.get(category, 0) + 1

    return sorted(selected)


def _approximate_tokens(text: str) -> int:
    return max(1, len(text) // _PHASE2_TOKEN_CHAR_DIVISOR) if text else 0


def record_phase2_context_metrics(contexts: dict[str, str], full_prompt: str) -> None:
    """Record prompt block sizes without storing prompt text."""
    for name, text in {**contexts, "FULL_PHASE2_PROMPT": full_prompt}.items():
        record_context_block(
            LLMContextBlockMetric(
                operation=_PHASE2_CONTEXT_OPERATION,
                block_name=name,
                char_count=len(text),
                approximate_tokens=_approximate_tokens(text),
            )
        )
    full_prompt_tokens = _approximate_tokens(full_prompt)
    if full_prompt_tokens > settings.phase2_prompt_budget_tokens:
        _log.info(
            "Phase 2 prompt estimate exceeds target budget: approximate_tokens=%d target=%d",
            full_prompt_tokens,
            settings.phase2_prompt_budget_tokens,
        )


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
    model: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Map a Phase 1 signal chain to an ordered list of GR7 component dicts.

    Exemplar-first pipeline:
      1. Retrieve top-5 tonally similar factory presets
      2. Gather manual descriptions for exemplar components
      3. Retrieve manual descriptions for effect categories the exemplars lack
      4. Build prompt with exemplars, manual reference, schema, cabinet lookup
      5. Call the LLM with the exemplar refinement prompt (compact tonal target)
      6. Parse JSON response, fill defaults, enforce cabinet

    Args:
        signal_chain: The raw Phase 1 signal chain text (used for ChromaDB
            manual retrieval where the verbose text aids embedding similarity).
        parsed: The structured Phase 1 output.  Tags and component names are
            extracted directly for exemplar scoring, and a compact tonal
            target is rendered for the Phase 2 prompt.
        model: Provider/model identifier. Defaults to ``settings.default_model``.

    Returns:
        Tuple of (components, exemplars):
            components: Ordered list of component dicts, each with
                component_name, component_id, base_exemplar,
                modification, confidence, parameters.
            exemplars: List of exemplar dicts retrieved for this query.

    Raises:
        ValueError: If the LLM response cannot be parsed as a JSON array.
    """
    _log.info(
        "map_components: %d exemplar tags, %d pre-extracted components",
        len(parsed.tags_characters + parsed.tags_genres),
        sum(len(s.units) for s in parsed.sections),
    )
    schema = load_schema()
    amp_cabinet_lookup = load_amp_cabinet_lookup()
    annotations = load_annotations()
    name_lookup = build_name_lookup(schema)

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
    manual_for_exemplars = _canonicalize_manual_chunk_names(
        get_manual_chunks_for_components(_expand_manual_lookup_names(exemplar_component_names)),
        name_lookup,
    )

    # 4. Manual descriptions for categories the exemplars may lack
    manual_for_additions = _canonicalize_manual_chunk_names(
        search_manual_for_categories(signal_chain, exclude_names=exemplar_component_names),
        name_lookup,
    )

    # 4b. Tonal similarity search — swap candidates across all categories
    manual_for_tonal = _canonicalize_manual_chunk_names(
        search_manual_by_tonal_target(
            signal_chain,
            top_n=5,
            exclude_names=exemplar_component_names,
        ),
        name_lookup,
    )

    # 5. Collect high-priority component names that need schema entries.
    all_component_names = select_schema_component_names(
        exemplar_component_names=exemplar_component_names,
        tonal_chunks=manual_for_tonal,
        gap_chunks=manual_for_additions,
        parsed=parsed,
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

    prompt_context = {
        "SIGNAL_CHAIN": tonal_target,
        "EXEMPLAR_PRESETS": exemplar_context,
        "MANUAL_REFERENCE": manual_context,
        "COMPONENT_SCHEMA": schema_context,
        "CABINET_LOOKUP": cabinet_context,
        "CRP_REFERENCE": crp_context,
        "TONAL_DESCRIPTORS": tonal_descriptor_context,
    }

    prompt = render_prompt(
        "exemplar_refinement_prompt",
        **prompt_context,
    )
    record_phase2_context_metrics(prompt_context, prompt)

    # 8. Phase 2 LLM call
    resolved_model = model or settings.default_model
    raw = llm_client.complete(
        [{"role": "user", "content": prompt}],
        model=resolved_model,
        max_tokens=4096,
        temperature=settings.phase2_temperature,
    )

    _log.info(
        "Phase 2 LLM call complete: model=%s, response_length=%d",
        resolved_model,
        len(raw),
    )
    raw = raw.strip()

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

    # 9. Resolve LLM component names to canonical schema names.
    components = resolve_component_names(components, name_lookup)
    components = repair_component_identities(components, schema)

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
        _log.debug("Cabinet handling: CRP present")
        components = [
            c for c in components if c.get("component_name", "") != _MATCHED_CABINET_PRO_NAME
        ]
        _validate_crp_params(components)
    elif has_mcp:
        # LLM emitted MCP — validate Cab against reference but don't override.
        _log.debug("Cabinet handling: MCP present")
        _validate_mcp_params(components, amp_cabinet_lookup)
    else:
        # No cabinet solution at all — inject Matched Cabinet Pro as fallback.
        _log.debug("Cabinet handling: fallback — injecting MCP")
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
