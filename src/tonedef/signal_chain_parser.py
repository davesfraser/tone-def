# applied-skills: streamlit
"""Parse Phase 1 signal chain text into structured data for UI rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Parameter:
    """A single knob/setting on a unit."""

    name: str
    value: str
    explanation: str = ""


@dataclass
class Unit:
    """A single piece of gear in the signal chain."""

    name: str
    unit_type: str
    provenance: str  # DOCUMENTED, INFERRED, ESTIMATED
    gr_equivalent: str | None = None
    parameters: list[Parameter] = field(default_factory=list)


@dataclass
class Section:
    """A named group of units (e.g. SIGNAL CHAIN, CABINET AND MIC)."""

    title: str
    units: list[Unit] = field(default_factory=list)


@dataclass
class ParsedSignalChain:
    """Fully parsed Phase 1 output."""

    chain_type: str  # AMP_ONLY or FULL_PRODUCTION
    chain_type_reason: str
    sections: list[Section] = field(default_factory=list)
    why_it_works: str = ""
    playing_notes: str = ""
    confidence: str = ""  # HIGH, MEDIUM, LOW
    confidence_detail: str = ""
    tags_characters: list[str] = field(default_factory=list)
    tags_genres: list[str] = field(default_factory=list)


_SECTION_SEP = re.compile(r"━{3,}")
_CHAIN_TYPE = re.compile(
    r"Chain\s+type:\s*(AMP_ONLY|FULL_PRODUCTION)\s*[\u2014\u2013-]\s*(.+)",
    re.IGNORECASE,
)
_UNIT_LINE = re.compile(
    r"\[\s*(.+?)\s*—\s*(.+?)\s*\]\s*\[(DOCUMENTED|INFERRED|ESTIMATED)\]",
    re.IGNORECASE,
)
_GR_EQUIV = re.compile(r"→\s*\(Guitar\s+Rig:\s*(.+?)\)")
_PARAM_LINE = re.compile(r"◆\s*(.+?):\s*(.+)")
_EXPLANATION_LINE = re.compile(r"└─\s*(.+)")
_CONFIDENCE_LINE = re.compile(
    r"CONFIDENCE:\s*(HIGH|MEDIUM|LOW)\s*[\u2014\u2013-]\s*(.+)", re.IGNORECASE
)
_TAGS_CHARS = re.compile(r"Characters:\s*(.+)", re.IGNORECASE)
_TAGS_GENRES = re.compile(r"Genres:\s*(.+)", re.IGNORECASE)

# Section headers that contain equipment units
_EQUIPMENT_HEADERS = {
    "SIGNAL CHAIN",
    "GUITAR SIGNAL CHAIN",
    "CABINET AND MIC",
    "RECORDING CHAIN",
    "STUDIO PROCESSING",
}


def parse_signal_chain(raw: str) -> ParsedSignalChain:
    """Parse the raw Phase 1 ``<signal_chain>`` text into a structured object.

    Args:
        raw: The full Phase 1 output, optionally wrapped in
             ``<signal_chain>`` XML tags.

    Returns:
        A :class:`ParsedSignalChain` with all fields populated.
    """
    # Strip XML wrapper
    text = re.sub(r"</?signal_chain>", "", raw).strip()

    result = ParsedSignalChain(chain_type="", chain_type_reason="")

    # Extract chain type
    ct_match = _CHAIN_TYPE.search(text)
    if ct_match:
        result.chain_type = ct_match.group(1).upper()
        result.chain_type_reason = ct_match.group(2).strip()

    # Split into blocks by the ━━━ separator
    blocks = _SECTION_SEP.split(text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Try to extract special text sections
        _extract_why(block, result)
        _extract_playing_notes(block, result)
        _extract_confidence(block, result)
        _extract_tags(block, result)

        # Try to extract an equipment section
        _extract_equipment_section(block, result)

    return result


def _extract_why(block: str, result: ParsedSignalChain) -> None:
    match = re.search(r"WHY THIS CHAIN WORKS\s*\n(.+)", block, re.DOTALL)
    if match:
        text = match.group(1).strip()
        # Stop at the next known heading
        for heading in ("PLAYING NOTES", "CONFIDENCE:", "TAGS"):
            idx = text.find(heading)
            if idx != -1:
                text = text[:idx].strip()
        if text and not result.why_it_works:
            result.why_it_works = text


def _extract_playing_notes(block: str, result: ParsedSignalChain) -> None:
    match = re.search(r"PLAYING NOTES\s*\n(.+)", block, re.DOTALL)
    if match:
        text = match.group(1).strip()
        for heading in ("CONFIDENCE:", "TAGS"):
            idx = text.find(heading)
            if idx != -1:
                text = text[:idx].strip()
        if text and not result.playing_notes:
            result.playing_notes = text


def _extract_confidence(block: str, result: ParsedSignalChain) -> None:
    match = _CONFIDENCE_LINE.search(block)
    if match and not result.confidence:
        result.confidence = match.group(1).upper()
        result.confidence_detail = match.group(2).strip()


def _extract_tags(block: str, result: ParsedSignalChain) -> None:
    chars_match = _TAGS_CHARS.search(block)
    if chars_match and not result.tags_characters:
        result.tags_characters = [t.strip() for t in chars_match.group(1).split(",") if t.strip()]
    genres_match = _TAGS_GENRES.search(block)
    if genres_match and not result.tags_genres:
        result.tags_genres = [t.strip() for t in genres_match.group(1).split(",") if t.strip()]


def _extract_equipment_section(block: str, result: ParsedSignalChain) -> None:
    """Parse an equipment section (units with parameters) from a block."""
    lines = block.split("\n")

    # Find the section header
    header: str | None = None
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip().upper()
        for known in _EQUIPMENT_HEADERS:
            if stripped == known:
                header = known.title()
                content_start = i + 1
                break
        if header:
            break

    if header is None:
        return

    section = Section(title=header)
    current_unit: Unit | None = None
    current_param: Parameter | None = None

    for line in lines[content_start:]:
        # Stop if we hit a non-equipment heading
        stripped = line.strip()
        if stripped.upper() in (
            "WHY THIS CHAIN WORKS",
            "PLAYING NOTES",
            "TAGS",
        ) or stripped.upper().startswith("CONFIDENCE:"):
            break

        # Skip flow arrows and blank lines
        if stripped in ("↓", ""):
            continue

        # Unit line?
        unit_match = _UNIT_LINE.search(line)
        if unit_match:
            gr_eq = _GR_EQUIV.search(line)
            current_unit = Unit(
                name=unit_match.group(1).strip(),
                unit_type=unit_match.group(2).strip(),
                provenance=unit_match.group(3).upper(),
                gr_equivalent=gr_eq.group(1).strip() if gr_eq else None,
            )
            section.units.append(current_unit)
            current_param = None
            continue

        # Parameter line?
        param_match = _PARAM_LINE.search(line)
        if param_match and current_unit is not None:
            current_param = Parameter(
                name=param_match.group(1).strip(),
                value=param_match.group(2).strip(),
            )
            current_unit.parameters.append(current_param)
            continue

        # Explanation line?
        expl_match = _EXPLANATION_LINE.search(line)
        if expl_match and current_param is not None:
            current_param.explanation = expl_match.group(1).strip()
            continue

    if section.units:
        result.sections.append(section)
