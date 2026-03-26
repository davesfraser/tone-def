"""
exemplar_store.py
-----------------
Builds and formats a dataset of factory preset exemplars for few-shot parameter
grounding in EXEMPLAR_REFINEMENT_PROMPT.

Each exemplar record pairs a preset's tonal tags (from tag_catalogue.json) with
its actual component list and parameter values (parsed from the .ngrr binary).
These records are injected as few-shot examples so the LLM sees real parameter
combinations for specific tonal characters rather than relying solely on
clock-position arithmetic.

Functions:

  build_exemplar_records(preset_dir, tag_catalogue, schema)
      Parse all .ngrr presets, look up their tags, return list of exemplar
      record dicts. Called once by scripts/build_exemplar_index.py.

  format_exemplar_context(exemplars)
      Format a short list of exemplar records as a few-shot prompt block.
      Called at runtime by component_mapper.map_components().
"""

from __future__ import annotations

from pathlib import Path

from tonedef.ngrr_parser import extract_preset_name, extract_xml2, parse_non_fix_components


def _invert_tag_catalogue(tag_catalogue: list[dict]) -> dict[str, list[str]]:
    """
    Build a {preset_name: [tag_value, ...]} mapping from the tag catalogue.

    The tag catalogue is stored tag-first (each entry lists the presets that
    carry it). This inverts it to preset-first for O(1) tag lookup during
    record construction.

    Args:
        tag_catalogue: Loaded tag_catalogue.json — list of tag dicts, each with
                       a "value" string and a "seen_in_presets" list.

    Returns:
        Dict mapping preset name to list of tag value strings.
    """
    preset_tags: dict[str, list[str]] = {}
    for entry in tag_catalogue:
        tag_value = entry["value"]
        for preset_name in entry.get("seen_in_presets", []):
            preset_tags.setdefault(preset_name, []).append(tag_value)
    return preset_tags


def build_exemplar_records(
    preset_dir: Path,
    tag_catalogue: list[dict],
    schema: dict,
) -> list[dict]:
    """
    Parse factory presets into exemplar records pairing tags with components.

    For each .ngrr file in preset_dir:
      1. Extract the preset name and XML2 block
      2. Parse the non-fix component list
      3. Look up tags from the inverted tag catalogue
      4. Convert parameters from list-of-dicts to {param_id: float} dict

    Presets that fail to parse or have no components are silently skipped.
    Presets with no tags are included with an empty tags list.

    Args:
        preset_dir: Directory containing .ngrr factory preset files.
        tag_catalogue: Loaded tag_catalogue.json (list of tag dicts).
        schema: Loaded component_schema.json. Accepted for API consistency
                but not used — parsing pulls values directly from the binary.

    Returns:
        List of exemplar record dicts, each with:
            preset_name: str
            tags:        list[str]
            components:  list[dict]  — {component_name, component_id,
                                         parameters: {param_id: float}}
    """
    preset_tags = _invert_tag_catalogue(tag_catalogue)
    records = []

    for path in sorted(preset_dir.glob("*.ngrr")):
        try:
            name = extract_preset_name(path)
            xml2 = extract_xml2(path)
            if xml2 is None:
                continue
            raw_components = parse_non_fix_components(xml2)
            if not raw_components:
                continue
        except Exception:
            continue

        components = [
            {
                "component_name": c["component_name"],
                "component_id": c["component_id"],
                "parameters": {p["param_id"]: round(p["value"], 4) for p in c["parameters"]},
            }
            for c in raw_components
        ]

        records.append(
            {
                "preset_name": name,
                "tags": preset_tags.get(name, []),
                "components": components,
            }
        )

    return records


def format_exemplar_context(exemplars: list[dict]) -> str:
    """
    Format a list of exemplar records as a few-shot block for prompt injection.

    Each exemplar shows the preset's tonal tags followed by its component list
    with all parameter values. This gives the LLM concrete examples of real
    parameter combinations for specific tonal characters, calibrating its
    estimates against actual Guitar Rig presets.

    Format:
        [Tag1, Tag2] — Preset Name
          Component Name (component_id): param1=0.50 param2=0.70 ...
          Next Component (component_id): ...

    Args:
        exemplars: Up to 3 exemplar records (as returned by
                   build_exemplar_records or retriever.search_exemplars).

    Returns:
        Formatted multi-line string for {{EXEMPLAR_PRESETS}} injection.
        Returns "(no exemplars available)" if exemplars is empty.
    """
    if not exemplars:
        return "(no exemplars available)"

    sections = []
    for ex in exemplars:
        tag_str = ", ".join(ex["tags"]) if ex["tags"] else "untagged"
        lines = [f"[{tag_str}] -- {ex['preset_name']}"]
        for comp in ex["components"]:
            params_str = "  ".join(f"{pid}={v:.2f}" for pid, v in comp["parameters"].items())
            lines.append(f"  {comp['component_name']} ({comp['component_id']}): {params_str}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
