"""
promote_component_mapping.py
----------------------------
Reads the human-reviewed component_mapping_review.csv, validates all entries,
logs corrections, and writes the final component_mapping.json to data/processed.

Expects the CSV to have been reviewed with reviewed=y set on checked rows.
Rows with corrected=y are logged separately as an audit trail.

Usage:
    uv run python scripts/promote_component_mapping.py
"""

import csv
import json
import sys

from tonedef.paths import DATA_INTERIM, DATA_PROCESSED

review_csv_path = DATA_INTERIM / "component_mapping_review.csv"
output_path = DATA_PROCESSED / "component_mapping.json"
schema_path = DATA_PROCESSED / "component_schema.json"

if not review_csv_path.exists():
    print(f"Review CSV not found: {review_csv_path}")
    print("Run generate_component_mapping.py first.")
    sys.exit(1)

with open(schema_path, encoding="utf-8") as f:
    schema = json.load(f)
known_components = set(schema.keys())

with open(review_csv_path, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

print(f"Loaded {len(rows)} rows from review CSV")

# Report review coverage
reviewed = [r for r in rows if r.get("reviewed", "").strip().lower() == "y"]
corrected = [r for r in rows if r.get("corrected", "").strip().lower() == "y"]
unreviewed = [r for r in rows if r.get("reviewed", "").strip().lower() != "y"]

print(f"  Reviewed:   {len(reviewed)}")
print(f"  Corrected:  {len(corrected)}")
print(f"  Unreviewed: {len(unreviewed)}")

if unreviewed:
    print(f"\nWarning: {len(unreviewed)} rows have not been marked as reviewed.")
    response = input("Promote anyway? (y/n): ").strip().lower()
    if response != "y":
        print("Aborted.")
        sys.exit(0)

# Validate all rows
errors = []
valid_confidence = {"documented", "inferred", "estimated"}
valid_types = {
    "tube amplifier",
    "solid state amplifier",
    "overdrive pedal",
    "distortion pedal",
    "fuzz pedal",
    "compressor pedal",
    "delay pedal",
    "reverb pedal",
    "modulation pedal",
    "equaliser",
    "noise gate",
    "cabinet simulation",
    "microphone",
    "utility",
}

for i, row in enumerate(rows, start=2):  # start=2 for header row
    if not row.get("hardware_name", "").strip():
        errors.append(f"Row {i}: missing hardware_name")
    if not row.get("component_name", "").strip():
        errors.append(f"Row {i}: missing component_name")
    if row.get("component_name", "").strip() not in known_components:
        errors.append(
            f"Row {i}: component_name '{row.get('component_name')}' not found in catalogue"
        )
    if row.get("confidence", "").strip() not in valid_confidence:
        errors.append(
            f"Row {i}: invalid confidence '{row.get('confidence')}' "
            f"- must be one of {valid_confidence}"
        )
    if row.get("hardware_type", "").strip() not in valid_types:
        errors.append(
            f"Row {i}: invalid hardware_type '{row.get('hardware_type')}' "
            f"- must be one of {valid_types}"
        )

if errors:
    print(f"\nValidation failed with {len(errors)} error(s):")
    for error in errors:
        print(f"  {error}")
    sys.exit(1)

print("\nValidation passed.")

# Log corrections
if corrected:
    print(f"\nCorrected rows ({len(corrected)}):")
    for row in corrected:
        print(f"  {row['hardware_name']} -> {row['component_name']} ({row['confidence']})")

# Build output - list of dicts, one per row, review columns stripped
output_rows = []
for row in rows:
    output_rows.append(
        {
            "hardware_name": row["hardware_name"].strip(),
            "hardware_type": row["hardware_type"].strip(),
            "software": row["software"].strip(),
            "component_name": row["component_name"].strip(),
            "component_id": int(row["component_id"]) if row["component_id"] else 0,
            "confidence": row["confidence"].strip(),
            "rationale": row["rationale"].strip(),
        }
    )

# Sort by software then hardware_name for readability
output_rows.sort(key=lambda r: (r["software"], r["hardware_name"]))

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_rows, f, indent=2, ensure_ascii=False)

print("\nPromotion complete:")
print(f"  {len(output_rows)} mapping rows written to {output_path}")
print(f"  {len({r['component_name'] for r in output_rows})} unique components covered")
print(f"  {len({r['hardware_name'] for r in output_rows})} unique hardware names mapped")
