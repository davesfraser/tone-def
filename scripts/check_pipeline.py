"""Check that all pipeline artefacts are present and populated.

Run this before starting the app to confirm everything is in order, or after
a fresh clone to see what still needs to be built.

Usage:
    uv run python scripts/check_pipeline.py
"""

import sys
from pathlib import Path

from tonedef.health import (
    check_chromadb,
    check_env,
    check_files,
    check_schema_integrity,
    check_staleness,
)
from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED, GR7_PRESETS_DIR

# ---------------------------------------------------------------------------
# Script-specific declarations
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPTS_DIR.parent / "src" / "tonedef"

FILES: list[tuple[str, Path, int, str]] = [
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

STALENESS_MAP: list[tuple[Path, str, list[Path]]] = [
    (
        DATA_PROCESSED / "component_schema.json",
        "Component schema",
        [_SCRIPTS_DIR / "build_component_schema.py", _SRC_DIR / "ngrr_parser.py", GR7_PRESETS_DIR],
    ),
    (
        DATA_PROCESSED / "tag_catalogue.json",
        "Tag catalogue",
        [_SCRIPTS_DIR / "build_tag_catalogue.py", _SRC_DIR / "ngrr_parser.py", GR7_PRESETS_DIR],
    ),
    (
        DATA_PROCESSED / "gr_manual_chunks.json",
        "GR7 manual chunks",
        [_SCRIPTS_DIR / "build_manual_chunks.py", _SRC_DIR / "manual_parser.py"],
    ),
    (
        DATA_PROCESSED / "exemplar_store.json",
        "Exemplar store",
        [_SCRIPTS_DIR / "build_exemplar_index.py", _SRC_DIR / "ngrr_parser.py", GR7_PRESETS_DIR],
    ),
    (
        DATA_PROCESSED / "amp_cabinet_lookup.json",
        "Amp-cabinet lookup",
        [_SCRIPTS_DIR / "build_amp_cabinet_lookup.py", DATA_PROCESSED / "exemplar_store.json"],
    ),
    (
        DATA_PROCESSED / "chromadb",
        "ChromaDB index",
        [_SCRIPTS_DIR / "build_retrieval_index.py", DATA_PROCESSED / "gr_manual_chunks.json"],
    ),
    (
        DATA_PROCESSED / "parameter_annotations.json",
        "Parameter annotations",
        [_SCRIPTS_DIR / "build_parameter_annotations.py", DATA_PROCESSED / "component_schema.json"],
    ),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("ToneDef pipeline check")
    print("======================")

    all_issues: list[str] = []
    all_issues += check_files(FILES)
    all_issues += check_chromadb("gr_manual", 100, "uv run python scripts/build_retrieval_index.py")
    all_issues += check_schema_integrity()
    all_issues += check_env()

    # Staleness is advisory — warn but don't block the app from running.
    stale_warnings = check_staleness(STALENESS_MAP)

    print()
    if all_issues:
        print(f"\033[31mFound {len(all_issues)} issue(s):\033[0m")
        for issue in all_issues:
            print(f"  • {issue}")
        sys.exit(1)
    else:
        if stale_warnings:
            print(f"\033[33m{len(stale_warnings)} artefact(s) may be stale:\033[0m")
            for w in stale_warnings:
                print(f"  • {w}")
            print()
        print("\033[32mAll checks passed — app is ready to run.\033[0m")
        print("\n  uv run streamlit run app.py")


if __name__ == "__main__":
    main()
