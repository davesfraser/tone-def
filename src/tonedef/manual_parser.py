"""Parser for the Guitar Rig 7 manual PDF.

Extracts per-component text chunks from the component reference section,
producing a dict keyed by component name with category and description text.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPONENT_REFERENCE_START_PAGE: int = 89  # 1-indexed page where components begin

CATEGORY_HEADERS: frozenset[str] = frozenset(
    {
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
)

# Keywords that appear in the first sentence of a component description.
DESCRIPTION_KEYWORDS: list[str] = [
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
_ARTIFACT_PATTERNS: list[str] = [
    r"^accordingly\.",
    r"^information, refer",
    r"^stronger\.",
    r"^tuned for",
    r"^clicking",
    r"^when ",
    r"^if ",
]

# Component names that belong to "EQ" in GR7 but appear under "Dynamics"
# in the manual PDF.  Override the inherited section category for these.
_EQ_COMPONENT_NAMES: frozenset[str] = frozenset(
    {
        "Custom EQ",
        "Equalizer Graphic",
        "Equalizer Parametric",
        "Equalizer Shelving",
        "Solid EQ",
    }
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_artifact(line: str) -> bool:
    """Return True if *line* matches a known non-component artifact pattern."""
    return any(re.match(p, line.lower()) for p in _ARTIFACT_PATTERNS)


def _resolve_category(component_name: str, section_category: str) -> str:
    """Return the correct GR7 category for *component_name*.

    The manual PDF nests EQ components inside the Dynamics section, but
    Guitar Rig 7 treats them as a separate "EQ" component type.  This
    function overrides the inherited section category when needed.
    """
    if component_name in _EQ_COMPONENT_NAMES:
        return "EQ"
    return section_category


def extract_full_text(pdf_path: Path, start_page: int = COMPONENT_REFERENCE_START_PAGE) -> str:
    """Extract and clean text from the component reference section of the PDF.

    Parameters
    ----------
    pdf_path:
        Path to the Guitar Rig 7 manual PDF.
    start_page:
        1-indexed page where the component reference begins.

    Returns
    -------
    str
        Concatenated cleaned text from *start_page* onwards.
    """
    if pdfplumber is None:  # pragma: no cover
        msg = "pdfplumber is required - install with: uv add pdfplumber"  # type: ignore[unreachable]
        raise ImportError(msg)

    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(start_page - 1, len(pdf.pages)):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
            cleaned = [
                line for line in lines if not re.match(r"^COMPONENTS REFERENCE \d+$", line.strip())
            ]
            full_text += "\n".join(cleaned) + "\n"
    return full_text


def parse_chunks(full_text: str) -> dict[str, dict[str, str]]:
    """Parse component text into a dict keyed by component name.

    Each value has:
        category (str): The section this component belongs to.
        text (str):     Full component description including parameter list.
    """
    lines = full_text.split("\n")
    chunks: dict[str, dict[str, str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    current_category: str | None = None

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
                    "category": _resolve_category(current_name, current_category or ""),
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
                    "category": _resolve_category(current_name, current_category or ""),
                    "text": "\n".join(current_lines).strip(),
                }
            current_name = stripped
            current_lines = [stripped]
        elif current_name:
            current_lines.append(stripped)

    # Final component
    if current_name and not is_artifact(current_name):
        chunks[current_name] = {
            "category": _resolve_category(current_name, current_category or ""),
            "text": "\n".join(current_lines).strip(),
        }

    return chunks
