"""
build_tag_catalogue.py
----------------------
Parses all .ngrr preset files in data/external and writes the tag
catalogue to data/processed/tag_catalogue.json.

The catalogue covers four tag categories:
    Characters  - tonal character (Clean, Distorted, Crunch, Spacious...)
    FX Types    - effect categories (Amps & Cabinets, Delay, Reverb...)
    Genres      - musical genre (Rock, Pop, Blues, Alternative...)
    Input Sources - instrument type (Guitar, Bass...)

The Amplifiers category is excluded as it is redundant with the
component mapping — amp identity is captured at finer grain there.

Usage:
    uv run python scripts/build_tag_catalogue.py
"""

import json
import sys
from collections import Counter

from tonedef.ngrr_parser import (
    extract_xml1,
    finalise_tag_catalogue,
    merge_tags_into_catalogue,
    parse_preset_metadata,
)
from tonedef.paths import DATA_PROCESSED, GR7_PRESETS_DIR

DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
PRESET_FILE_PATH = GR7_PRESETS_DIR
if not PRESET_FILE_PATH.exists():
    print("ERROR: GR7_PRESETS_DIR not set or does not exist — see .env.example")
    sys.exit(1)
output_path = DATA_PROCESSED / "tag_catalogue.json"

print("Building tag catalogue")
print(f"Source: {PRESET_FILE_PATH}")
print(f"Output: {output_path}")
print()

preset_files = sorted(PRESET_FILE_PATH.glob("*.ngrr"))

if not preset_files:
    print("No .ngrr files found in data/external.")
    sys.exit(1)

print(f"Found {len(preset_files)} preset file(s)")

catalogue = {}
skipped = 0
factory_count = 0

for path in preset_files:
    xml1 = extract_xml1(path)
    if xml1 is None:
        skipped += 1
        continue

    metadata = parse_preset_metadata(xml1)
    if not metadata:
        skipped += 1
        continue

    if metadata.get("is_factory"):
        factory_count += 1

    catalogue = merge_tags_into_catalogue(catalogue, metadata)

tag_list = finalise_tag_catalogue(catalogue)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(tag_list, f, indent=2, ensure_ascii=False)

print()
print("Tag catalogue complete:")
print(f"  Presets processed: {len(preset_files) - skipped}")
print(f"  Factory presets:   {factory_count}")
print(f"  Skipped:           {skipped}")
print(f"  Unique tags:       {len(tag_list)}")
print(f"  Output:            {output_path}")
print()

# Summary by category

by_root = Counter(t["root"] for t in tag_list)
print("Tags by category:")
for root, count in sorted(by_root.items()):
    print(f"  {root:<20} {count} unique values")
print()

print("Top 10 most common tags:")
top = sorted(tag_list, key=lambda t: -t["occurrence_count"])[:10]
for t in top:
    print(f"  {t['occurrence_count']:>5}x  {t['path']}")
