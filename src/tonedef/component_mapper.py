"""
component_mapper.py
--------------------
Runtime module that maps a Phase 1 signal chain to Guitar Rig 7 components.

Responsibilities:
  1. Load component_mapping.json and component_schema.json
  2. Index the mapping by hardware name for fast lookup
  3. Parse hardware names from the Phase 1 signal chain text
  4. Resolve each hardware name to candidate GR7 components
     (exact match → fuzzy match → no match / omit)
  5. Build COMPONENT_SELECTION_PROMPT context strings
  6. Call the Anthropic API (Phase 2 LLM call)
  7. Parse and validate the JSON response
  8. Fill defaults for any omitted parameters from the schema
  9. Return an ordered list of component dicts ready for xml_builder
"""

from __future__ import annotations

import difflib
import json
import re

import anthropic

from tonedef.paths import DATA_PROCESSED
from tonedef.prompts import COMPONENT_SELECTION_PROMPT, DESCRIPTOR_SELECTION_PROMPT
from tonedef.retriever import search_by_descriptor, search_by_hardware

_MAPPING_PATH = DATA_PROCESSED / "component_mapping.json"
_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_MANUAL_CHUNKS_PATH = DATA_PROCESSED / "gr_manual_chunks.json"

# Minimum similarity score for fuzzy hardware name matching
_FUZZY_CUTOFF = 0.6


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_mapping() -> list[dict]:
    """Load component_mapping.json as a list of row dicts."""
    with open(_MAPPING_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_schema() -> dict:
    """Load component_schema.json as a dict keyed by component_name."""
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_manual_chunks() -> dict:
    """Load gr_manual_chunks.json as a dict keyed by component_name."""
    if not _MANUAL_CHUNKS_PATH.exists():
        return {}
    with open(_MANUAL_CHUNKS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Indexing and lookup
# ---------------------------------------------------------------------------


def build_hardware_index(mapping: list[dict]) -> dict[str, list[dict]]:
    """
    Build an inverted index from lowercase hardware name to mapping rows.

    Multiple rows may share a hardware name (aliasing multiple variants),
    so the value is always a list.

    Args:
        mapping: Output of load_mapping().

    Returns:
        Dict mapping lowercase hardware_name → list of matching rows.
    """
    index: dict[str, list[dict]] = {}
    for row in mapping:
        key = row["hardware_name"].lower().strip()
        index.setdefault(key, []).append(row)
    return index


def lookup_hardware(
    hardware_name: str,
    index: dict[str, list[dict]],
) -> list[dict]:
    """
    Look up a hardware name in the mapping index.

    Tries exact match first (case-insensitive), then fuzzy match using
    difflib. Returns an empty list if no match meets the similarity cutoff.

    Args:
        hardware_name: Hardware name as extracted from the signal chain.
        index: Output of build_hardware_index().

    Returns:
        List of matching mapping rows (may be empty).
    """
    key = hardware_name.lower().strip()

    # Exact match
    if key in index:
        return index[key]

    # Fuzzy match
    close = difflib.get_close_matches(key, index.keys(), n=3, cutoff=_FUZZY_CUTOFF)
    if close:
        best = close[0]
        rows = index[best]
        return rows

    return []


# ---------------------------------------------------------------------------
# Hardware name extraction from Phase 1 output
# ---------------------------------------------------------------------------


def extract_hardware_names(signal_chain: str) -> list[str]:
    """
    Extract hardware unit names from a Phase 1 signal chain string.

    Parses lines that match the Phase 1 output format:
        [ Unit name — unit type ] [DOCUMENTED/INFERRED/ESTIMATED]

    Args:
        signal_chain: The text content of the <signal_chain> block from Phase 1.

    Returns:
        List of hardware unit names in signal chain order.
    """
    # Pattern: [ Name — type ] [LABEL] — capture the Name part
    # Use only em dash and en dash as separators (not hyphen, which appears in hardware names)
    pattern = re.compile(r"\[\s*(.+?)\s*[\u2014\u2013]\s*.+?\s*\]", re.MULTILINE)
    names = []
    for match in pattern.finditer(signal_chain):
        candidate = match.group(1).strip()
        # Skip the provenance label token if it leaked through
        if candidate.upper() not in ("DOCUMENTED", "INFERRED", "ESTIMATED"):
            names.append(candidate)
    return names


# ---------------------------------------------------------------------------
# Prompt context builders
# ---------------------------------------------------------------------------


def _build_hardware_mapping_context(candidate_rows: list[dict]) -> str:
    """Format mapping rows as a pipe-delimited table for the prompt."""
    if not candidate_rows:
        return "(no matches found in mapping table)"
    lines = []
    for row in candidate_rows:
        lines.append(
            f"{row['hardware_name']} | {row['component_name']} "
            f"| {row['component_id']} | {row['confidence']}"
        )
    return "\n".join(lines)


def _build_component_candidates_context(
    component_names: list[str],
    manual_chunks: dict,
) -> str:
    """Format manual chunk descriptions for candidate components."""
    if not component_names:
        return "(no manual descriptions available)"
    sections = []
    for name in component_names:
        chunk = manual_chunks.get(name) or manual_chunks.get(name.upper())
        if chunk:
            text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
            # Trim to the first 400 characters to keep context concise
            trimmed = text[:400].rstrip()
            if len(text) > 400:
                trimmed += " ..."
            sections.append(f"[{name}]\n{trimmed}")
    return "\n\n".join(sections) if sections else "(no manual descriptions available)"


def _build_retrieved_candidates_context(results: list[dict]) -> str:
    """Format ChromaDB retrieval results as numbered candidate descriptions."""
    if not results:
        return "(no candidates retrieved)"
    sections = []
    for r in results:
        name = r["component_name"]
        category = r.get("category", "")
        text = r.get("text", "")
        trimmed = text[:400].rstrip()
        if len(text) > 400:
            trimmed += " ..."
        sections.append(f"[{name}] ({category})\n{trimmed}")
    return "\n\n".join(sections)


def _extract_tonal_description(signal_chain: str) -> str:
    """Extract a compact tonal description from a Phase 1 signal chain string.

    Strips the structured signal chain lines and returns the descriptive text
    that follows, falling back to the full string if no structure is found.
    """
    # Return everything after the last </signal_chain> tag if present
    import re

    match = re.search(r"</signal_chain>\s*(.*)", signal_chain, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Otherwise return the full string — still useful as a query
    return signal_chain.strip()


def _build_component_schema_context(
    component_names: list[str],
    schema: dict,
) -> str:
    """Format parameter definitions for candidate components."""
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


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def fill_defaults(components: list[dict], schema: dict) -> list[dict]:
    """
    Ensure every parameter in the schema is present in each component's
    parameter dict. Missing parameters are filled with their default_value.

    Also clamps all values to [0.0, 1.0].

    Args:
        components: Component list from the LLM response.
        schema: Parsed component_schema.json.

    Returns:
        Component list with complete, clamped parameter dicts.
    """
    for comp in components:
        comp_name = comp.get("component_name", "")
        params = comp.get("parameters", {})
        if comp_name in schema:
            for param_entry in schema[comp_name].get("parameters", []):
                pid = param_entry["param_id"]
                if pid not in params:
                    params[pid] = param_entry["default_value"]
                else:
                    params[pid] = max(0.0, min(1.0, float(params[pid])))
        comp["parameters"] = params
    return components


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def map_components(
    signal_chain: str,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-6",
) -> list[dict]:
    """
    Map a Phase 1 signal chain string to an ordered list of GR7 component dicts.

    Orchestrates the full Phase 2 pipeline:
      1. Extract hardware names from the signal chain
      2. Resolve each name to GR7 component candidates via the mapping index
      3. Assemble prompt context (mapping table, manual descriptions, schema)
      4. Call the LLM with COMPONENT_SELECTION_PROMPT
      5. Parse the JSON response
      6. Fill missing parameters with schema defaults

    Args:
        signal_chain: The text of the Phase 1 signal chain (full output string
                      or just the content inside <signal_chain> tags).
        client: An initialised anthropic.Anthropic client.
        model: Anthropic model identifier.

    Returns:
        Ordered list of component dicts, each with:
            component_name: str
            component_id: int
            hardware_source: str
            confidence: str
            parameters: dict[param_id, float]

    Raises:
        ValueError: If the LLM response cannot be parsed as a JSON array.
    """
    mapping = load_mapping()
    schema = load_schema()
    manual_chunks = load_manual_chunks()

    index = build_hardware_index(mapping)
    hardware_names = extract_hardware_names(signal_chain)

    # Collect all candidate rows and unique component names via mapping table
    all_candidate_rows: list[dict] = []
    seen_component_names: set[str] = set()
    candidate_component_names: list[str] = []

    for hw_name in hardware_names:
        rows = lookup_hardware(hw_name, index)
        # Fallback: semantic search for unmatched hardware names
        if not rows:
            retrieved = search_by_hardware(hw_name)
            for r in retrieved:
                cname = r["component_name"]
                if cname not in seen_component_names:
                    seen_component_names.add(cname)
                    candidate_component_names.append(cname)
        else:
            all_candidate_rows.extend(rows)
            for row in rows:
                cname = row["component_name"]
                if cname not in seen_component_names:
                    seen_component_names.add(cname)
                    candidate_component_names.append(cname)

    if all_candidate_rows:
        # Hardware route — mapping table produced results
        mapping_context = _build_hardware_mapping_context(all_candidate_rows)
        candidates_context = _build_component_candidates_context(
            candidate_component_names, manual_chunks
        )
        schema_context = _build_component_schema_context(candidate_component_names, schema)
        prompt = (
            COMPONENT_SELECTION_PROMPT.replace("{{SIGNAL_CHAIN}}", signal_chain)
            .replace("{{HARDWARE_MAPPING}}", mapping_context)
            .replace("{{COMPONENT_CANDIDATES}}", candidates_context)
            .replace("{{COMPONENT_SCHEMA}}", schema_context)
        )
    else:
        # Descriptor route — no recognised hardware; query by tonal description
        tonal_description = _extract_tonal_description(signal_chain)
        retrieved = search_by_descriptor(tonal_description)
        retrieved_names = [r["component_name"] for r in retrieved]
        retrieved_context = _build_retrieved_candidates_context(retrieved)
        schema_context = _build_component_schema_context(retrieved_names, schema)
        prompt = (
            DESCRIPTOR_SELECTION_PROMPT.replace("{{TONAL_DESCRIPTION}}", tonal_description)
            .replace("{{RETRIEVED_CANDIDATES}}", retrieved_context)
            .replace("{{COMPONENT_SCHEMA}}", schema_context)
        )

    # Phase 2 LLM call
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown fences if the model added them despite instructions
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    # Extract the JSON array even if the model prefixed it with reasoning prose
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    try:
        components: list[dict] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Phase 2 LLM returned non-JSON response: {exc}\n\n{raw}") from exc

    if not isinstance(components, list):
        raise ValueError(f"Phase 2 LLM returned non-array JSON: {type(components)}")

    components = fill_defaults(components, schema)

    return components
