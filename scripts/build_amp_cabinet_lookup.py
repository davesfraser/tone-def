# applied-skills: ds-eda
"""
Build amp_cabinet_lookup.json from the exemplar store.

For each amplifier component, determines the correct Matched Cabinet Pro
component_id and Cab enum value by analysing which Cab value is most
commonly paired with that amplifier across all factory presets.

Usage:
    uv run python scripts/build_amp_cabinet_lookup.py
"""

from __future__ import annotations

import json
from collections import Counter

import chromadb

from tonedef.paths import DATA_PROCESSED

_EXEMPLAR_PATH = DATA_PROCESSED / "exemplar_store.json"
_CHROMADB_DIR = DATA_PROCESSED / "chromadb"
_OUTPUT_PATH = DATA_PROCESSED / "amp_cabinet_lookup.json"

_CABINET_COMPONENT_NAME = "Matched Cabinet Pro"
_CABINET_COMPONENT_ID = 156000

# Amps present in the schema/exemplars but absent from the ChromaDB manual
# index. These are discovered by cross-referencing the exemplar store.
_EXTRA_AMP_NAMES: set[str] = {"Fire Seeker"}


def _get_amp_names() -> set[str]:
    """Return amplifier component names from the ChromaDB manual index."""
    client = chromadb.PersistentClient(path=str(_CHROMADB_DIR))
    coll = client.get_collection("gr_manual")
    results = coll.get(where={"category": "Amplifiers"}, include=["metadatas"])
    return {meta["component_name"] for meta in results["metadatas"]}


def _build_lookup(store: list[dict], amp_names: set[str]) -> dict[str, dict]:
    """Build amp_name -> {cabinet_component_id, cabinet_component_name, cab_value}."""
    # Build case-insensitive index so "AC BOX XV" from the manual and
    # "AC Box XV" from the schema both resolve correctly
    amp_lower_to_names: dict[str, set[str]] = {}
    for name in amp_names:
        amp_lower_to_names.setdefault(name.lower(), set()).add(name)

    amp_cab_counts: dict[str, Counter] = {}

    for preset in store:
        comps = preset["components"]
        mcp = next(
            (c for c in comps if c["component_name"] == _CABINET_COMPONENT_NAME),
            None,
        )
        if mcp is None:
            continue
        cab_value = mcp["parameters"].get("Cab")
        if cab_value is None:
            continue

        for c in comps:
            cn_lower = c["component_name"].lower()
            if cn_lower not in amp_lower_to_names:
                continue
            # Register under both the canonical name(s) AND the exact preset name
            names_to_register = set(amp_lower_to_names[cn_lower])
            names_to_register.add(c["component_name"])
            for name in names_to_register:
                amp_cab_counts.setdefault(name, Counter())[cab_value] += 1

    lookup: dict[str, dict] = {}
    for amp_name in sorted(amp_cab_counts):
        counts = amp_cab_counts[amp_name]
        if not counts:
            continue
        best_cab, best_count = counts.most_common(1)[0]
        total = sum(counts.values())
        lookup[amp_name] = {
            "cabinet_component_name": _CABINET_COMPONENT_NAME,
            "cabinet_component_id": _CABINET_COMPONENT_ID,
            "cab_value": best_cab,
            "evidence_count": best_count,
            "evidence_total": total,
        }

    return lookup


def main() -> None:
    store: list[dict] = json.loads(_EXEMPLAR_PATH.read_text(encoding="utf-8"))
    amp_names = _get_amp_names() | _EXTRA_AMP_NAMES

    lookup = _build_lookup(store, amp_names)

    _OUTPUT_PATH.write_text(
        json.dumps(lookup, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(lookup)} amp entries to {_OUTPUT_PATH}")
    for amp_name, entry in sorted(lookup.items()):
        cab = entry["cab_value"]
        n = entry["evidence_count"]
        t = entry["evidence_total"]
        print(f"  {amp_name:22s}  Cab={cab:<6}  ({n}/{t} presets)")


if __name__ == "__main__":
    main()
