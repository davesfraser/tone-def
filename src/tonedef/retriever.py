"""
retriever.py
------------
RAG retrieval layer for ToneDef Phase 2.

Provides two retrieval functions:

  search_by_hardware(name)
      Semantic search against GR7 manual descriptions.
      Used when a hardware name has no match in component_mapping.json.

  search_by_descriptor(descriptor)
      Category-stratified semantic search for tonal descriptors. Queries
      each GR7 component category separately (Amplifiers, Distortion, etc.)
      and merges results, so a query dominated by one tonal noun (e.g.
      "reverb") still surfaces relevant amps and drive units.

Both functions query the same ChromaDB collection — the distinction is
only in what string is used as the query and how results are retrieved.

Build the persisted collection once with:
    scripts/build_retrieval_index.py
"""

from __future__ import annotations

from pathlib import Path

import chromadb

from tonedef.paths import DATA_PROCESSED

_COLLECTION_NAME = "gr_manual"
_PERSIST_DIR = DATA_PROCESSED / "chromadb"

# Cached client + collection — created once per process
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    """Return the persisted ChromaDB collection, loading it if needed."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(_PERSIST_DIR))
        _collection = _client.get_collection(_COLLECTION_NAME)
    return _collection


def search_by_hardware(hardware_name: str, n_results: int = 5) -> list[dict]:
    """
    Retrieve GR7 component descriptions most similar to a hardware name.

    Used as a fallback when lookup_hardware() returns no mapping rows —
    surfaces descriptions of plausible GR7 components by semantic similarity.

    Args:
        hardware_name: The real-world hardware name (e.g. "Dallas Arbiter Fuzz Face").
        n_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: component_name, category, text, distance.
    """
    return _query(_QUERY_PREFIX_HARDWARE + hardware_name, n_results)


def search_by_descriptor(descriptor: str, n_results: int = 8) -> list[dict]:
    """
    Retrieve GR7 component descriptions most similar to a tonal descriptor.

    Uses category-stratified retrieval — queries each category in
    _DESCRIPTOR_ALLOCATION separately, then merges and sorts by distance.
    This prevents a query that mentions "reverb" from returning only reverb
    components; a typical guitar signal chain needs amps, drive units, and
    time-based effects simultaneously.

    n_results is retained for API compatibility but is not used; the total
    returned is governed by _DESCRIPTOR_ALLOCATION (default: 8 results).

    Args:
        descriptor: A tonal descriptor string (e.g. "bright clean jangly shimmer
                    with chorus and reverb, low gain, wide stereo").
        n_results: Unused — retained for API compatibility.

    Returns:
        List of dicts with keys: component_name, category, text, distance,
        sorted by ascending distance.
    """
    return _query_stratified(descriptor, _DESCRIPTOR_ALLOCATION)


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


def _query(query_text: str, n_results: int) -> list[dict]:
    collection = _get_collection()
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    items = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        strict=False,
    ):
        items.append(
            {
                "component_name": meta.get("component_name", ""),
                "category": meta.get("category", ""),
                "text": doc,
                "distance": dist,
            }
        )
    return items


def collection_path() -> Path:
    """Return the path where the ChromaDB collection is persisted."""
    return _PERSIST_DIR


# Prefix that tilts hardware-name queries toward amp/effect matching
_QUERY_PREFIX_HARDWARE = "Guitar effect or amplifier similar to: "

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
