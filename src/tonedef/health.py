"""Pipeline health checks — verify artefacts, staleness, and environment."""

from __future__ import annotations

import json
import os
from pathlib import Path

from tonedef.paths import DATA_PROCESSED
from tonedef.settings import settings

# ---------------------------------------------------------------------------
# ANSI markers
# ---------------------------------------------------------------------------

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def newest_mtime(*paths: Path) -> float:
    """Return the newest mtime across all given *paths*.

    For directories, checks all files recursively.
    Silently returns ``0.0`` for paths that don't exist.
    """
    newest = 0.0
    for p in paths:
        if not p.exists():
            continue
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file():
                    newest = max(newest, child.stat().st_mtime)
        else:
            newest = max(newest, p.stat().st_mtime)
    return newest


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_files(
    files: list[tuple[str, Path, int, str]],
) -> list[str]:
    """Verify that expected data files exist and meet minimum size."""
    issues: list[str] = []
    print("\nData files")
    print("----------")
    for label, path, min_bytes, fix in files:
        if not path.exists():
            print(f"  {FAIL}  {label}: MISSING")
            issues.append(f"{label}: run  {fix}")
        else:
            size = os.path.getsize(path)
            if size < min_bytes:
                print(f"  {WARN}  {label}: suspiciously small ({size:,} bytes)")
                issues.append(f"{label}: may be empty — run  {fix}")
            else:
                print(f"  {OK}  {label} ({size:,} bytes)")
    return issues


def check_chromadb(
    collection_name: str,
    min_docs: int,
    fix_command: str,
) -> list[str]:
    """Verify that the ChromaDB manual-chunks collection is populated."""
    issues: list[str] = []
    print("\nChromaDB collections")
    print("--------------------")
    try:
        import chromadb  # type: ignore[import-untyped]

        from tonedef.retriever import collection_path

        client = chromadb.PersistentClient(path=str(collection_path()))
        existing = {c.name for c in client.list_collections()}

        if collection_name not in existing:
            print(f"  {FAIL}  ChromaDB manual chunks: collection missing")
            issues.append(f"ChromaDB manual chunks: run  {fix_command}")
        else:
            col = client.get_collection(collection_name)
            count = col.count()
            if count < min_docs:
                print(
                    "  "
                    f"{WARN}  ChromaDB manual chunks: only {count} documents "
                    f"(expected ≥{min_docs})"
                )
                issues.append(f"ChromaDB manual chunks: re-run  {fix_command}")
            else:
                print(f"  {OK}  ChromaDB manual chunks ({count:,} documents)")
    except Exception as exc:
        print(f"  {WARN}  Could not connect to ChromaDB: {exc}")
        issues.append("ChromaDB: run build_retrieval_index.py")
    return issues


def check_schema_integrity() -> list[str]:
    """Verify component schema and amp-cabinet lookup can be loaded."""
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


def check_env() -> list[str]:
    """Verify that required environment variables are configured."""
    issues: list[str] = []
    print("\nEnvironment")
    print("-----------")
    api_key = settings.anthropic_api_key.get_secret_value()

    if api_key and api_key.startswith("sk-ant-"):
        print(f"  {OK}  ANTHROPIC_API_KEY: set")
    else:
        print(f"  {FAIL}  ANTHROPIC_API_KEY: not set")
        issues.append("ANTHROPIC_API_KEY: add to .env")
    return issues


def check_staleness(
    staleness_map: list[tuple[Path, str, list[Path]]],
) -> list[str]:
    """Warn when artefacts are older than their source dependencies."""
    issues: list[str] = []
    print("\nStaleness")
    print("---------")
    for artifact_path, label, deps in staleness_map:
        if not artifact_path.exists():
            continue
        artifact_mtime = newest_mtime(artifact_path)
        dep_mtime = newest_mtime(*deps)
        if dep_mtime > artifact_mtime:
            stale_deps = [p.name for p in deps if p.exists() and newest_mtime(p) > artifact_mtime]
            print(f"  {WARN}  {label}: may be stale (newer: {', '.join(stale_deps)})")
            issues.append(f"{label}: may be stale — rebuild may be needed")
        else:
            print(f"  {OK}  {label}")
    return issues
