"""
build_exemplar_index.py
-----------------------
Build and persist the exemplar store used by tonedef.retriever.search_exemplars.

1. Parses all factory .ngrr presets via exemplar_store.build_exemplar_records
2. Writes data/processed/exemplar_store.json
3. Indexes into a ChromaDB collection "gr_exemplars":
      document  = tag list + preset name (for semantic retrieval)
      metadata  = {"preset_name": preset_name}
      id        = preset_name

Run once before using exemplar retrieval in map_components():
    uv run python scripts/build_exemplar_index.py
"""

import contextlib
import json

import chromadb

from tonedef.exemplar_store import build_exemplar_records
from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED

_PRESETS_DIR = DATA_EXTERNAL / "presets"
_TAG_CATALOGUE_PATH = DATA_PROCESSED / "tag_catalogue.json"
_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_OUTPUT_PATH = DATA_PROCESSED / "exemplar_store.json"
_PERSIST_DIR = DATA_PROCESSED / "chromadb"
_COLLECTION_NAME = "gr_exemplars"


def main() -> None:
    tag_catalogue: list[dict] = json.loads(_TAG_CATALOGUE_PATH.read_text(encoding="utf-8"))
    schema: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    print("Parsing factory presets...")
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    print(f"  {len(records)} records built")

    _OUTPUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"  Written to {_OUTPUT_PATH}")

    client = chromadb.PersistentClient(path=str(_PERSIST_DIR))

    with contextlib.suppress(Exception):
        client.delete_collection(_COLLECTION_NAME)

    collection = client.create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids, documents, metadatas = [], [], []
    seen: set[str] = set()
    for record in records:
        name = record["preset_name"]
        if name in seen:
            continue
        seen.add(name)
        tag_str = " ".join(record["tags"])
        doc = f"{tag_str} -- {name}" if tag_str else name
        ids.append(name)
        documents.append(doc)
        metadatas.append({"preset_name": name})

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  {len(ids)} presets indexed into '{_COLLECTION_NAME}' -> {_PERSIST_DIR}")


if __name__ == "__main__":
    main()
