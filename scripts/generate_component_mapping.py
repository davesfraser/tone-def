"""
generate_component_mapping.py
-----------------------------
Sends the Guitar Rig 7 component list to Claude and generates a first-pass
hardware-to-component mapping table.

Outputs:
    data/interim/component_mapping_raw.json   - structured LLM output for code
    data/interim/component_mapping_review.csv - long-format table for human review

The CSV is the review artefact. Edit it directly, set reviewed=y and
corrected=y on changed rows, then run promote_component_mapping.py.

Usage:
    uv run python scripts/generate_component_mapping.py
"""

import csv
import json
import sys

import anthropic

from tonedef.paths import DATA_INTERIM, DATA_PROCESSED
from tonedef.prompts import MAPPING_PROMPT

DATA_INTERIM.mkdir(parents=True, exist_ok=True)

schema_path = DATA_PROCESSED / "component_schema.json"
raw_output_path = DATA_INTERIM / "component_mapping_raw.json"
review_csv_path = DATA_INTERIM / "component_mapping_review.csv"

with open(schema_path, encoding="utf-8") as f:
    schema = json.load(f)

component_names = sorted(schema.keys())
print(f"Loaded {len(component_names)} components from catalogue")

component_list = "\n".join(f"- {name}" for name in component_names)
prompt = MAPPING_PROMPT.format(component_list=component_list)

print("Calling Claude API...")
client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8000,
    messages=[{"role": "user", "content": prompt}],
)

raw_text = message.content[0].text.strip()

# Strip markdown code fences if present
if raw_text.startswith("```"):
    raw_text = raw_text.split("\n", 1)[1]
    raw_text = raw_text.rsplit("```", 1)[0].strip()

try:
    mappings = json.loads(raw_text)
except json.JSONDecodeError as e:
    print(f"Failed to parse LLM response as JSON: {e}")
    print("Raw response saved to data/interim/component_mapping_error.txt")
    error_path = DATA_INTERIM / "component_mapping_error.txt"
    error_path.write_text(raw_text, encoding="utf-8")
    sys.exit(1)

print(f"Received {len(mappings)} mappings from LLM")

# Enrich with component_id from catalogue
id_lookup = {name: entry["component_id"] for name, entry in schema.items()}
for mapping in mappings:
    mapping["component_id"] = id_lookup.get(mapping["component_name"], 0)

# Write raw JSON
with open(raw_output_path, "w", encoding="utf-8") as f:
    json.dump(mappings, f, indent=2, ensure_ascii=False)
print(f"Raw JSON written to {raw_output_path}")

# Write long-format review CSV
# One row per hardware alias per component
csv_rows = []
for mapping in mappings:
    for alias in mapping["hardware_aliases"]:
        csv_rows.append(
            {
                "hardware_name": alias,
                "hardware_type": mapping["hardware_type"],
                "software": "Guitar Rig 7",
                "component_name": mapping["component_name"],
                "component_id": mapping["component_id"],
                "confidence": mapping["confidence"],
                "rationale": mapping["rationale"],
                "reviewed": "",
                "corrected": "",
            }
        )

csv_columns = [
    "hardware_name",
    "hardware_type",
    "software",
    "component_name",
    "component_id",
    "confidence",
    "rationale",
    "reviewed",
    "corrected",
]

with open(review_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"Review CSV written to {review_csv_path}")
print(f"  {len(csv_rows)} rows ({len(mappings)} components)")
print()
print("Next step: review and correct the CSV, then run promote_component_mapping.py")
