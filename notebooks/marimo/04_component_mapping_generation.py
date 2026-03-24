import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # Component Mapping Generation

    Demonstrates the LLM-based hardware mapping process for a small subset
    of Guitar Rig 7 components before running the full generation script.

    The companion script `scripts/generate_component_mapping.py` runs this
    process across all 147 components and writes:

    - `data/interim/component_mapping_raw.json` — structured output for code
    - `data/interim/component_mapping_review.csv` — long-format table for review

    ## What we are doing

    The component schema catalogue tells us what Guitar Rig components exist
    and what their parameters are. It does not tell us what real-world hardware
    each component is based on. This step asks the LLM to make that connection.

    The output is a long-format mapping table: one row per hardware alias per
    component. Multiple hardware names can map to the same Guitar Rig component
    (e.g. both "Vox AC30" and "Vox AC15" map to "AC Box").
    """)
    return


@app.cell
def _():
    import csv
    import json

    import anthropic

    import tonedef.paths as paths
    from tonedef.prompts import MAPPING_PROMPT

    return anthropic, json, paths


@app.cell
def _(mo):
    mo.md("""
    ## Load component catalogue
    """)
    return


@app.cell
def _(json, paths):
    mapping_schema_path = paths.DATA_PROCESSED / "component_schema.json"
    with open(mapping_schema_path, encoding="utf-8") as mapping_f:
        mapping_schema = json.load(mapping_f)

    mapping_all_names = sorted(mapping_schema.keys())
    print(f"Loaded {len(mapping_all_names)} components from catalogue")
    print("\nFirst 10 components:")
    for mapping_n in mapping_all_names[:10]:
        print(f"  {mapping_n}")
    return mapping_all_names, mapping_schema


@app.cell
def _(mo):
    mo.md(r"""
    ## Select a sample to test

    We run the mapping prompt against a small subset first to validate
    output quality before committing to a full 147-component run.
    """)
    return


@app.cell
def _(mapping_all_names):
    # Hand-picked sample covering different component types:
    # amplifiers, pedals, effects, and utility components
    mapping_sample = [
        "AC Box",
        "Plexi",
        "Tweed Delight",
        "Bass Invader",
        "TS Drive",
        "Treble Booster",
        "Studio Reverb",
        "Tape Echo",
        "Flanger",
        "Tube Compressor",
        "Control Room",
        "Noise Gate",
    ]
    print(f"Sample size: {len(mapping_sample)} components")
    for mapping_s in mapping_sample:
        in_catalogue = mapping_s in mapping_all_names
        print(f"  {'✓' if in_catalogue else '✗'} {mapping_s}")
    return (mapping_sample,)


@app.cell
def _(mo):
    mo.md("""
    ## The mapping prompt
    """)
    return


@app.cell
def _(mapping_sample):
    MAPPING_PROMPT_TEMPLATE = """
    You are an expert in guitar equipment, amp modelling software, and signal chain
    hardware. You have deep knowledge of Guitar Rig 7 by Native Instruments and the
    real-world hardware units it models.

    Below is a list of Guitar Rig 7 component names. For each component, provide a
    mapping to the real-world hardware it is based on.

    Return a JSON array. Each element must have exactly these fields:

    {{
      "component_name": "exact Guitar Rig component name as given",
      "hardware_aliases": [
    "Primary hardware name e.g. Vox AC30",
    "Alternative name or variant e.g. Vox AC30 Top Boost"
      ],
      "hardware_type": "one of: tube amplifier, solid state amplifier, overdrive pedal, distortion pedal, fuzz pedal, compressor pedal, delay pedal, reverb pedal, modulation pedal, equaliser, noise gate, cabinet simulation, microphone, utility",
      "confidence": "one of: documented, inferred, estimated",
      "rationale": "one sentence explaining the mapping and confidence level"
    }}

    Confidence levels:
    - documented: confirmed in NI documentation, marketing materials, or well-established community knowledge
    - inferred: component characteristics strongly suggest a specific hardware unit but not officially confirmed
    - estimated: generic type with no clear single hardware reference

    Rules:
    - hardware_aliases must contain at least one entry
    - For generic components with no real-world hardware equivalent, use the component name as the primary alias and set confidence to estimated
    - Do not invent hardware that does not exist
    - Return ONLY the JSON array, no preamble or explanation

    Guitar Rig 7 components to map:
    {component_list}
    """

    mapping_component_list = "\n".join(f"- {name}" for name in mapping_sample)
    mapping_prompt = MAPPING_PROMPT_TEMPLATE.format(component_list=mapping_component_list)

    print("Prompt preview (first 500 chars):")
    print(mapping_prompt[:500])
    print("...")
    return (mapping_prompt,)


@app.cell
def _(mo):
    mo.md("""
    ## Call the API
    """)
    return


@app.cell
def _(anthropic, mapping_prompt):
    mapping_client = anthropic.Anthropic()

    mapping_message = mapping_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": mapping_prompt}],
    )

    mapping_raw_text = mapping_message.content[0].text.strip()

    # Strip markdown code fences if present
    if mapping_raw_text.startswith("```"):
        mapping_raw_text = mapping_raw_text.split("\n", 1)[1]
        mapping_raw_text = mapping_raw_text.rsplit("```", 1)[0].strip()

    print(f"Response length: {len(mapping_raw_text)} chars")
    print(f"\nRaw response preview:\n{mapping_raw_text[:500]}")
    return (mapping_raw_text,)


@app.cell
def _(mo):
    mo.md("""
    ## Parse and inspect the output
    """)
    return


@app.cell
def _(json, mapping_raw_text):
    mapping_parsed = json.loads(mapping_raw_text)
    print(f"Parsed {len(mapping_parsed)} mappings\n")
    for mapping_entry in mapping_parsed:
        print(f"[{mapping_entry['confidence'].upper()}] {mapping_entry['component_name']}")
        print(f"  Type:     {mapping_entry['hardware_type']}")
        print(f"  Hardware: {', '.join(mapping_entry['hardware_aliases'])}")
        print(f"  Rationale: {mapping_entry['rationale']}")
        print()
    return (mapping_parsed,)


@app.cell
def _(mo):
    mo.md("""
    ## What the review CSV rows look like
    """)
    return


@app.cell
def _(mapping_parsed, mapping_schema):
    mapping_id_lookup = {name: entry["component_id"] for name, entry in mapping_schema.items()}

    mapping_csv_rows = []
    for mapping_m in mapping_parsed:
        for mapping_alias in mapping_m["hardware_aliases"]:
            mapping_csv_rows.append(
                {
                    "hardware_name": mapping_alias,
                    "hardware_type": mapping_m["hardware_type"],
                    "software": "Guitar Rig 7",
                    "component_name": mapping_m["component_name"],
                    "component_id": mapping_id_lookup.get(mapping_m["component_name"], 0),
                    "confidence": mapping_m["confidence"],
                    "rationale": mapping_m["rationale"],
                    "reviewed": "",
                    "corrected": "",
                }
            )

    print(f"CSV rows generated: {len(mapping_csv_rows)}")
    print(f"(from {len(mapping_parsed)} components with multiple aliases expanded)\n")
    print(f"{'hardware_name':<30} {'software':<15} {'component_name':<20} {'confidence'}")
    print("-" * 85)
    for mapping_row in mapping_csv_rows:
        print(
            f"{mapping_row['hardware_name']:<30} "
            f"{mapping_row['software']:<15} "
            f"{mapping_row['component_name']:<20} "
            f"{mapping_row['confidence']}"
        )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Quality check

    Things to look for when reviewing the CSV:

    - **documented** entries should have a clear, verifiable hardware reference
    - **inferred** entries should make sonic/circuit sense even if not confirmed
    - **estimated** entries should be genuine GR abstractions with no clear hardware model
    - Hardware aliases should cover common name variations (e.g. both "Marshall Plexi" and "Marshall Super Lead 1959")
    - hardware_type should be accurate — an amp modelled as a pedal is a bug

    Once satisfied with the sample quality, run the full script:

    ```
    uv run python scripts/generate_component_mapping.py
    ```

    Then review `data/interim/component_mapping_review.csv` and promote with:

    ```
    uv run python scripts/promote_component_mapping.py
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
