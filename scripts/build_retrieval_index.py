"""
build_retrieval_index.py
------------------------
Build and persist the ChromaDB collection used by tonedef.retriever.

Reads gr_manual_chunks.json and indexes each component's description text
into a ChromaDB collection with all-MiniLM-L6-v2 embeddings (default).

Run once before using the descriptor route in map_components():
    uv run python scripts/build_retrieval_index.py
"""

import contextlib
import json

import chromadb

from tonedef.paths import DATA_PROCESSED
from tonedef.retriever import _COLLECTION_NAME, _PERSIST_DIR, collection_path

_CHUNKS_PATH = DATA_PROCESSED / "gr_manual_chunks.json"


def main() -> None:
    with open(_CHUNKS_PATH, encoding="utf-8") as f:
        chunks: dict = json.load(f)

    client = chromadb.PersistentClient(path=str(_PERSIST_DIR))

    # Delete and recreate for a clean rebuild
    with contextlib.suppress(Exception):
        client.delete_collection(_COLLECTION_NAME)

    collection = client.create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids, documents, metadatas = [], [], []
    for component_name, entry in chunks.items():
        text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
        category = entry.get("category", "") if isinstance(entry, dict) else ""
        ids.append(component_name)
        documents.append(text)
        metadatas.append({"component_name": component_name, "category": category})

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indexed {len(ids)} components → {collection_path()}")


if __name__ == "__main__":
    main()
