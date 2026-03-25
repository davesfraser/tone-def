"""
Tests for tonedef.ngrr_builder

Tests for pure functions that operate on bytearray / bytes without needing
real .ngrr files. The transplant_preset integration test uses the real blank
template present in data/external/.
"""

from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest

from tonedef.ngrr_builder import (
    refresh_uuids,
    update_preset_name,
    update_remaining_bytes_fields,
    verify_preset,
)
from tonedef.paths import DATA_EXTERNAL

# ---------------------------------------------------------------------------
# update_preset_name
# ---------------------------------------------------------------------------


def _make_xml1_bytes(name: str) -> bytearray:
    """Build minimal data containing a <name>...</name> tag."""
    content = f"prefix<name>{name}</name>suffix".encode()
    return bytearray(content)


def test_update_preset_name_replaces_name_tag() -> None:
    data = _make_xml1_bytes("Blank template")
    result = update_preset_name(data, "Blank template", "My Preset")
    assert b"<name>My Preset</name>" in bytes(result)


def test_update_preset_name_removes_old_name() -> None:
    data = _make_xml1_bytes("Blank template")
    result = update_preset_name(data, "Blank template", "My Preset")
    assert b"<name>Blank template</name>" not in bytes(result)


def test_update_preset_name_raises_if_not_found() -> None:
    data = _make_xml1_bytes("Other Name")
    with pytest.raises(ValueError, match="not found"):
        update_preset_name(data, "Missing Name", "New Name")


def test_update_preset_name_handles_n_tag_variant() -> None:
    data = bytearray(b"prefix<n>Short</n>suffix")
    result = update_preset_name(data, "Short", "Longer Name Here")
    assert b"<n>Longer Name Here</n>" in bytes(result)


def test_update_preset_name_returns_bytearray() -> None:
    data = _make_xml1_bytes("Template")
    result = update_preset_name(data, "Template", "New")
    assert isinstance(result, bytearray)


# ---------------------------------------------------------------------------
# update_remaining_bytes_fields
# ---------------------------------------------------------------------------


def _make_rb_data(size: int, field_position: int = 100) -> tuple[bytearray, int]:
    """
    Build a bytearray of `size` bytes with a valid remaining-bytes field
    at `field_position`. The field value is (size - field_position).
    """
    data = bytearray(size)
    rb_value = size - field_position
    # Only insert if the value would be > 100 (satisfies the filter in the function)
    assert rb_value > 100, "Choose a field_position far enough from the end"
    struct.pack_into("<I", data, field_position, rb_value)
    return data, rb_value


def test_update_remaining_bytes_updates_field() -> None:
    original_size = 2000
    data, _old_val = _make_rb_data(original_size)
    # Extend the data to simulate a larger file after signal chain injection
    data += bytearray(500)
    result = update_remaining_bytes_fields(data, original_size)
    field_pos = 100
    stored = struct.unpack("<I", bytes(result)[field_pos : field_pos + 4])[0]
    assert stored == len(result) - field_pos


def test_update_remaining_bytes_returns_bytearray() -> None:
    original_size = 2000
    data, _ = _make_rb_data(original_size)
    result = update_remaining_bytes_fields(data, original_size)
    assert isinstance(result, bytearray)


# ---------------------------------------------------------------------------
# refresh_uuids
# ---------------------------------------------------------------------------


def test_refresh_uuids_changes_main_uuid() -> None:
    data = bytearray(256)
    original_uuid = bytes(data[24:40])
    result = refresh_uuids(data)
    assert bytes(result[24:40]) != original_uuid


def test_refresh_uuids_returns_same_length() -> None:
    data = bytearray(256)
    result = refresh_uuids(data)
    assert len(result) == len(data)


def test_refresh_uuids_returns_bytearray() -> None:
    data = bytearray(256)
    result = refresh_uuids(data)
    assert isinstance(result, bytearray)


# ---------------------------------------------------------------------------
# transplant_preset integration test (requires blank template on disk)
# ---------------------------------------------------------------------------

_SIMPLE_SIGNAL_CHAIN = (
    b"<non-fix-components>"
    b'<component id="79000" name="Tweed Delight" uuid="AAAA">'
    b'<component-gui><view component-template-bank="" component-template-name=""'
    b' stored-view-mode="1" view-mode="1" visible="true"/></component-gui>'
    b'<component-audio version="2">'
    b'<parameters enable-automation="1" num-parameters="1" static-automation="0">'
    b'<parameter id="vb" name="Bright" value="0.640000">'
    b'<base-parameters remote-max="1.000000" remote-min="0.000000"/>'
    b"</parameter></parameters></component-audio></component>"
    b"</non-fix-components>"
)


@pytest.mark.skipif(
    not (DATA_EXTERNAL / "Blank_template.ngrr").exists(),
    reason="Blank_template.ngrr not present in data/external/",
)
def test_transplant_preset_produces_valid_file() -> None:
    from tonedef.ngrr_builder import transplant_preset

    template = DATA_EXTERNAL / "Blank_template.ngrr"
    with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        transplant_preset(
            template_path=template,
            signal_chain_xml=_SIMPLE_SIGNAL_CHAIN,
            output_path=out_path,
            preset_name="Test Preset",
        )
        result = verify_preset(out_path)
        assert result["valid"], f"Verification errors: {result['errors']}"
    finally:
        out_path.unlink(missing_ok=True)


@pytest.mark.skipif(
    not (DATA_EXTERNAL / "Blank_template.ngrr").exists(),
    reason="Blank_template.ngrr not present in data/external/",
)
def test_transplant_preset_raises_for_missing_template() -> None:
    from tonedef.ngrr_builder import transplant_preset

    with pytest.raises(FileNotFoundError):
        transplant_preset(
            template_path=Path("/nonexistent/template.ngrr"),
            signal_chain_xml=_SIMPLE_SIGNAL_CHAIN,
            output_path=Path("/tmp/out.ngrr"),
        )
