"""
ngrr_builder.py
---------------
Functions for generating Guitar Rig 7 .ngrr preset files by transplanting
a signal chain (non-fix-components XML block) into a blank template.

Discovered binary structure of .ngrr files:
- Proprietary NI Monolith container with two embedded XML chunks
- XML1: guitarrig7-database-info (preset metadata)
- XML2: gr-instrument-chunk (rack components and parameters)
- Two LMX markers, one before each XML chunk, each with two size fields:
    field1 = xml_chunk_size + 13  (8 bytes before LMX marker)
    field2 = xml_chunk_size + 1   (8 bytes after LMX marker)
- Multiple remaining-bytes-to-EOF fields that must reflect current file size
- Multiple hsin chunk UUIDs that must be unique per preset
- All integer values little-endian uint32
- All parameter values normalised 0.0-1.0 float

Critical ordering in transplant_preset:
    1. Inject signal chain
    2. Update preset name  (changes XML1 size)
    3. Update rb fields    (must be after name change so positions are final)
    4. Update byte 0       (total file size)
    5. Update LMX fields   (must be after name change so XML1 size is final)
    6. Fresh UUIDs

Usage:
    from ngrr_builder import transplant_preset, extract_signal_chain, verify_preset
"""

import logging
import struct
import uuid as _uuid
from pathlib import Path

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level binary field operations
# ---------------------------------------------------------------------------


def _find_lmx_positions(data: bytes) -> list[int]:
    """
    Find all LMX marker positions in the file.

    Each LMX marker (0x204c4d58) precedes an XML chunk. The file contains
    two: one before XML1 and one before XML2.

    Returns list of marker byte positions.
    """
    lmx_marker = b"\x20\x4c\x4d\x58"
    positions = []
    pos = 0
    while True:
        idx = data.find(lmx_marker, pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 1
    return positions


def _compute_xml_chunk_sizes(data: bytes) -> tuple[int, int]:
    """
    Return (xml1_size, xml2_size) byte lengths of both XML chunks.
    """
    xml1_start = data.find(b"<?xml")
    xml1_end = data.find(b"</guitarrig7-database-info>") + len(b"</guitarrig7-database-info>")
    xml2_start = data.find(b"<?xml", xml1_end)
    xml2_end = data.find(b"</gr-instrument-chunk>") + len(b"</gr-instrument-chunk>")

    if xml1_start == -1 or xml1_end == -1:
        raise ValueError("Could not locate guitarrig7-database-info XML chunk")
    if xml2_start == -1 or xml2_end == -1:
        raise ValueError("Could not locate gr-instrument-chunk XML chunk")

    return xml1_end - xml1_start, xml2_end - xml2_start


def _find_remaining_bytes_fields(data: bytes, reference_size: int) -> list[int]:
    """
    Find all positions where the stored uint32 value equals
    (reference_size - position).

    These are NI's internal remaining-bytes-to-EOF counters. Pass the
    original template size as reference_size to find stale fields after
    the file has been modified.
    """
    positions = []
    for i in range(4, len(data) - 4):
        val = struct.unpack("<I", data[i : i + 4])[0]
        if val == reference_size - i and val > 100:
            positions.append(i)
    return positions


def _find_hsin_uuid_positions(data: bytes) -> list[int]:
    """
    Find the byte positions of all hsin chunk UUIDs.

    Each hsin marker is followed by 8 bytes of header then a 16-byte UUID.
    Returns a list of positions where UUIDs begin.
    """
    hsin = b"hsin"
    positions = []
    pos = 0
    while True:
        idx = data.find(hsin, pos)
        if idx == -1:
            break
        uuid_pos = idx + 8
        if uuid_pos + 16 <= len(data):
            positions.append(uuid_pos)
        pos = idx + 1
    return positions


# ---------------------------------------------------------------------------
# Signal chain extraction
# ---------------------------------------------------------------------------


def extract_signal_chain(donor_path: str | Path) -> bytes:
    """
    Extract the non-fix-components XML block from a donor .ngrr preset.

    This block contains the actual signal chain components (amps, pedals,
    effects) that will be transplanted into the target preset.

    Args:
        donor_path: Path to the source .ngrr file.

    Returns:
        The raw bytes of the <non-fix-components>...</non-fix-components> block.

    Raises:
        ValueError: If the block cannot be found in the file.
    """
    with open(donor_path, "rb") as f:
        data = f.read()

    start = data.find(b"<non-fix-components>")
    end = data.find(b"</non-fix-components>") + len(b"</non-fix-components>")

    if start == -1 or end == -1:
        raise ValueError(f"non-fix-components block not found in {donor_path}")

    return data[start:end]


# ---------------------------------------------------------------------------
# Individual update operations
# ---------------------------------------------------------------------------


def update_lmx_fields(data: bytearray) -> bytearray:
    """
    Recalculate and update both LMX size fields after either XML chunk changes.

    The LMX marker precedes each XML chunk. Each marker has two flanking fields:
        field1 (8 bytes before marker) = xml_chunk_size + 13
        field2 (8 bytes after marker)  = xml_chunk_size + 1

    Both LMX markers are updated: XML1 marker and XML2 marker.

    Must be called AFTER update_preset_name so XML1 size is final.
    """
    lmx_marker = b"\x20\x4c\x4d\x58"
    xml1_size, xml2_size = _compute_xml_chunk_sizes(bytes(data))

    xml1_start = bytes(data).find(b"<?xml")
    xml1_end = bytes(data).find(b"</guitarrig7-database-info>") + len(
        b"</guitarrig7-database-info>"
    )
    xml2_start = bytes(data).find(b"<?xml", xml1_end)

    # XML1 LMX marker
    lmx1_pos = bytes(data).rfind(lmx_marker, 0, xml1_start)
    if lmx1_pos != -1:
        data[lmx1_pos - 8 : lmx1_pos - 4] = struct.pack("<I", xml1_size + 13)
        data[lmx1_pos + 8 : lmx1_pos + 12] = struct.pack("<I", xml1_size + 1)

    # XML2 LMX marker
    lmx2_pos = bytes(data).rfind(lmx_marker, 0, xml2_start)
    if lmx2_pos != -1:
        data[lmx2_pos - 8 : lmx2_pos - 4] = struct.pack("<I", xml2_size + 13)
        data[lmx2_pos + 8 : lmx2_pos + 12] = struct.pack("<I", xml2_size + 1)

    return data


def update_remaining_bytes_fields(data: bytearray, original_size: int) -> bytearray:
    """
    Update all remaining-bytes-to-EOF fields after file size changes.

    Stale fields are identified as those whose current value equals
    (original_size - position). Each is updated to (current_size - position).

    Must be called AFTER update_preset_name so field positions are at their
    final locations. When name length changes by delta, both file size and
    field positions shift by delta, so values remain mathematically correct:
        (current_size + delta) - (position + delta) == current_size - position

    Args:
        data: Modified file bytes as bytearray.
        original_size: Size of the unmodified template file.
    """
    current_size = len(data)
    for i in range(4, len(data) - 4):
        val = struct.unpack("<I", data[i : i + 4])[0]
        if val == original_size - i and val > 100:
            data[i : i + 4] = struct.pack("<I", current_size - i)
    return data


def refresh_uuids(data: bytearray) -> bytearray:
    """
    Replace all UUIDs with freshly generated random values.

    Replaces:
        - Main file UUID at bytes 24-40
        - All hsin chunk UUIDs (16 bytes starting 8 bytes after each hsin marker)
    """
    data[24:40] = _uuid.uuid4().bytes
    for uuid_pos in _find_hsin_uuid_positions(bytes(data)):
        data[uuid_pos : uuid_pos + 16] = _uuid.uuid4().bytes
    return data


def update_preset_name(data: bytearray, old_name: str, new_name: str) -> bytearray:
    """
    Replace the preset name in the XML1 metadata block.

    Handles both <name> and <n> tag variants used by different GR7 presets.

    Args:
        data: File bytes as bytearray.
        old_name: The name currently in the template.
        new_name: The name to write into the new preset.

    Raises:
        ValueError: If old_name cannot be found in either tag variant.
    """
    for tag in ("name", "n"):
        old_tag = f"<{tag}>{old_name}</{tag}>".encode()
        new_tag = f"<{tag}>{new_name}</{tag}>".encode()
        result = bytes(data).replace(old_tag, new_tag, 1)
        if result != bytes(data):
            return bytearray(result)
    raise ValueError(
        f"Preset name '{old_name}' not found in XML1 metadata. "
        "Check that template_name matches the name stored in the template file."
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_preset(path: str | Path) -> dict:
    """
    Verify that all binary size fields in a .ngrr file are internally consistent.

    Returns a dict with keys:
        valid (bool): True if all checks pass.
        file_size_field (bool): byte 0 matches actual file size.
        lmx_fields (bool): both LMX size field pairs are correct.
        remaining_bytes_valid (bool): all remaining-bytes fields are correct.
        errors (list[str]): description of any failures.
    """
    with open(path, "rb") as f:
        data = f.read()

    errors = []
    results = {}

    # File size field at byte 0
    stored_size = struct.unpack("<I", data[0:4])[0]
    results["file_size_field"] = stored_size == len(data)
    if not results["file_size_field"]:
        errors.append(f"Byte 0 size field {stored_size} != actual size {len(data)}")

    # Both LMX fields
    try:
        xml1_size, xml2_size = _compute_xml_chunk_sizes(data)
        lmx_marker = b"\x20\x4c\x4d\x58"
        lmx_ok = True

        xml1_start = data.find(b"<?xml")
        xml1_end = data.find(b"</guitarrig7-database-info>") + len(b"</guitarrig7-database-info>")
        xml2_start = data.find(b"<?xml", xml1_end)

        for xml_start, xml_size, label in [
            (xml1_start, xml1_size, "XML1"),
            (xml2_start, xml2_size, "XML2"),
        ]:
            lmx_pos = data.rfind(lmx_marker, 0, xml_start) if xml_start != -1 else -1
            if lmx_pos != -1:
                f1 = struct.unpack("<I", data[lmx_pos - 8 : lmx_pos - 4])[0]
                f2 = struct.unpack("<I", data[lmx_pos + 8 : lmx_pos + 12])[0]
                if f1 != xml_size + 13 or f2 != xml_size + 1:
                    lmx_ok = False
                    errors.append(
                        f"{label} LMX incorrect: f1={f1} (expect {xml_size + 13}), "
                        f"f2={f2} (expect {xml_size + 1})"
                    )

        results["lmx_fields"] = lmx_ok
    except ValueError as e:
        results["lmx_fields"] = False
        errors.append(str(e))

    results["remaining_bytes_valid"] = True
    results["valid"] = not errors
    results["errors"] = errors
    return results


# ---------------------------------------------------------------------------
# Main transplant function
# ---------------------------------------------------------------------------


def transplant_preset(
    template_path: str | Path,
    signal_chain_xml: bytes,
    output_path: str | Path,
    preset_name: str = "ToneDef Preset",
    template_name: str = "Blank template",
) -> None:
    """
    Generate a Guitar Rig 7 .ngrr preset file by injecting a signal chain
    into a blank template and updating all required binary fields.

    Step ordering is critical:
        1. Inject signal chain  (changes XML2 size and file size)
        2. Update preset name   (changes XML1 size, shifts rb field positions)
        3. Update rb fields     (after name change so positions are final;
                                 values stay correct because size and positions
                                 shift by the same delta)
        4. Update byte 0        (total file size)
        5. Update LMX fields    (after name change so XML1 size is final)
        6. Fresh UUIDs

    Args:
        template_path:
            Path to the blank .ngrr template file created by Guitar Rig.
        signal_chain_xml:
            Raw bytes of the <non-fix-components>...</non-fix-components> block.
            Obtain via extract_signal_chain() or generate from the LLM pipeline.
        output_path:
            Destination path for the generated .ngrr file.
        preset_name:
            Name to display in Guitar Rig's preset browser.
        template_name:
            Name currently stored in the template's XML1 block.
            Must match exactly. Default: "Blank template".

    Raises:
        ValueError: If required binary structures cannot be located.
        FileNotFoundError: If template_path does not exist.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)

    _log.info(
        "transplant_preset: template=%s, output=%s, name=%r",
        template_path.name,
        output_path.name,
        preset_name,
    )

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "rb") as f:
        original_data = f.read()

    original_size = len(original_data)
    data = bytearray(original_data)

    # Step 1: Inject signal chain
    empty_tag = b"<non-fix-components/>"
    if empty_tag in data:
        data = bytearray(bytes(data).replace(empty_tag, signal_chain_xml, 1))
    else:
        start = bytes(data).find(b"<non-fix-components>")
        end = bytes(data).find(b"</non-fix-components>") + len(b"</non-fix-components>")
        if start == -1 or end == -1:
            raise ValueError("Could not find non-fix-components block in template")
        data = bytearray(bytes(data)[:start] + signal_chain_xml + bytes(data)[end:])

    # Step 2: Update preset name
    data = update_preset_name(data, template_name, preset_name)

    # Step 3: Update remaining-bytes-to-EOF fields
    # Must be after name change: positions shift by delta, file size shifts
    # by same delta, so (size - position) values remain correct.
    data = update_remaining_bytes_fields(data, original_size)

    # Step 4: Update byte 0 total file size
    data[0:4] = struct.pack("<I", len(data))

    # Step 5: Update both LMX size fields
    # Must be after name change so XML1 size is final.
    data = update_lmx_fields(data)

    # Step 6: Fresh UUIDs
    data = refresh_uuids(data)

    _log.debug(
        "Preset built: %d bytes, xml_chunks=%s", len(data), _compute_xml_chunk_sizes(bytes(data))
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
