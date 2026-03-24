"""
generate_component_mapping.py
-----------------------------
Generates the hardware-to-component mapping table for Guitar Rig 7 components
using a three-tier hierarchy:

Tier 1 — Ali Jamieson (documented, 1:1 unambiguous mappings)
    Unambiguous single hardware name mappings from a well-regarded community
    source. Used where Ali gives a clean 1:1 with no hedging language.
    Source: https://alijamieson.co.uk/2022/12/29/guitar-rig-6-equivalencies-updated-for-2022/
    File:   data/external/gr_equivalencies_alijamieson.txt

Tier 2 — Manual text + LLM (documented or inferred)
    For components covered in the GR7 manual, passes NI's own description text
    to the LLM for hardware identification. Manual descriptions contain explicit
    hardware references or enough circuit detail to infer confidently.
    File:   data/external/gr_manual_chunks.json

Tier 3 — Parameter list + LLM only (inferred or estimated)
    For components not in the manual — utility routing, modifiers, GR-specific
    abstractions. Parameter names act as type fingerprints.

Cabinet and microphone names from Ali Jamieson are excluded — cabinets and
mics live inside Control Room / Matched Cabinet components in the schema,
not as standalone entries.

Data retrieval
--------------
To refresh Ali Jamieson source:
    # Open in browser, Select All, paste to text file:
    # data/external/gr_equivalencies_alijamieson.txt

To refresh manual chunks:
    uv run python scripts/build_manual_chunks.py

Outputs
-------
    data/interim/component_mapping_raw.json   - structured output for code
    data/interim/component_mapping_review.csv - long-format table for human review

Usage
-----
    uv run python scripts/generate_component_mapping.py
"""

import csv
import json
import re
import sys
from collections import Counter

import anthropic
from dotenv import load_dotenv

from tonedef.paths import DATA_EXTERNAL, DATA_INTERIM, DATA_PROCESSED

load_dotenv()


DATA_INTERIM.mkdir(parents=True, exist_ok=True)

ALI_FILE = DATA_EXTERNAL / "Guitar Rig 6 Equivalencies (updated for 2022) - Ali Jamieson.txt"
MANUAL_FILE = DATA_PROCESSED / "gr_manual_chunks.json"
SCHEMA_PATH = DATA_PROCESSED / "component_schema.json"
RAW_OUT = DATA_INTERIM / "component_mapping_raw.json"
REVIEW_CSV = DATA_INTERIM / "component_mapping_review.csv"

for path in [ALI_FILE, MANUAL_FILE, SCHEMA_PATH]:
    if not path.exists():
        print(f"Missing required file: {path}")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------------

with open(SCHEMA_PATH, encoding="utf-8") as f:
    schema = json.load(f)
component_names = sorted(schema.keys())
print(f"Schema:  {len(component_names)} components")

with open(MANUAL_FILE, encoding="utf-8") as f:
    manual_chunks = json.load(f)
print(f"Manual:  {len(manual_chunks)} component chunks")

with open(ALI_FILE, encoding="utf-8") as f:
    ali_text = f.read()

# ---------------------------------------------------------------------------
# Ali Jamieson name normalisation
# Maps Ali's name variants to the exact schema component names
# ---------------------------------------------------------------------------

ALI_NAME_MAP = {
    "rc24": "RC 24",
    "rc48": "RC 48",
    "vc160": "VC 160",
    "vc2a": "VC 2A",
    "vc76": "VC 76",
    "sledge hammer": "Sledgehammer",
    "demon": "Demon Distortion",
    "flanger/chorus": "Flanger Chorus",
    "pro-filter": "Pro-Filter",
    "iceverb": "Iceverb",
    "mezone": "Mezone",
    "harmonic synthesizer": "Harmonic Synthesizer",
    "octaver": "Oktaver",
    "ring modulator": "Ring Modulator",
    "tremolo": "Tremolo",
    "big fuzz": "Big Fuzz",
    "distortion": "Distortion",
}

# Names to exclude entirely from Ali parsing —
# social links, page title, ambiguous entries, cabinet/mic names
# (cabinets and mics are not standalone schema components)
ALI_EXCLUDE = {
    "share on facebook",
    "share on reddit",
    "share on x",
    "share on linkedin",
    "share on whatsapp",
    "share on telegram",
    "guitar rig 6 equivalencies",
    "replika",  # NI standalone plugin, not GR component Replika GR
}


# Cabinet name prefixes — exclude these as they don't exist as schema components
def is_cabinet_name(name: str) -> bool:
    return bool(re.match(r"^\d+\s*x\s*\d+", name.lower()))


# Microphone name pattern — Con/Dyn/Rib live inside Control Room in the schema
def is_mic_name(name: str) -> bool:
    return bool(re.match(r"^(con|dyn|rib)\s+\d+", name.lower()))


# ---------------------------------------------------------------------------
# Parse Ali Jamieson — unambiguous 1:1 mappings only
# ---------------------------------------------------------------------------


def clean_ali_equiv(equiv: str) -> str:
    """Strip inline URL tags but keep surrounding text."""
    # Match <http...> including content with spaces (line-wrapped URLs)
    cleaned = re.sub(r"\s*<https?://[^>]+>", "", equiv, flags=re.DOTALL)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_unambiguous(equiv: str) -> bool:
    """Return True if the equivalency is a clean single hardware reference."""
    ambiguous = [
        " or ",
        " and ",
        ", ",
        "style of",
        "similar to",
        "various",
        "generic",
        "unclear",
        "possibly",
        "models the",
        "associated with",
        "late 1980s",
    ]
    return not any(s in equiv.lower() for s in ambiguous)


ali_lookup = {}
bullet_re = re.compile(r"\*\s+([A-Za-z0-9\s\'\/\-&+]+?)\s+\(([^)]+)\)", re.DOTALL)

for m in bullet_re.finditer(ali_text):
    name = m.group(1).strip()
    equiv = clean_ali_equiv(m.group(2).strip())

    if not name or not equiv or len(name) <= 2:
        continue
    if name.lower() in ALI_EXCLUDE:
        continue
    if is_cabinet_name(name) or is_mic_name(name):
        continue
    if not is_unambiguous(equiv):
        continue

    # Normalise name to schema canonical form
    canonical = ALI_NAME_MAP.get(name.lower(), name).lower()
    ali_lookup[canonical] = {
        "component_name": name,
        "hardware_aliases": [equiv],
        "source": "Ali Jamieson",
    }

print(f"Ali Jamieson: {len(ali_lookup)} unambiguous mappings")

# ---------------------------------------------------------------------------
# Hardware type from manual category
# ---------------------------------------------------------------------------

HARDWARE_TYPE_BY_CATEGORY = {
    "Amplifiers": "tube amplifier",
    "Cabinets": "cabinet simulation",
    "Delay / Echo": "delay pedal",
    "Distortion": "distortion pedal",
    "Dynamics": "compressor pedal",
    "Equalizer": "equaliser",
    "Filter": "modulation pedal",
    "Modulation": "modulation pedal",
    "Pitch": "modulation pedal",
    "Reverb": "reverb pedal",
    "Special FX": "utility",
    "Modifier": "utility",
    "Tools": "utility",
    "Legacy": "utility",
}


def get_hardware_type(comp_name: str) -> str:
    cat = manual_chunks.get(comp_name, {}).get("category", "")
    return HARDWARE_TYPE_BY_CATEGORY.get(cat, "utility")


# ---------------------------------------------------------------------------
# Tier 1 — Ali Jamieson unambiguous matches
# ---------------------------------------------------------------------------

tier1 = {}
remaining = []

for comp_name in component_names:
    key = ALI_NAME_MAP.get(comp_name.lower(), comp_name).lower()
    ali = ali_lookup.get(key) or ali_lookup.get(comp_name.lower())
    if ali:
        tier1[comp_name] = {
            "component_name": comp_name,
            "component_id": schema[comp_name]["component_id"],
            "hardware_aliases": ali["hardware_aliases"],
            "hardware_type": get_hardware_type(comp_name),
            "confidence": "documented",
            "rationale": "Unambiguous 1:1 mapping from Ali Jamieson",
            "source": "Ali Jamieson",
        }
    else:
        remaining.append(comp_name)

print(f"\nTier 1 (Ali Jamieson):   {len(tier1)}")
print(f"Remaining for Tier 2/3:  {len(remaining)}")

tier2_names = [n for n in remaining if n in manual_chunks]
tier3_names = [n for n in remaining if n not in manual_chunks]
print(f"Tier 2 (manual + LLM):   {len(tier2_names)}")
print(f"Tier 3 (params + LLM):   {len(tier3_names)}")

# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """For each Guitar Rig 7 component below, identify the real-world hardware it models.

Return a JSON array. Each element must have exactly these fields:

{{
  "component_name": "exact component name as given",
  "hardware_aliases": ["Primary hardware name", "Alternative if applicable"],
  "hardware_type": "one of: tube amplifier, solid state amplifier, overdrive pedal, distortion pedal, fuzz pedal, compressor pedal, delay pedal, reverb pedal, modulation pedal, equaliser, noise gate, cabinet simulation, microphone, utility",
  "confidence": "one of: documented, inferred, estimated",
  "rationale": "one sentence citing the evidence for this mapping"
}}

Confidence:
- documented: NI's own description text explicitly identifies the hardware
- inferred: description strongly implies specific hardware but does not name it
- estimated: generic or GR-specific component with no clear hardware equivalent

Rules:
- Use the NI description text as primary evidence where provided
- hardware_aliases must contain at least one entry
- For utility/routing components use the component name as alias, confidence estimated
- Do not invent hardware that does not exist
- Return ONLY the JSON array

Components:
{component_list}"""


def build_entry(name: str, context: str) -> str:
    params = [p["param_name"] for p in schema[name]["parameters"]]
    param_str = ", ".join(params[:8]) if params else "none"
    return (
        f"Component: {name}\n"
        f"ID: {schema[name]['component_id']}\n"
        f"Parameters: {param_str}\n"
        f"Context: {context}"
    )


def run_llm(entries: list[str], label: str) -> list[dict]:
    if not entries:
        return []
    prompt = PROMPT_TEMPLATE.format(component_list="\n---\n".join(entries))
    print(f"\nCalling Claude API for {len(entries)} {label} components...")
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        results = json.loads(raw)
        for r in results:
            r["component_id"] = schema.get(r["component_name"], {}).get("component_id", 0)
            r["source"] = label
        print(f"  Received {len(results)} mappings")
        return results
    except json.JSONDecodeError as e:
        error_path = DATA_INTERIM / f"mapping_error_{label.replace(' ', '_')}.txt"
        error_path.write_text(raw, encoding="utf-8")
        print(f"  JSON parse error: {e} — saved to {error_path}")
        return []


# ---------------------------------------------------------------------------
# Tier 2 — manual text + LLM
# ---------------------------------------------------------------------------

tier2_entries = [
    build_entry(name, manual_chunks[name]["text"][:400].replace("\n", " ")) for name in tier2_names
]
tier2_results = run_llm(tier2_entries, "manual+LLM")

# ---------------------------------------------------------------------------
# Tier 3 — parameter list + LLM
# ---------------------------------------------------------------------------

tier3_entries = [build_entry(name, "No manual entry available") for name in tier3_names]
tier3_results = run_llm(tier3_entries, "params+LLM")

# ---------------------------------------------------------------------------
# Merge and write outputs
# ---------------------------------------------------------------------------

all_mappings = list(tier1.values()) + tier2_results + tier3_results
all_mappings.sort(key=lambda r: r["component_name"])

with open(RAW_OUT, "w", encoding="utf-8") as f:
    json.dump(all_mappings, f, indent=2, ensure_ascii=False)
print(f"\nRaw JSON written to {RAW_OUT}")

CSV_COLUMNS = [
    "hardware_name",
    "hardware_type",
    "software",
    "component_name",
    "component_id",
    "confidence",
    "rationale",
    "source",
    "reviewed",
    "corrected",
]

csv_rows = []
for mapping in all_mappings:
    for alias in mapping.get("hardware_aliases", []):
        csv_rows.append(
            {
                "hardware_name": alias.strip(),
                "hardware_type": mapping.get("hardware_type", ""),
                "software": "Guitar Rig 7",
                "component_name": mapping["component_name"],
                "component_id": mapping.get("component_id", 0),
                "confidence": mapping.get("confidence", ""),
                "rationale": mapping.get("rationale", ""),
                "source": mapping.get("source", ""),
                "reviewed": "",
                "corrected": "",
            }
        )

with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"Review CSV written to {REVIEW_CSV}")
print(f"  {len(csv_rows)} rows ({len(all_mappings)} components)")

print("\nMappings by source:")
for src, cnt in sorted(Counter(m.get("source") for m in all_mappings).items()):
    print(f"  {src:<25} {cnt}")

print("\nMappings by confidence:")
for conf, cnt in sorted(Counter(m.get("confidence") for m in all_mappings).items()):
    print(f"  {conf:<15} {cnt}")

print("\nNext step: review data/interim/component_mapping_review.csv")
print("Then run: uv run python scripts/promote_component_mapping.py")
