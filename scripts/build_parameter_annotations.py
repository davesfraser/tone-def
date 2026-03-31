# applied-skills: ds-workflow
"""Build parameter annotations from manual chunks and component schema.

Extracts per-parameter semantic metadata:
  - description: brief what-it-does (1 line)
  - boundary: what 0.0 means (e.g. "filter off") when special
  - param_type: continuous | switch | enum

Uses regex extraction from manual text with fallback to schema-only
stats when the manual doesn't describe a parameter.

Output: data/processed/parameter_annotations.json
"""

from __future__ import annotations

import json
import re

from tonedef.paths import DATA_PROCESSED

_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_MANUAL_PATH = DATA_PROCESSED / "gr_manual_chunks.json"
_OUTPUT_PATH = DATA_PROCESSED / "parameter_annotations.json"

# ---------------------------------------------------------------------------
# Regex patterns for extracting parameter semantics from manual text
# ---------------------------------------------------------------------------

# Matches "• ParamDisplayName: description..." bullet points
_BULLET_PARAM = re.compile(
    r"•\s+(?P<name>[^:]{2,40}):\s+(?P<desc>.+?)(?=\n•|\Z)",
    re.DOTALL,
)

# Matches "turned fully to the left" / "turned fully left" → off/disabled
_BOUNDARY_OFF_LEFT = re.compile(
    r"(?:turned|set)\s+fully\s+(?:to\s+the\s+)?left"
    r"[^.]*?(?P<effect>(?:is\s+)?(?:switched\s+off|off|disabled|bypassed|deactivated))",
    re.IGNORECASE,
)

# Matches "When set to 0" / "at 0%" style boundaries
_BOUNDARY_ZERO = re.compile(
    r"(?:when\s+set\s+to|at)\s+0[^.]*?(?P<effect>(?:is\s+)?(?:off|disabled|bypassed|no\s+effect))",
    re.IGNORECASE,
)

# Matches frequency ranges: "30 Hz to 600 Hz" or "50 kHz to 3 kHz"
_FREQ_RANGE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?P<lo_unit>Hz|kHz)\s+to\s+"
    r"(?P<hi>\d+(?:\.\d+)?)\s*(?P<hi_unit>Hz|kHz)",
    re.IGNORECASE,
)

# Matches time ranges: "5 ms to 80 ms"
_TIME_RANGE = re.compile(
    r"(?P<lo>\d+(?:\.\d+)?)\s*(?P<lo_unit>ms|s)\s+to\s+"
    r"(?P<hi>\d+(?:\.\d+)?)\s*(?P<hi_unit>ms|s)",
    re.IGNORECASE,
)


def _first_sentence(text: str) -> str:
    """Extract roughly the first sentence from a description block."""
    # Stop at first period followed by space/newline, or at newline
    match = re.match(r"(.+?\.)\s", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: first line
    return text.split("\n")[0].strip()


def _detect_param_type(
    param_entry: dict,
) -> str:
    """Classify parameter type from schema stats."""
    default = param_entry.get("default_value", 0.0)
    stats = param_entry.get("stats", {})
    lo = stats.get("min", 0.0)
    hi = stats.get("max", 1.0)

    # Switch: only 0 and 1 observed
    if float(lo) == 0.0 and float(hi) == 1.0 and float(default) in (0.0, 1.0):
        unique_modes = stats.get("mode_count", 0)
        count = stats.get("count", 1)
        # If mode accounts for >90% of values and is 0 or 1, likely a switch
        if unique_modes > 0 and unique_modes / count > 0.9:
            return "switch"

    # Integer enum: default, min, max all whole numbers and range > 1
    if float(default) == int(default) and float(lo) == int(lo) and float(hi) == int(hi) and hi > 1:
        return "enum"

    return "continuous"


def _match_manual_param(
    param_name: str,
    manual_params: dict[str, str],
) -> str | None:
    """Find the best matching manual parameter description for a schema param_name.

    Tries exact match first, then substring containment.

    Args:
        param_name: Display name from schema (e.g. "HF Gain", "HP Freq").
        manual_params: Dict of {manual_display_name: description_text}.

    Returns:
        The description text if matched, else None.
    """
    # Exact match (case-insensitive)
    for manual_name, desc in manual_params.items():
        if manual_name.lower() == param_name.lower():
            return desc

    # Common abbreviation mappings
    _ABBREVS: dict[str, list[str]] = {
        "HP Freq": ["HPF"],
        "LP Freq": ["LPF"],
        "HF Gain": ["HF Gain"],
        "HF Freq": ["HF Freq"],
        "HF Bell": ["HF Bell/Shelf", "HF Bell"],
        "HMF Gain": ["HMF Gain"],
        "HMF Freq": ["HMF Freq"],
        "HMF Q": ["HMF Q"],
        "LMF Gain": ["LMF Gain"],
        "LMF Freq": ["LMF Freq"],
        "LMF Q": ["LMF Q"],
        "LF Gain": ["LF Gain"],
        "LF Freq": ["LF Freq"],
        "LF Bell": ["LF Bell/Shelf", "LF Bell"],
        "Mode": ["G/E response"],
        "On/Off": ["Power", "On/Off"],
    }

    if param_name in _ABBREVS:
        for alt in _ABBREVS[param_name]:
            for manual_name, desc in manual_params.items():
                if alt.lower() in manual_name.lower():
                    return desc

    # Substring match: param_name appears in manual name or vice versa
    pn_lower = param_name.lower()
    for manual_name, desc in manual_params.items():
        mn_lower = manual_name.lower()
        if pn_lower in mn_lower or mn_lower in pn_lower:
            return desc

    return None


def _extract_boundary(desc_text: str) -> str | None:
    """Extract boundary semantics from a parameter description.

    Returns a string like "0.0 = filter off" or None.
    """
    m = _BOUNDARY_OFF_LEFT.search(desc_text)
    if m:
        return "0.0 = " + m.group("effect").strip().rstrip(".")
    m = _BOUNDARY_ZERO.search(desc_text)
    if m:
        return "0.0 = " + m.group("effect").strip().rstrip(".")
    return None


def _extract_range(desc_text: str) -> str | None:
    """Extract a human-readable range from a parameter description.

    Returns e.g. "30 Hz - 600 Hz" or "5 ms - 80 ms", or None.
    """
    m = _FREQ_RANGE.search(desc_text)
    if m:
        return f"{m.group('lo')} {m.group('lo_unit')} - {m.group('hi')} {m.group('hi_unit')}"
    m = _TIME_RANGE.search(desc_text)
    if m:
        return f"{m.group('lo')} {m.group('lo_unit')} - {m.group('hi')} {m.group('hi_unit')}"
    return None


def _parse_manual_params(text: str) -> dict[str, str]:
    """Parse bullet-point parameter descriptions from manual text.

    Returns dict of {display_name: full_description_text}.
    """
    params: dict[str, str] = {}
    for m in _BULLET_PARAM.finditer(text):
        name = m.group("name").strip()
        desc = m.group("desc").strip()
        # Collapse internal whitespace
        desc = re.sub(r"\s+", " ", desc)
        params[name] = desc
    return params


def build_annotations() -> list[dict]:
    """Build parameter annotations for all components.

    Returns:
        List of annotation dicts, one per component+parameter.
    """
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    with open(_MANUAL_PATH, encoding="utf-8") as f:
        manual_chunks = json.load(f)

    annotations: list[dict] = []

    for comp_name, comp_entry in schema.items():
        # Parse manual text for this component
        manual_text = ""
        if comp_name in manual_chunks:
            manual_text = manual_chunks[comp_name].get("text", "")
        manual_params = _parse_manual_params(manual_text) if manual_text else {}

        for param_entry in comp_entry.get("parameters", []):
            pid = param_entry["param_id"]
            pname = param_entry.get("param_name", pid)

            # Skip Power/On-Off — always 1.0
            if pid == "Pwr":
                continue

            annotation: dict = {
                "component_name": comp_name,
                "param_id": pid,
                "param_name": pname,
                "param_type": _detect_param_type(param_entry),
            }

            # Try to match manual description
            matched_desc = _match_manual_param(pname, manual_params)
            if matched_desc:
                annotation["description"] = _first_sentence(matched_desc)

                # Extract boundary semantics
                boundary = _extract_boundary(matched_desc)
                if boundary:
                    annotation["boundary"] = boundary

                # Extract real-world range
                hw_range = _extract_range(matched_desc)
                if hw_range:
                    annotation["range"] = hw_range

            annotations.append(annotation)

    return annotations


def main() -> None:
    """Build and write parameter_annotations.json."""
    annotations = build_annotations()

    # Restructure as nested dict for fast lookup:
    # { component_name: { param_id: { ... } } }
    lookup: dict[str, dict[str, dict]] = {}
    for ann in annotations:
        comp = ann["component_name"]
        pid = ann["param_id"]
        entry = {k: v for k, v in ann.items() if k not in ("component_name", "param_id")}
        lookup.setdefault(comp, {})[pid] = entry

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)

    # Summary stats
    total = sum(len(params) for params in lookup.values())
    with_desc = sum(1 for params in lookup.values() for p in params.values() if "description" in p)
    with_boundary = sum(1 for params in lookup.values() for p in params.values() if "boundary" in p)
    with_range = sum(1 for params in lookup.values() for p in params.values() if "range" in p)

    print(f"Components:  {len(lookup)}")
    print(f"Parameters:  {total}")
    print(f"With description: {with_desc} ({with_desc * 100 // max(total, 1)}%)")
    print(f"With boundary:    {with_boundary}")
    print(f"With range:       {with_range}")
    print(f"Written to: {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
