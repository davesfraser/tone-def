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
from pathlib import Path

import chromadb

from tonedef.paths import DATA_PROCESSED

_COLLECTION_NAME = "gr_manual"
_EXEMPLARS_COLLECTION_NAME = "gr_exemplars"
_PERSIST_DIR = DATA_PROCESSED / "chromadb"
_EXEMPLARS_PATH = DATA_PROCESSED / "exemplar_store.json"

# Module-level caches — created once per process
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None
_exemplars_collection: chromadb.Collection | None = None
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


def _get_exemplars_collection() -> chromadb.Collection:
    """Return the exemplar presets collection, loading it if needed."""
    global _exemplars_collection
    if _exemplars_collection is None:
        _exemplars_collection = _get_client().get_collection(_EXEMPLARS_COLLECTION_NAME)
    return _exemplars_collection


def _get_exemplars_store() -> dict[str, dict]:
    """Return the in-memory exemplar store index, loading from JSON if needed."""
    global _exemplars_store
    if _exemplars_store is None:
        records: list[dict] = json.loads(_EXEMPLARS_PATH.read_text(encoding="utf-8"))
        _exemplars_store = {r["preset_name"]: r for r in records}
    return _exemplars_store


def search_exemplars(query: str, n_results: int = 5) -> list[dict]:
    """
    Retrieve exemplar preset records most similar to a tonal query.

    Queries the "gr_exemplars" ChromaDB collection (document = tag string +
    preset name) and returns the matching full exemplar records from the
    in-memory exemplar store. Results include real parameter values from
    actual Guitar Rig factory presets.

    The full signal chain text from Phase 1 is the most useful query — it
    contains tonal vocabulary (clean, distorted, blues, rock, etc.) that
    aligns naturally with the tag strings stored as document text.

    Args:
        query: Tonal query string — typically the Phase 1 signal chain text.
        n_results: Number of exemplar records to return.

    Returns:
        List of exemplar record dicts, each with:
            preset_name: str
            tags:        list[str]
            components:  list[dict]
            distance:    float
    """
    collection = _get_exemplars_collection()
    store = _get_exemplars_store()

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["metadatas", "distances"],
    )

    items = []
    for meta, dist in zip(
        results["metadatas"][0],
        results["distances"][0],
        strict=False,
    ):
        preset_name = meta.get("preset_name", "")
        record = store.get(preset_name)
        if record is not None:
            items.append({**record, "distance": dist})
    return items


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
