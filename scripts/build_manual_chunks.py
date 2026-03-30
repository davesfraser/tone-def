"""
build_manual_chunks.py
----------------------
Extracts per-component text chunks from the Guitar Rig 7 manual PDF and
writes them to data/external/gr_manual_chunks.json.

Source: Guitar Rig 7 Manual (English)
File:   data/external/Guitar_Rig_7_Manual_English_07_09_23.pdf

Usage
-----
    uv run python scripts/build_manual_chunks.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from tonedef.manual_parser import extract_full_text, parse_chunks
from tonedef.paths import DATA_EXTERNAL

MANUAL_PDF = DATA_EXTERNAL / "Guitar_Rig_7_Manual_English_07_09_23.pdf"
OUTPUT_PATH = DATA_EXTERNAL / "gr_manual_chunks.json"


def main() -> None:
    if not MANUAL_PDF.exists():
        print(f"Manual PDF not found: {MANUAL_PDF}")
        print("Place the Guitar Rig 7 manual PDF at that path and re-run.")
        sys.exit(1)

    print(f"Extracting manual chunks from {MANUAL_PDF.name}")

    full_text = extract_full_text(MANUAL_PDF)
    chunks = parse_chunks(full_text)

    by_category = Counter(v["category"] for v in chunks.values())

    print(f"\nExtracted {len(chunks)} components")
    print("\nBy category:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        print(f"  {cat or 'Unknown':<20} {count}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"\nWritten to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
