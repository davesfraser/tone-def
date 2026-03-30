"""
crp_lookup.py
-------------
Loader for Control Room Pro integer enum tables (cabinet, microphone,
mic-position).  Data lives in ``data/processed/crp_enum_lookup.json``
and is injected into the Phase 2 prompt only for FULL_PRODUCTION chains.
"""

from __future__ import annotations

import json
from functools import lru_cache

from tonedef.paths import DATA_PROCESSED

_CRP_LOOKUP_PATH = DATA_PROCESSED / "crp_enum_lookup.json"


@lru_cache(maxsize=1)
def load_crp_enums() -> dict:
    """Load the CRP enum lookup from JSON.

    Returns:
        Dict with keys ``cabinets``, ``microphones``, ``mic_positions``.
        Each maps integer-string keys to ``{name, description}`` dicts.
    """
    with open(_CRP_LOOKUP_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)
    return data


def format_crp_reference(enums: dict | None = None) -> str:
    """Format CRP enum tables as a human-readable string for prompt injection.

    Args:
        enums: Output of :func:`load_crp_enums`.  Loaded automatically if
            ``None``.

    Returns:
        Formatted string suitable for the ``{{CRP_REFERENCE}}`` placeholder.
    """
    if enums is None:
        enums = load_crp_enums()

    lines: list[str] = []

    lines.append("CABINETS (Cab1 / Cab2 / … integer values):")
    for key in sorted(enums["cabinets"], key=int):
        entry = enums["cabinets"][key]
        lines.append(f"{int(key):>2} = {entry['name']}  ({entry['description']})")

    lines.append("")
    lines.append("MICROPHONES (Mic1 / Mic2 / … integer values):")
    for key in sorted(enums["microphones"], key=int):
        entry = enums["microphones"][key]
        lines.append(f"{int(key)} = {entry['name']}  ({entry['description']})")

    lines.append("")
    lines.append("MIC POSITIONS (MPos1 / MPos2 / … integer values):")
    for key in sorted(enums["mic_positions"], key=int):
        entry = enums["mic_positions"][key]
        lines.append(f"{int(key)} = {entry['name']}  ({entry['description']})")

    return "\n".join(lines)
