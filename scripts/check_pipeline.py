"""Check that all pipeline artefacts are present and populated.

Run this before starting the app to confirm everything is in order, or after
a fresh clone to see what still needs to be built.

Usage:
    uv run python scripts/check_pipeline.py
"""

import json
import os
import sys

from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED

# ---------------------------------------------------------------------------
# Expected artefacts
# ---------------------------------------------------------------------------

# (label, path, minimum_size_bytes, fix_command)
FILES: list[tuple[str, object, int, str]] = [
    (
        "Component schema",
        DATA_PROCESSED / "component_schema.json",
        100_000,
        "uv run python scripts/build_component_schema.py",
    ),
    (
        "Tag catalogue",
        DATA_PROCESSED / "tag_catalogue.json",
        10_000,
        "uv run python scripts/build_tag_catalogue.py",
    ),
    (
        "GR7 manual chunks",
        DATA_PROCESSED / "gr_manual_chunks.json",
        50_000,
        "uv run python scripts/build_manual_chunks.py",
    ),
    (
        "Amp-cabinet lookup",
        DATA_PROCESSED / "amp_cabinet_lookup.json",
        500,
        "uv run python scripts/build_amp_cabinet_lookup.py",
    ),
    (
        "Exemplar store",
        DATA_PROCESSED / "exemplar_store.json",
        500_000,
        "uv run python scripts/build_exemplar_index.py",
    ),
    (
        "Blank template preset",
        DATA_EXTERNAL / "Blank_template.ngrr",
        1_000,
        "— source file required (not generated)",
    ),
]

# (label, collection_name, minimum_docs, fix_command)
COLLECTIONS: list[tuple[str, str, int, str]] = [
    (
        "ChromaDB manual chunks",
        "gr_manual",
        100,
        "uv run python scripts/build_retrieval_index.py",
    ),
    (
        "ChromaDB exemplar presets",
        "gr_exemplars",
        1000,
        "uv run python scripts/build_exemplar_index.py",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"


def _check_files() -> list[str]:
    issues: list[str] = []
    print("\nData files")
    print("----------")
    for label, path, min_bytes, fix in FILES:
        if not path.exists():  # type: ignore[union-attr]
            print(f"  {FAIL}  {label}: MISSING")
            issues.append(f"{label}: run  {fix}")
        else:
            size = os.path.getsize(path)  # type: ignore[arg-type]
            if size < min_bytes:
                print(f"  {WARN}  {label}: suspiciously small ({size:,} bytes)")
                issues.append(f"{label}: may be empty — run  {fix}")
            else:
                print(f"  {OK}  {label} ({size:,} bytes)")
    return issues


def _check_chromadb() -> list[str]:
    issues: list[str] = []
    print("\nChromaDB collections")
    print("--------------------")
    try:
        import chromadb  # type: ignore[import-untyped]

        from tonedef.retriever import collection_path

        client = chromadb.PersistentClient(path=str(collection_path()))
        existing = {c.name for c in client.list_collections()}

        for label, name, min_docs, fix in COLLECTIONS:
            if name not in existing:
                print(f"  {FAIL}  {label}: collection missing")
                issues.append(f"{label}: run  {fix}")
            else:
                col = client.get_collection(name)
                count = col.count()
                if count < min_docs:
                    print(f"  {WARN}  {label}: only {count} documents (expected ≥{min_docs})")
                    issues.append(f"{label}: re-run  {fix}")
                else:
                    print(f"  {OK}  {label} ({count:,} documents)")
    except Exception as exc:
        print(f"  {WARN}  Could not connect to ChromaDB: {exc}")
        issues.append("ChromaDB: run build_retrieval_index.py and build_exemplar_index.py")
    return issues


def _check_schema_integrity() -> list[str]:
    issues: list[str] = []
    print("\nSchema integrity")
    print("----------------")
    schema_path = DATA_PROCESSED / "component_schema.json"
    lookup_path = DATA_PROCESSED / "amp_cabinet_lookup.json"

    if schema_path.exists():
        with open(schema_path) as f:
            schema: dict = json.load(f)
        print(f"  {OK}  Component schema: {len(schema)} components")
    else:
        print(f"  {FAIL}  Component schema: missing")
        issues.append("component_schema.json missing — run build_component_schema.py")

    if lookup_path.exists():
        with open(lookup_path) as f:
            lookup: dict = json.load(f)
        print(f"  {OK}  Amp-cabinet lookup: {len(lookup)} entries")
    else:
        print(f"  {FAIL}  Amp-cabinet lookup: missing")
        issues.append("amp_cabinet_lookup.json missing — run build_amp_cabinet_lookup.py")
    return issues


def _check_env() -> list[str]:
    issues: list[str] = []
    print("\nEnvironment")
    print("-----------")
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"  {FAIL}  ANTHROPIC_API_KEY: not set")
        issues.append("ANTHROPIC_API_KEY: add to .env")
    else:
        print(f"  {OK}  ANTHROPIC_API_KEY: set ({api_key[:8]}…)")
    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("ToneDef pipeline check")
    print("======================")

    all_issues: list[str] = []
    all_issues += _check_files()
    all_issues += _check_chromadb()
    all_issues += _check_schema_integrity()
    all_issues += _check_env()

    print()
    if all_issues:
        print(f"\033[31mFound {len(all_issues)} issue(s):\033[0m")
        for issue in all_issues:
            print(f"  • {issue}")
        sys.exit(1)
    else:
        print("\033[32mAll checks passed — app is ready to run.\033[0m")
        print("\n  uv run streamlit run app.py")


if __name__ == "__main__":
    main()
