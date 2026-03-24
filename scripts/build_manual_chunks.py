"""
build_manual_chunks.py
----------------------
Extracts per-component text chunks from the Guitar Rig 7 manual PDF and
writes them to data/external/gr_manual_chunks.json.

Each chunk contains the full component description and parameter list as
written by NI, making it the most authoritative source for hardware
identification in the mapping pipeline.

Source
------
Guitar Rig 7 Manual (English)
Author: Native Instruments GmbH
File:   data/external/Guitar_Rig_7_Manual_English_07_09_23.pdf
Note:   Component reference begins on page 89. Pages 1-88 are skipped.

Usage
-----
    uv run python scripts/build_manual_chunks.py
"""

import json
import re
import sys
from pathlib import Path

from tonedef.paths import DATA_EXTERNAL

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run: uv add pdfplumber")
    sys.exit(1)

MANUAL_PDF = DATA_EXTERNAL / "Guitar_Rig_7_Manual_English_07_09_23.pdf"
OUTPUT_PATH = DATA_EXTERNAL / "gr_manual_chunks.json"

COMPONENT_REFERENCE_START_PAGE = 89  # 1-indexed

# Category section headers in the manual — used to track current category
# and excluded from component name detection
CATEGORY_HEADERS = {
    "Amplifiers",
    "Cabinets",
    "Delay / Echo",
    "Distortion",
    "Dynamics",
    "Equalizer",
    "Filter",
    "Modulation",
    "Pitch",
    "Reverb",
    "Special FX",
    "Modifier",
    "Tools",
    "Legacy",
}

# Keywords that appear in the first sentence of a component description.
# Used to detect component name headings.
DESCRIPTION_KEYWORDS = [
    "models",
    "is a ",
    "provides",
    "enables",
    "combines",
    "recreates",
    "features",
    "expands",
    "serves",
    "brings",
    "degrades",
    "emulates",
    "includes",
    "offers",
    "produces",
]

# Lines that are clearly not component names
ARTIFACT_PATTERNS = [
    r"^accordingly\.",
    r"^information, refer",
    r"^stronger\.",
    r"^tuned for",
    r"^clicking",
    r"^when ",
    r"^if ",
]


def is_artifact(line: str) -> bool:
    return any(re.match(p, line.lower()) for p in ARTIFACT_PATTERNS)


def extract_full_text(pdf_path: Path, start_page: int) -> str:
    """Extract and clean text from the component reference section."""
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page - 1, len(pdf.pages)):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if not text:
                continue
            # Strip running page headers e.g. "COMPONENTS REFERENCE 82"
            lines = text.split("\n")
            cleaned = [
                line for line in lines if not re.match(r"^COMPONENTS REFERENCE \d+$", line.strip())
            ]
            full_text += "\n".join(cleaned) + "\n"
    return full_text


def parse_chunks(full_text: str) -> dict[str, dict]:
    """
    Parse component text into a dict keyed by component name.

    Each value has:
        category (str): The section this component belongs to
        text (str):     Full component description including parameter list
    """
    lines = full_text.split("\n")
    chunks = {}
    current_name = None
    current_lines = []
    current_category = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            if current_name:
                current_lines.append("")
            continue

        # Category header
        if stripped in CATEGORY_HEADERS:
            if current_name and not is_artifact(current_name):
                chunks[current_name] = {
                    "category": current_category,
                    "text": "\n".join(current_lines).strip(),
                }
            current_category = stripped
            current_name = None
            current_lines = []
            continue

        # Detect component name heading
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        is_component_start = (
            stripped
            and len(stripped) < 50
            and not stripped.startswith("•")
            and not stripped.startswith("▶")
            and not stripped.startswith("This")
            and stripped not in CATEGORY_HEADERS
            and not is_artifact(stripped)
            and any(kw in next_line.lower() for kw in DESCRIPTION_KEYWORDS)
        )

        if is_component_start:
            if current_name and not is_artifact(current_name):
                chunks[current_name] = {
                    "category": current_category,
                    "text": "\n".join(current_lines).strip(),
                }
            current_name = stripped
            current_lines = [stripped]
        elif current_name:
            current_lines.append(stripped)

    # Final component
    if current_name and not is_artifact(current_name):
        chunks[current_name] = {
            "category": current_category,
            "text": "\n".join(current_lines).strip(),
        }

    return chunks


def main() -> None:
    if not MANUAL_PDF.exists():
        print(f"Manual PDF not found: {MANUAL_PDF}")
        print("Place the Guitar Rig 7 manual PDF at that path and re-run.")
        sys.exit(1)

    print(f"Extracting manual chunks from {MANUAL_PDF.name}")
    print(f"Component reference starts at page {COMPONENT_REFERENCE_START_PAGE}")

    full_text = extract_full_text(MANUAL_PDF, COMPONENT_REFERENCE_START_PAGE)
    chunks = parse_chunks(full_text)

    from collections import Counter

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
