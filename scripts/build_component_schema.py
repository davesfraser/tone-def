"""
build_component_schema.py
-------------------------
Parses all .ngrr preset files in data/external and writes the component
schema catalogue to data/processed/component_schema.json.

Usage:
    uv run python scripts/build_component_schema.py
"""

import json
import sys
from pathlib import Path

from tonedef.ngrr_parser import (
    extract_preset_name,
    extract_xml2,
    finalise_catalogue,
    merge_into_catalogue,
    parse_non_fix_components,
)
from tonedef.paths import DATA_PROCESSED
from tonedef.settings import settings

PRESET_FILE_PATH = Path(settings.gr7_presets_dir)
if not PRESET_FILE_PATH.exists():
    print("ERROR: GR7_PRESETS_DIR not set or does not exist — see .env.example")
    sys.exit(1)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
output_path = DATA_PROCESSED / "component_schema.json"

print("Building component schema catalogue")
print(f"Source: {PRESET_FILE_PATH}")
print(f"Output: {output_path}")
print()

preset_files = sorted(PRESET_FILE_PATH.glob("*.ngrr"))

if not preset_files:
    print("No .ngrr files found in data/external.")
    sys.exit(1)

print(f"Found {len(preset_files)} preset file(s)")

catalogue = {}

for path in preset_files:
    preset_name = extract_preset_name(path)
    print(f"  Parsing: {preset_name} ({path.name})")

    xml2 = extract_xml2(path)
    if xml2 is None:
        print("    Skipping - could not extract XML2")
        continue

    components = parse_non_fix_components(xml2)

    if not components:
        print("    No signal chain components found")
        continue

    print(f"    Found {len(components)} component(s)")
    catalogue = merge_into_catalogue(catalogue, components, preset_name)

catalogue = finalise_catalogue(catalogue)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(catalogue, f, indent=2, ensure_ascii=False)

print()
print("Catalogue complete:")
print(f"  Unique components: {len(catalogue)}")
print(f"  Output: {output_path}")
print()
print("Components found:")
for name, entry in catalogue.items():
    print(
        f"  [{entry['component_id']:>6}] {name:<30} "
        f"{len(entry['parameters'])} params, "
        f"seen in {entry['occurrence_count']} preset(s)"
    )
