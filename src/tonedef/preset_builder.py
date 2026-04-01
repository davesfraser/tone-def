"""Preset assembly orchestration — build .ngrr files from component dicts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tonedef.component_mapper import load_schema
from tonedef.ngrr_builder import transplant_preset
from tonedef.paths import DATA_EXTERNAL
from tonedef.xml_builder import build_signal_chain_xml


def build_preset(components: list[dict], name: str) -> bytes:
    """Build a .ngrr preset file from mapped components and return the bytes.

    Args:
        components: Phase 2 component dicts (component_name, parameters, …).
        name: Human-readable preset name embedded in the .ngrr binary.

    Returns:
        Raw bytes of the assembled .ngrr file.
    """
    schema = load_schema()
    xml = build_signal_chain_xml(components, schema)

    with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    transplant_preset(
        template_path=DATA_EXTERNAL / "Blank_template.ngrr",
        signal_chain_xml=xml,
        output_path=tmp_path,
        preset_name=name,
    )
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


def auto_preset_name(query: str) -> str:
    """Generate a clean preset name from the user's query text.

    Args:
        query: Raw query string from the user.

    Returns:
        A title-cased, truncated preset name (max 50 chars before titling).
    """
    name = query.strip()[:50]
    for prefix in ("I want ", "i want ", "Give me ", "give me "):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name.strip().title() if name else "ToneDef Preset"
