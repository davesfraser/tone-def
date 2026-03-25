"""
retriever.py
------------
RAG retrieval layer for ToneDef Phase 2.

Provides two retrieval functions:

  search_by_hardware(name, collection)
      Semantic search against GR7 manual descriptions.
      Used when a hardware name has no match in component_mapping.json.

  search_by_descriptor(descriptor, collection)
      Semantic search using a tonal descriptor string (e.g. "bright clean
      jangly with chorus") when the signal chain contains no recognisable
      hardware names.

Both functions query the same ChromaDB collection — the distinction is
only in what string is used as the query.

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

    Used when the signal chain contains no recognisable hardware names —
    the Phase 1 tonal summary is used directly as the query.

    Args:
        descriptor: A tonal descriptor string (e.g. "bright clean jangly shimmer
                    with chorus and reverb, low gain, wide stereo").
        n_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: component_name, category, text, distance.
    """
    return _query(descriptor, n_results)


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
