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

    Demonstrates the three-tier hardware mapping process for Guitar Rig 7
    components. Run `scripts/generate_component_mapping.py` for the full run.

    ## Three-tier hierarchy

    **Tier 1 — Ali Jamieson (documented, unambiguous 1:1 only)**
    Clean single hardware name mappings with no hedging language.
    Entries like "in the style of various Marshall amps" are excluded —
    those go to Tier 2 where the manual can disambiguate them.

    **Tier 2 — GR7 manual text + LLM (documented or inferred)**
    NI's own component descriptions passed as context to the LLM.
    The manual is explicit enough to identify hardware and disambiguate
    closely related components (Cool Plex vs Hot Plex vs Plex).

    **Tier 3 — Parameter list + LLM (inferred or estimated)**
    For components not in the manual — utility, routing, GR-specific
    abstractions. Parameter names act as type fingerprints.

    Microphone mappings (Con/Dyn/Rib) come exclusively from Ali Jamieson.
    """)
    return


@app.cell
def _():
    import json
    import re
    from collections import Counter

    import anthropic

    import tonedef.paths as paths

    return anthropic, json, paths, re


@app.cell
def _(mo):
    mo.md("""
    ## Load sources
    """)
    return


@app.cell
def _(json, paths):
    map_schema_path = paths.DATA_PROCESSED / "component_schema.json"
    map_manual_path = paths.DATA_PROCESSED / "gr_manual_chunks.json"
    map_ali_path = (
        paths.DATA_EXTERNAL / "Guitar Rig 6 Equivalencies (updated for 2022) - Ali Jamieson.txt"
    )

    with open(map_schema_path, encoding="utf-8") as f:
        map_schema = json.load(f)
    with open(map_manual_path, encoding="utf-8") as f:
        map_manual = json.load(f)
    with open(map_ali_path, encoding="utf-8") as f:
        map_ali_text = f.read()

    map_component_names = sorted(map_schema.keys())

    print(f"Schema:  {len(map_component_names)} components")
    print(f"Manual:  {len(map_manual)} chunks")
    return map_ali_text, map_component_names, map_manual, map_schema


@app.cell
def _(mo):
    mo.md("""
    ## Step 1: Parse Ali Jamieson — unambiguous 1:1 mappings only
    """)
    return


@app.cell
def _(map_ali_text, re):
    def map_is_unambiguous(equiv: str) -> bool:
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
        ]
        return not any(s in equiv.lower() for s in ambiguous)

    map_ali_lookup = {}
    map_bullet_re = re.compile(r"\*\s+([A-Za-z0-9\s\'\/\-&+]+?)\s+\(([^)]+)\)")
    for map_m in map_bullet_re.finditer(map_ali_text):
        map_bname = map_m.group(1).strip()
        map_bequiv = map_m.group(2).strip()
        if map_bname and map_bequiv and len(map_bname) > 2 and map_is_unambiguous(map_bequiv):
            map_ali_lookup[map_bname.lower()] = {
                "component_name": map_bname,
                "hardware_aliases": [map_bequiv],
                "source": "Ali Jamieson",
            }

    # Microphones
    map_mic_sec = re.search(
        r"Microphones\s*(.*?)(?=\n\n\s*\n|Effects Units)", map_ali_text, re.DOTALL
    )
    if map_mic_sec:
        for map_mm in re.finditer(
            r"\*\s+((?:Con|Dyn|Rib)\s+\d+)\s+\(([^)]+)\)", map_mic_sec.group(1)
        ):
            map_ali_lookup[map_mm.group(1).strip().lower()] = {
                "component_name": map_mm.group(1).strip(),
                "hardware_aliases": [map_mm.group(2).strip()],
                "hardware_type": "microphone",
                "source": "Ali Jamieson",
            }

    print(f"Ali Jamieson unambiguous mappings: {len(map_ali_lookup)}")
    print("\nSample mappings accepted:")
    for map_v in list(map_ali_lookup.items())[:8]:
        print(f"  {map_v['component_name']:<20} → {map_v['hardware_aliases'][0]}")
    return (map_ali_lookup,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 2: Show manual disambiguation — the Plex family
    """)
    return


@app.cell
def _(map_manual):
    # Demonstrate why the manual is essential for closely related components
    for map_plex in ["Plex", "Cool Plex", "Hot Plex"]:
        chunk = map_manual.get(map_plex, {})
        text = chunk.get("text", "Not found")[:300]
        print(f"{'=' * 60}")
        print(f"{map_plex}")
        print(f"{'=' * 60}")
        print(text)
        print()
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step 3: Tier assignment for all components
    """)
    return


@app.cell
def _(map_ali_lookup, map_component_names, map_manual):
    map_tier1_names = []
    map_tier2_names = []
    map_tier3_names = []

    for map_cname in map_component_names:
        if map_cname.lower() in map_ali_lookup:
            map_tier1_names.append(map_cname)
        elif map_cname in map_manual:
            map_tier2_names.append(map_cname)
        else:
            map_tier3_names.append(map_cname)

    print(f"Tier 1 Ali Jamieson (documented):  {len(map_tier1_names)}")
    print(f"Tier 2 manual + LLM:               {len(map_tier2_names)}")
    print(f"Tier 3 params + LLM:               {len(map_tier3_names)}")

    print("\nTier 3 components (no manual entry):")
    for map_n in map_tier3_names:
        map_params = [p["param_name"] for p in map_manual.get(map_n, {}).get("parameters", [])]
        print(f"  {map_n}")
    return (map_tier2_names,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 4: LLM call — sample of 3 Tier 2 components
    """)
    return


@app.cell
def _(anthropic, json, map_manual, map_schema, map_tier2_names):
    # Sample 3 from tier 2 including the Plex family to show disambiguation
    map_sample = ["Cool Plex", "Hot Plex", "Plex"]
    map_sample = [n for n in map_sample if n in map_tier2_names]

    map_entries = []
    for map_sn in map_sample:
        map_chunk = map_manual.get(map_sn, {})
        map_ctx = map_chunk.get("text", "")[:400].replace("\n", " ")
        _map_params = [p["param_name"] for p in map_schema[map_sn]["parameters"]]
        map_entries.append(
            f"Component: {map_sn}\n"
            f"ID: {map_schema[map_sn]['component_id']}\n"
            f"Parameters: {', '.join(_map_params[:8])}\n"
            f"Context: {map_ctx}"
        )

    map_prompt = """For each Guitar Rig 7 component below, identify the real-world hardware it models.

    Return a JSON array. Each element must have exactly these fields:

    {{
      "component_name": "exact component name as given",
      "hardware_aliases": ["Primary hardware name", "Alternative if applicable"],
      "hardware_type": "one of: tube amplifier, solid state amplifier, overdrive pedal, distortion pedal, fuzz pedal, compressor pedal, delay pedal, reverb pedal, modulation pedal, equaliser, noise gate, cabinet simulation, microphone, utility",
      "confidence": "one of: documented, inferred, estimated",
      "rationale": "one sentence citing the evidence for this mapping"
    }}

    Return ONLY the JSON array.

    Components:
    {component_list}""".format(component_list="\n---\n".join(map_entries))

    map_client = anthropic.Anthropic()
    map_msg = map_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": map_prompt}],
    )
    map_raw = map_msg.content[0].text.strip()
    if map_raw.startswith("```"):
        map_raw = map_raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    map_results = json.loads(map_raw)

    print(f"LLM returned {len(map_results)} mappings\n")
    for map_r in map_results:
        print(f"[{map_r['confidence'].upper()}] {map_r['component_name']}")
        print(f"  Hardware:  {', '.join(map_r['hardware_aliases'])}")
        print(f"  Type:      {map_r['hardware_type']}")
        print(f"  Rationale: {map_r['rationale']}")
        print()
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Next steps

    Run the full generation script:
    ```
    uv run python scripts/generate_component_mapping.py
    ```

    Review `data/interim/component_mapping_review.csv`. Focus attention on
    `manual+LLM` and `params+LLM` rows. Ali Jamieson rows should need
    minimal review.

    Then promote:
    ```
    uv run python scripts/promote_component_mapping.py
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
