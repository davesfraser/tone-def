"""
build_exemplar_index.py
-----------------------
Build the exemplar store used by tonedef.retriever.search_exemplars.

1. Parses all factory .ngrr presets via exemplar_store.build_exemplar_records
2. Writes data/processed/exemplar_store.json

Run once before using exemplar retrieval in map_components():
    uv run python scripts/build_exemplar_index.py
"""

import json

from tonedef.exemplar_store import build_exemplar_records
from tonedef.paths import DATA_PROCESSED, GR7_PRESETS_DIR

_PRESETS_DIR = GR7_PRESETS_DIR
_TAG_CATALOGUE_PATH = DATA_PROCESSED / "tag_catalogue.json"
_SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
_OUTPUT_PATH = DATA_PROCESSED / "exemplar_store.json"


def main() -> None:
    if not _PRESETS_DIR.exists():
        print("ERROR: GR7_PRESETS_DIR not set or does not exist — see .env.example")
        raise SystemExit(1)
    tag_catalogue: list[dict] = json.loads(_TAG_CATALOGUE_PATH.read_text(encoding="utf-8"))
    schema: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    print("Parsing factory presets...")
    records = build_exemplar_records(_PRESETS_DIR, tag_catalogue, schema)
    print(f"  {len(records)} records built")

    _OUTPUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"  Written to {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
