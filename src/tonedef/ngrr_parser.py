"""
ngrr_parser.py
--------------
Functions for parsing Guitar Rig 7 .ngrr preset files and extracting
component schema information.

These functions support building the component schema catalogue used by
the ToneDef mapping layer to translate LLM signal chain recommendations
into valid Guitar Rig preset XML.

Usage:
    from tonedef.ngrr_parser import (
        extract_xml2,
        extract_preset_name,
        parse_non_fix_components,
    )
"""

import statistics
from pathlib import Path
from xml.etree import ElementTree as ET


def extract_preset_name(path: str | Path) -> str:
    """
    Extract the preset display name from the XML1 metadata block.

    Handles both <n> and <name> tag variants used by different GR7 presets.
    Falls back to the filename stem if no name tag is found.

    Args:
        path: Path to the .ngrr file.

    Returns:
        The preset name as a string.
    """
    with open(path, "rb") as f:
        data = f.read()

    xml1_start = data.find(b"<?xml")
    xml1_end = data.find(b"</guitarrig7-database-info>") + len(b"</guitarrig7-database-info>")

    if xml1_start == -1 or xml1_end == -1:
        return Path(path).stem

    xml1 = data[xml1_start:xml1_end].decode("utf-8", errors="replace")

    for tag in ("name", "n"):
        start = xml1.find(f"<{tag}>")
        end = xml1.find(f"</{tag}>")
        if start != -1 and end != -1:
            return xml1[start + len(f"<{tag}>") : end].strip()

    return Path(path).stem


def _extract_xml_block(data: bytes, *, nth_xml_decl: int, end_tag: bytes) -> str | None:
    """Extract the *nth* XML block ending with *end_tag* from binary data.

    Parameters
    ----------
    data:
        Raw .ngrr file bytes.
    nth_xml_decl:
        Which ``<?xml`` declaration to match (1-indexed).
    end_tag:
        Closing tag bytes (e.g. ``b"</gr-instrument-chunk>"``).

    Returns
    -------
    str | None
        The XML block as a UTF-8 string, or ``None`` if not found.
    """
    pos = -1
    for _ in range(nth_xml_decl):
        pos = data.find(b"<?xml", pos + 1)
        if pos == -1:
            return None
    end = data.find(end_tag, pos)
    if end == -1:
        return None
    end += len(end_tag)
    return data[pos:end].decode("utf-8", errors="replace")


def extract_xml2(path: str | Path) -> str | None:
    """
    Extract the gr-instrument-chunk XML block from an .ngrr binary file.

    Args:
        path: Path to the .ngrr file.

    Returns:
        The XML2 content as a UTF-8 string, or None if not found.
    """
    with open(path, "rb") as f:
        data = f.read()

    return _extract_xml_block(data, nth_xml_decl=2, end_tag=b"</gr-instrument-chunk>")


def parse_non_fix_components(xml2: str) -> list[dict]:
    """
    Parse the non-fix-components block from XML2 and return a list of
    component dicts representing the signal chain.

    Fix-components (tuner, metronome, I/O routing) are excluded — only
    user-placed signal chain components are returned.

    Each returned dict has the form:
        {
            "component_name": "Tweed Delight",
            "component_id": 79000,
            "parameters": [
                {
                    "param_id": "vb",
                    "param_name": "Bright",
                    "value": 0.64,
                },
                ...
            ]
        }

    Args:
        xml2: The gr-instrument-chunk XML string from extract_xml2().

    Returns:
        List of component dicts. Empty list if no signal chain components
        found or if XML is malformed.
    """
    try:
        root = ET.fromstring(xml2)
    except ET.ParseError:
        return []

    non_fix = root.find(".//non-fix-components")
    if non_fix is None:
        return []

    components = []
    for component in non_fix.findall("component"):
        name = component.get("name", "")
        raw_id = component.get("id", "0")

        try:
            comp_id = int(raw_id)
        except ValueError:
            comp_id = 0

        parameters = []
        for param in component.findall(".//parameter"):
            raw_value = param.get("value", "0")
            try:
                value = float(raw_value)
            except ValueError:
                value = 0.0

            parameters.append(
                {
                    "param_id": param.get("id", ""),
                    "param_name": param.get("name", ""),
                    "value": value,
                }
            )

        components.append(
            {
                "component_name": name,
                "component_id": comp_id,
                "parameters": parameters,
            }
        )

    return components


def merge_into_catalogue(
    catalogue: dict,
    components: list[dict],
    preset_name: str,
) -> dict:
    """
    Merge a list of parsed components into the running catalogue.

    For each component, creates a new catalogue entry if not seen before,
    or updates the existing entry with any new parameter values and preset
    references.

    Catalogue entries have the form:
        {
            "component_name": "Tweed Delight",
            "component_id": 79000,
            "parameters": [
                {
                    "param_id": "vb",
                    "param_name": "Bright",
                    "default_value": 0.5,
                    "seen_values": [0.64, 0.5, 0.72]
                },
                ...
            ],
            "seen_in_presets": ["EC - Beano", "Blues Clean"],
            "occurrence_count": 2
        }

    Args:
        catalogue: The running catalogue dict, keyed by component_name.
                   Pass an empty dict to start a new catalogue.
        components: Output of parse_non_fix_components() for one preset.
        preset_name: Display name of the preset being merged.

    Returns:
        The updated catalogue dict.
    """
    for comp in components:
        name = comp["component_name"]

        if name not in catalogue:
            catalogue[name] = {
                "component_name": name,
                "component_id": comp["component_id"],
                "parameters": {},
                "seen_in_presets": [],
                "occurrence_count": 0,
            }

        entry = catalogue[name]
        entry["occurrence_count"] += 1

        if preset_name not in entry["seen_in_presets"]:
            entry["seen_in_presets"].append(preset_name)

        for param in comp["parameters"]:
            pid = param["param_id"]
            if pid not in entry["parameters"]:
                entry["parameters"][pid] = {
                    "param_id": pid,
                    "param_name": param["param_name"],
                    "seen_values": [param["value"]],
                }
            else:
                entry["parameters"][pid]["seen_values"].append(param["value"])

    return catalogue


def _compute_mode(values: list[float]) -> tuple[float, int]:
    """
    Return (mode_value, mode_count) for a list of floats.

    Values are rounded to 6 decimal places before counting so that
    minor floating-point differences don't fragment the distribution.
    """
    from collections import Counter

    rounded = [round(v, 6) for v in values]
    counter = Counter(rounded)
    mode_val, mode_count = counter.most_common(1)[0]
    return mode_val, mode_count


def finalise_catalogue(catalogue: dict) -> dict:
    """
    Convert the internal catalogue format to the final serialisable format.

    Replaces raw seen_values lists with summary statistics.  ``default_value``
    is set to the **mode** of all observed values when the mode accounts for
    at least 15 % of observations, otherwise the **median** is used as a
    safer fallback for high-cardinality continuous parameters.
    """
    finalised = {}
    for name in sorted(catalogue.keys()):
        entry = dict(catalogue[name])
        params = []
        for param in entry["parameters"].values():
            values = param["seen_values"]
            mode_val, mode_count = _compute_mode(values)
            total = len(values)
            median_val = round(statistics.median(values), 6)

            # Use mode when it represents a meaningful cluster (>=15%)
            default = mode_val if mode_count / total >= 0.15 else median_val

            summary: dict = {
                "param_id": param["param_id"],
                "param_name": param["param_name"],
                "default_value": default,
            }
            if total > 1:
                sorted_vals = sorted(values)
                summary["stats"] = {
                    "count": total,
                    "min": round(min(values), 6),
                    "max": round(max(values), 6),
                    "mean": round(statistics.mean(values), 6),
                    "median": median_val,
                    "p25": round(sorted_vals[total // 4], 6),
                    "p75": round(sorted_vals[3 * total // 4], 6),
                    "mode": mode_val,
                    "mode_count": mode_count,
                }
            else:
                summary["stats"] = {
                    "count": 1,
                    "min": values[0],
                    "max": values[0],
                    "mean": values[0],
                    "median": values[0],
                    "p25": values[0],
                    "p75": values[0],
                    "mode": values[0],
                    "mode_count": 1,
                }
            params.append(summary)
        entry["parameters"] = params
        finalised[name] = entry
    return finalised


def extract_xml1(path: str | Path) -> str | None:
    """
    Extract the guitarrig7-database-info XML block from an .ngrr binary file.

    Args:
        path: Path to the .ngrr file.

    Returns:
        The XML1 content as a UTF-8 string, or None if not found.
    """
    with open(path, "rb") as f:
        data = f.read()

    return _extract_xml_block(data, nth_xml_decl=1, end_tag=b"</guitarrig7-database-info>")


# Tag categories to include - Amplifiers excluded as redundant with component mapping
INCLUDED_TAG_ROOTS = {"Characters", "FX Types", "Genres", "Input Sources"}


def parse_preset_metadata(xml1: str) -> dict:
    """
    Parse the guitarrig7-database-info XML block and return preset metadata.

    Extracts name, author, comment, and tags. Tags are filtered to exclude
    the Amplifiers category which is redundant with component mapping.

    Each tag entry has:
        value      - display value (e.g. "Rock")
        path       - full hierarchical path (e.g. "Genres > Rock")
        root       - top-level category (e.g. "Genres")

    Args:
        xml1: The guitarrig7-database-info XML string from extract_xml1().

    Returns:
        Dict with keys: name, author, comment, tags, is_factory.
    """
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(xml1)
    except ET.ParseError:
        return {}

    soundinfo = root.find(".//soundinfo")
    if soundinfo is None:
        return {}

    props = soundinfo.find("properties")
    name = ""
    author = ""
    comment = ""

    if props is not None:
        for tag in ("name", "n"):
            el = props.find(tag)
            if el is not None and el.text:
                name = el.text.strip()
                break
        author_el = props.find("author")
        if author_el is not None and author_el.text:
            author = author_el.text.strip()
        comment_el = props.find("comment")
        if comment_el is not None and comment_el.text:
            comment = comment_el.text.strip()

    tags = []
    is_factory = False

    for attr in root.findall(".//attribute"):
        value_el = attr.find("value")
        user_set_el = attr.find("user-set")

        if value_el is None or not value_el.text:
            continue

        value = value_el.text.strip()

        # Detect factory flag
        if value == "factory":
            is_factory = True
            continue

        # Skip bare category headers and utility tags
        if value in ("Effect", "curated", "UserSpace"):
            continue

        if user_set_el is None or not user_set_el.text:
            continue

        user_set = user_set_el.text.strip()

        # Parse the hierarchical path — tab-separated after RP://
        if not user_set.startswith("RP://"):
            continue

        path_parts = user_set[5:].split("\t")
        root_category = path_parts[0].strip()

        if root_category not in INCLUDED_TAG_ROOTS:
            continue

        # Skip bare root category entries (e.g. just "RP://Genres")
        if len(path_parts) < 2:
            continue

        # Build human-readable path
        human_path = " > ".join(p.strip() for p in path_parts)

        tags.append(
            {
                "value": value,
                "path": human_path,
                "root": root_category,
            }
        )

    return {
        "name": name,
        "author": author,
        "comment": comment,
        "tags": tags,
        "is_factory": is_factory,
    }


def merge_tags_into_catalogue(catalogue: dict, metadata: dict) -> dict:
    """
    Merge parsed preset metadata into the running tag catalogue.

    Catalogue entries have the form:
        {
            "value": "Rock",
            "root": "Genres",
            "path": "Genres > Rock",
            "occurrence_count": 42,
            "seen_in_presets": ["80s Stadium Rig", ...]
        }

    Args:
        catalogue: Running tag catalogue keyed by (root, value) tuple string.
        metadata: Output of parse_preset_metadata() for one preset.

    Returns:
        Updated catalogue dict.
    """
    preset_name = metadata.get("name", "")

    for tag in metadata.get("tags", []):
        key = f"{tag['root']}::{tag['value']}"

        if key not in catalogue:
            catalogue[key] = {
                "value": tag["value"],
                "root": tag["root"],
                "path": tag["path"],
                "occurrence_count": 0,
                "seen_in_presets": [],
            }

        entry = catalogue[key]
        entry["occurrence_count"] += 1
        if preset_name and preset_name not in entry["seen_in_presets"]:
            entry["seen_in_presets"].append(preset_name)

    return catalogue


def finalise_tag_catalogue(catalogue: dict) -> dict:
    """
    Sort and finalise the tag catalogue for serialisation.

    Sorts by root category then by occurrence count descending so the
    most common tags appear first within each category.

    Args:
        catalogue: Running catalogue from merge_tags_into_catalogue().

    Returns:
        Finalised catalogue as a list of tag entries sorted by root and frequency.
    """
    entries = list(catalogue.values())
    entries.sort(key=lambda e: (e["root"], -e["occurrence_count"]))
    return entries
