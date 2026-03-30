"""
tonal_vocab.py
--------------
Loader and formatter for the expanded tonal descriptor vocabulary.

Descriptors are organised by signal chain zone:
  pre_amp, amp, cabinet, room_mic, post_cab

For FULL_PRODUCTION chains all zones apply; for AMP_ONLY chains the
room_mic zone is limited to Mic Placement and Room Character groups
(Mic Tone requires Control Room Pro and is excluded).
"""

from __future__ import annotations

import json
from functools import lru_cache

from tonedef.paths import DATA_PROCESSED

_DESCRIPTORS_PATH = DATA_PROCESSED / "tonal_descriptors.json"

# Zones relevant to each chain type
_FULL_PRODUCTION_ZONES = ("pre_amp", "amp", "cabinet", "room_mic", "post_cab")
_AMP_ONLY_ZONES = ("pre_amp", "amp", "cabinet", "room_mic", "post_cab")

# Display labels for prompt output
_ZONE_LABELS: dict[str, str] = {
    "pre_amp": "PRE-AMP / PEDALS",
    "amp": "AMPLIFIER",
    "cabinet": "CABINET",
    "room_mic": "ROOM & MICROPHONE",
    "post_cab": "POST-CABINET / EFFECTS",
}


@lru_cache(maxsize=1)
def _load_raw() -> dict:
    """Load the raw JSON including ``_meta``."""
    with open(_DESCRIPTORS_PATH, encoding="utf-8") as f:
        data: dict = json.load(f)
    return data


@lru_cache(maxsize=1)
def load_tonal_descriptors() -> dict[str, list[dict]]:
    """Load the tonal descriptor vocabulary from JSON.

    Returns:
        Dict mapping zone name to list of descriptor dicts.
        The ``_meta`` key is excluded.
    """
    raw = _load_raw()
    return {k: v for k, v in raw.items() if k != "_meta"}


@lru_cache(maxsize=1)
def load_descriptor_meta() -> dict:
    """Load the ``_meta`` block from the descriptors JSON.

    Returns:
        Dict with ``zones`` and ``groups`` metadata for UI rendering.
    """
    raw = _load_raw()
    meta: dict = raw.get("_meta", {})
    return meta


def get_zones_for_chain_type(chain_type: str) -> tuple[str, ...]:
    """Return the zone names applicable to a chain type.

    Args:
        chain_type: ``"FULL_PRODUCTION"`` or ``"AMP_ONLY"``.

    Returns:
        Tuple of zone name strings.
    """
    if chain_type == "FULL_PRODUCTION":
        return _FULL_PRODUCTION_ZONES
    return _AMP_ONLY_ZONES


# Groups that only apply when Control Room Pro is available
_CRP_ONLY_GROUPS: frozenset[str] = frozenset({"Mic Tone"})


def format_tonal_descriptors(
    chain_type: str,
    descriptors: dict[str, list[dict]] | None = None,
) -> str:
    """Format tonal descriptors as a prompt-ready string.

    Only includes zones relevant to the given chain type.  For AMP_ONLY
    chains the room_mic zone includes Mic Placement and Room Character
    groups (mapped to MCP X-Fade) but excludes Mic Tone (CRP only).

    Args:
        chain_type: ``"FULL_PRODUCTION"`` or ``"AMP_ONLY"``.
        descriptors: Output of :func:`load_tonal_descriptors`.  Loaded
            automatically if ``None``.

    Returns:
        Formatted string suitable for the ``{{TONAL_DESCRIPTORS}}``
        placeholder.
    """
    if descriptors is None:
        descriptors = load_tonal_descriptors()

    zones = get_zones_for_chain_type(chain_type)
    is_amp_only = chain_type != "FULL_PRODUCTION"
    sections: list[str] = []

    for zone in zones:
        entries = descriptors.get(zone, [])
        if not entries:
            continue
        if is_amp_only and zone == "room_mic":
            entries = [e for e in entries if e.get("group") not in _CRP_ONLY_GROUPS]
            if not entries:
                continue
        label = _ZONE_LABELS.get(zone, zone.upper())
        lines: list[str] = [f"{label}:"]
        for entry in entries:
            term = entry["term"]
            delta = entry["delta"]
            rationale = entry["rationale"]
            lines.append(f'  "{term}" → {delta}')
            lines.append(f"    {rationale}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def get_ui_groups(zone: str) -> list[dict]:
    """Return descriptor groups for a zone, ready for UI rendering.

    Each group dict contains:
      - ``group``: group name (e.g. ``"Gain Amount"``)
      - ``description``: plain-English group description
      - ``options``: list of ``{term, ui_label, ui_description}`` dicts

    Args:
        zone: Zone name (e.g. ``"pre_amp"``).

    Returns:
        List of group dicts ordered by first appearance in the JSON.
    """
    descriptors = load_tonal_descriptors()
    meta = load_descriptor_meta()
    group_descriptions: dict[str, str] = meta.get("groups", {}).get(zone, {})
    entries = descriptors.get(zone, [])

    # Preserve insertion order: collect groups as they appear
    seen: dict[str, list[dict]] = {}
    for entry in entries:
        group_name = entry.get("group", "Other")
        if group_name not in seen:
            seen[group_name] = []
        seen[group_name].append(
            {
                "term": entry["term"],
                "ui_label": entry.get("ui_label", entry["term"]),
                "ui_description": entry.get("ui_description", entry.get("rationale", "")),
            }
        )

    return [
        {
            "group": name,
            "description": group_descriptions.get(name, ""),
            "options": options,
        }
        for name, options in seen.items()
    ]


def get_all_selected_terms(selections: dict[str, str | None]) -> list[str]:
    """Extract non-None selected terms from a group-keyed mapping.

    Args:
        selections: Dict mapping ``"{zone}__{group}"`` keys to the
            selected term string or ``None``.

    Returns:
        List of selected term strings (order matches dict insertion order).
    """
    return [term for term in selections.values() if term is not None]
