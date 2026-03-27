"""
retriever.py
------------
RAG retrieval layer for ToneDef Phase 2 (exemplar-first architecture).

Provides:
  search_exemplars(query)
      Retrieve tonally similar factory presets from the exemplar collection.
  get_manual_chunks_for_components(names)
      Retrieve manual descriptions for specific GR7 components.
  search_manual_for_categories(query, exclude_names)
      Category-stratified manual search for components the exemplars lack.

Build the persisted collections once with:
    scripts/build_retrieval_index.py
    scripts/build_exemplar_index.py
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import chromadb

from tonedef.paths import DATA_PROCESSED
from tonedef.settings import settings

_COLLECTION_NAME = "gr_manual"
_PERSIST_DIR = DATA_PROCESSED / "chromadb"
_EXEMPLARS_PATH = DATA_PROCESSED / "exemplar_store.json"

# Controlled tag vocabulary — must match prompts.py SYSTEM_PROMPT
CHARACTERS_VOCAB: frozenset[str] = frozenset(
    {
        "Clean",
        "Colored",
        "Complex",
        "Creative",
        "Dissonant",
        "Distorted",
        "Evolving",
        "Mash-Up",
        "Mixing",
        "Modulated",
        "Pitched",
        "Plucks",
        "Re-Sample",
        "Rhythmic",
        "Spacious",
        "Special FX",
    }
)
GENRES_VOCAB: frozenset[str] = frozenset(
    {
        "Alternative",
        "Ambient",
        "Blues",
        "Cinematic",
        "Country",
        "Electronica",
        "Experimental",
        "Funk & Soul",
        "Hip Hop",
        "Lofi",
        "Metal",
        "Pop",
        "Rock",
        "Stoner",
    }
)
CONTROLLED_VOCAB: frozenset[str] = CHARACTERS_VOCAB | GENRES_VOCAB

# Module-level caches — created once per process
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None
_exemplars_store: dict[str, dict] | None = None  # {preset_name: record}


def _get_client() -> chromadb.ClientAPI:
    """Return the shared persistent ChromaDB client, creating it if needed."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(_PERSIST_DIR))
    return _client


def _get_collection() -> chromadb.Collection:
    """Return the GR7 manual collection, loading it if needed."""
    global _collection
    if _collection is None:
        _collection = _get_client().get_collection(_COLLECTION_NAME)
    return _collection


def _get_exemplars_store() -> dict[str, dict]:
    """Return the in-memory exemplar store index, loading from JSON if needed."""
    global _exemplars_store
    if _exemplars_store is None:
        records: list[dict] = json.loads(_EXEMPLARS_PATH.read_text(encoding="utf-8"))
        _exemplars_store = {r["preset_name"]: r for r in records}
    return _exemplars_store


# ---------------------------------------------------------------------------
# Phase 1 output parsers
# ---------------------------------------------------------------------------

_TAGS_LINE_RE = re.compile(r"^(Characters|Genres)\s*:\s*(.+)$", re.MULTILINE)
_UNIT_NAME_RE = re.compile(r"^\[\s*(.+?)\s*—\s*.+?\]\s*\[", re.MULTILINE)


def parse_signal_chain_tags(signal_chain: str) -> list[str]:
    """Extract Characters + Genres tags from Phase 1 signal chain text.

    Parses lines like ``Characters: Clean, Spacious`` and
    ``Genres: Rock, Alternative`` from the TAGS section of Phase 1 output.
    Only returns values that exist in the controlled vocabulary.

    Args:
        signal_chain: Full Phase 1 signal chain text.

    Returns:
        De-duplicated list of tag strings in parse order.
    """
    tags: list[str] = []
    seen: set[str] = set()
    for match in _TAGS_LINE_RE.finditer(signal_chain):
        for raw in match.group(2).split(","):
            tag = raw.strip()
            if tag in CONTROLLED_VOCAB and tag not in seen:
                seen.add(tag)
                tags.append(tag)
    return tags


def parse_signal_chain_components(signal_chain: str) -> list[str]:
    """Extract unit names from Phase 1 signal chain text.

    Parses ``[ Unit Name — type ] [DOCUMENTED/...]`` lines and returns
    the unit names. Includes amps, effects, cabinets, and microphones.

    Args:
        signal_chain: Full Phase 1 signal chain text.

    Returns:
        De-duplicated list of component name strings in chain order.
    """
    names: list[str] = []
    seen: set[str] = set()
    for match in _UNIT_NAME_RE.finditer(signal_chain):
        name = match.group(1).strip()
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_exemplar(
    record: dict,
    query_tags: list[str],
    query_components: list[str],
    tag_weight: float | None = None,
    component_weight: float | None = None,
) -> float:
    """Score an exemplar record against parsed Phase 1 output.

    Computes a weighted combination of tag overlap (Jaccard similarity on
    the controlled vocabulary) and component name overlap.

    Args:
        record: Exemplar dict with ``tags`` and ``components`` keys.
        query_tags: Tags parsed from Phase 1 output (Characters + Genres).
        query_components: Component names parsed from Phase 1 output.
        tag_weight: Weight for tag score (default from settings).
        component_weight: Weight for component score (default from settings).

    Returns:
        Combined similarity score in [0.0, 1.0].
    """
    tw = tag_weight if tag_weight is not None else settings.exemplar_tag_weight
    cw = component_weight if component_weight is not None else settings.exemplar_component_weight

    # Tag score: Jaccard on controlled-vocab tags only
    query_tag_set = set(query_tags)
    exemplar_tag_set = {t for t in record.get("tags", []) if t in CONTROLLED_VOCAB}
    union = query_tag_set | exemplar_tag_set
    tag_score = len(query_tag_set & exemplar_tag_set) / len(union) if union else 0.0

    # Component score: overlap / max(len_a, len_b)
    query_comp_set = set(query_components)
    exemplar_comp_set = {c["component_name"] for c in record.get("components", [])}
    max_len = max(len(query_comp_set), len(exemplar_comp_set))
    comp_score = len(query_comp_set & exemplar_comp_set) / max_len if max_len else 0.0

    return tw * tag_score + cw * comp_score


def search_exemplars(
    query: str,
    n_results: int = 5,
    *,
    tags: list[str] | None = None,
    components: list[str] | None = None,
) -> list[dict]:
    """Retrieve exemplar preset records most similar to a Phase 1 signal chain.

    Uses structured matching — tag overlap and component name overlap —
    instead of vector similarity.  Scores every exemplar record in the
    store, sorts descending, and returns the top *n_results*.

    Ties are broken by seeded random shuffle for reproducibility without
    arbitrary alphabetical bias.

    When *tags* and *components* are provided (e.g. extracted from a
    ``ParsedSignalChain``), the function skips internal regex parsing of
    *query* and uses the pre-extracted values directly.

    Args:
        query: Phase 1 signal chain text (contains TAGS and unit names).
            Used only when *tags* or *components* are not provided.
        n_results: Number of exemplar records to return.
        tags: Pre-extracted tag strings (Characters + Genres).  When
            provided, ``parse_signal_chain_tags`` is skipped.
        components: Pre-extracted unit name strings.  When provided,
            ``parse_signal_chain_components`` is skipped.

    Returns:
        List of exemplar record dicts, each with:
            preset_name: str
            tags:        list[str]
            components:  list[dict]
            distance:    float  (1.0 - score, for backward compatibility)
    """
    store = _get_exemplars_store()
    query_tags = tags if tags is not None else parse_signal_chain_tags(query)
    query_components = (
        components if components is not None else parse_signal_chain_components(query)
    )

    scored: list[tuple[float, str, dict]] = []
    for name, record in store.items():
        sc = score_exemplar(record, query_tags, query_components)
        scored.append((sc, name, record))

    # Seeded shuffle before sort so ties are broken randomly but reproducibly
    rng = random.Random(settings.random_seed)
    rng.shuffle(scored)
    scored.sort(key=lambda x: x[0], reverse=True)

    return [{**rec, "distance": round(1.0 - sc, 4)} for sc, _name, rec in scored[:n_results]]


def _query_stratified(query_text: str, allocation: dict[str, int]) -> list[dict]:
    """
    Run one ChromaDB query per category, merge, deduplicate, and sort by distance.

    For each category in allocation, queries the collection filtered to that
    category and takes the top-N results for that category. Deduplicates by
    component_name and sorts the combined list by ascending distance.

    Args:
        query_text: The embedding query string.
        allocation: Dict mapping category name → max results for that category.

    Returns:
        Merged, deduplicated, distance-sorted list of result dicts.
    """
    collection = _get_collection()
    seen: set[str] = set()
    items: list[dict] = []

    for category, n in allocation.items():
        results = collection.query(
            query_texts=[query_text],
            n_results=n,
            where={"category": category},
            include=["documents", "metadatas", "distances"],
        )
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            strict=False,
        ):
            cname = meta.get("component_name", "")
            if cname not in seen:
                seen.add(cname)
                items.append(
                    {
                        "component_name": cname,
                        "category": meta.get("category", ""),
                        "text": doc,
                        "distance": dist,
                    }
                )

    items.sort(key=lambda x: x["distance"])
    return items


def collection_path() -> Path:
    """Return the path where the ChromaDB collections are persisted."""
    return _PERSIST_DIR


def get_manual_chunks_for_components(component_names: set[str]) -> list[dict]:
    """
    Retrieve manual descriptions for a specific set of GR7 component names.

    Queries the manual collection by exact component_name match. Used to
    provide the LLM with documentation for components already present in
    the selected exemplar presets.

    Args:
        component_names: Set of exact GR7 component names.

    Returns:
        List of dicts with keys: component_name, category, text.
    """
    if not component_names:
        return []
    collection = _get_collection()
    items: list[dict] = []
    for name in sorted(component_names):
        try:
            results = collection.get(
                where={"component_name": name},
                include=["documents", "metadatas"],
            )
        except Exception:
            continue
        for doc, meta in zip(
            results.get("documents", []),
            results.get("metadatas", []),
            strict=False,
        ):
            items.append(
                {
                    "component_name": meta.get("component_name", name),
                    "category": meta.get("category", ""),
                    "text": doc,
                }
            )
    return items


def search_manual_for_categories(
    query: str,
    exclude_names: set[str],
    categories: set[str] | None = None,
    n_per_category: int = 2,
) -> list[dict]:
    """
    Retrieve manual descriptions for components the exemplar may be missing.

    Searches each category and returns results whose component_name is NOT
    in exclude_names. This surfaces candidates for "adding a missing effect"
    — e.g. if the exemplar has no delay but the tonal target wants one.

    Args:
        query: Tonal query string (Phase 1 output).
        exclude_names: Component names already covered (from exemplars).
        categories: Optional set of category names to search. If None,
                    searches all categories in _DESCRIPTOR_ALLOCATION.
        n_per_category: Max results per category before filtering.

    Returns:
        Deduplicated list of dicts with keys: component_name, category, text.
    """
    allocation = dict.fromkeys(categories or _DESCRIPTOR_ALLOCATION.keys(), n_per_category)
    raw = _query_stratified(query, allocation)
    return [r for r in raw if r["component_name"] not in exclude_names]


# Per-category result budget for stratified descriptor search.
# Ensures a full guitar signal chain is covered even when the query text
# is dominated by a single tonal noun (e.g. "reverb" or "distortion").
# Total: 8 results — Amplifiers x2, Distortion x2, Dynamics x1, Modulation x1,
# Delay/Echo x1, Reverb x1.
_DESCRIPTOR_ALLOCATION: dict[str, int] = {
    "Amplifiers": 2,
    "Distortion": 2,
    "Dynamics": 1,
    "Modulation": 1,
    "Delay / Echo": 1,
    "Reverb": 1,
}
