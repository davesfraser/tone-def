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

    xml2_start = data.find(b"<?xml", data.find(b"<?xml") + 1)
    xml2_end = data.find(b"</gr-instrument-chunk>") + len(b"</gr-instrument-chunk>")

    if xml2_start == -1 or xml2_end == -1:
        return None

    return data[xml2_start:xml2_end].decode("utf-8", errors="replace")


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
                    "default_value": param["value"],
                    "seen_values": [param["value"]],
                }
            else:
                if param["value"] not in entry["parameters"][pid]["seen_values"]:
                    entry["parameters"][pid]["seen_values"].append(param["value"])

    return catalogue


def finalise_catalogue(catalogue: dict) -> dict:
    """
    Convert the internal catalogue format to the final serialisable format.
    Replaces raw seen_values lists with summary statistics.
    """
    finalised = {}
    for name in sorted(catalogue.keys()):
        entry = dict(catalogue[name])
        params = []
        for param in entry["parameters"].values():
            values = param["seen_values"]
            summary = {
                "param_id": param["param_id"],
                "param_name": param["param_name"],
                "default_value": param["default_value"],
            }
            if len(values) > 1:
                summary["stats"] = {
                    "count": len(values),
                    "min": round(min(values), 6),
                    "max": round(max(values), 6),
                    "mean": round(statistics.mean(values), 6),
                    "median": round(statistics.median(values), 6),
                    "p25": round(sorted(values)[len(values) // 4], 6),
                    "p75": round(sorted(values)[3 * len(values) // 4], 6),
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
                }
            params.append(summary)
        entry["parameters"] = params
        finalised[name] = entry
    return finalised
