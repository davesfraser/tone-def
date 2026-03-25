# applied-skills: marimo

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
    # Phase 2 — Component Selection Pipeline

    This notebook walks through the full Phase 2 pipeline built in this session:

    1. **Component mapping** — load `component_mapping.json` and look up hardware names
    2. **Hardware name extraction** — parse Phase 1 signal chain output for hardware units
    3. **Prompt context assembly** — build the mapping table, manual descriptions, and schema
       snippets that ground `COMPONENT_SELECTION_PROMPT`
    4. **LLM call (Phase 2)** — send the prompt and receive structured JSON
    5. **XML assembly** — convert component JSON to `<non-fix-components>` XML
    6. **Preset generation** — inject XML into the blank template via `transplant_preset()`

    The example query used throughout is: *"I want the tone from Where The Streets
    Have No Name by U2"* — the same example used in `SYSTEM_PROMPT`.
    """)
    return


@app.cell
def _():
    import json
    import os
    from pathlib import Path

    import anthropic
    from dotenv import load_dotenv

    from tonedef.component_mapper import (
        _build_component_candidates_context,
        _build_component_schema_context,
        _build_hardware_mapping_context,
        build_hardware_index,
        extract_hardware_names,
        fill_defaults,
        load_manual_chunks,
        load_mapping,
        load_schema,
        lookup_hardware,
        map_components,
    )
    from tonedef.ngrr_builder import transplant_preset
    from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED
    from tonedef.xml_builder import build_signal_chain_xml

    load_dotenv()

    mapping = load_mapping()
    schema = load_schema()
    manual_chunks = load_manual_chunks()
    index = build_hardware_index(mapping)
    return (
        DATA_EXTERNAL,
        Path,
        anthropic,
        build_signal_chain_xml,
        extract_hardware_names,
        index,
        json,
        lookup_hardware,
        manual_chunks,
        map_components,
        mapping,
        os,
        schema,
        transplant_preset,
    )


@app.cell
def _(mapping, mo):
    mo.md(f"""
    ## Component Mapping

    `component_mapping.json` contains **{len(mapping)} rows** mapping real-world hardware
    names to Guitar Rig 7 components, across {len({r["component_name"] for r in mapping})} unique GR7 components
    and {len({r["hardware_name"] for r in mapping})} unique hardware aliases.

    Confidence distribution:
    | Level | Count |
    |-------|-------|
    | documented | {sum(1 for r in mapping if r["confidence"] == "documented")} |
    | inferred | {sum(1 for r in mapping if r["confidence"] == "inferred")} |
    | estimated | {sum(1 for r in mapping if r["confidence"] == "estimated")} |
    """)
    return


@app.cell
def _(mapping, mo):
    import polars as pl

    _df = pl.DataFrame(mapping).select(
        ["hardware_name", "hardware_type", "component_name", "component_id", "confidence"]
    )
    mo.ui.table(_df, pagination=True)
    return (pl,)


@app.cell
def _(mo):
    mo.md("""
    ## Hardware Name Lookup

    `lookup_hardware()` performs an exact case-insensitive match first,
    then falls back to fuzzy matching via `difflib` with a 0.6 similarity cutoff.

    Below: looking up a few hardware names to show how the index resolves them.
    """)
    return


@app.cell
def _(index, lookup_hardware, mo, pl):
    _queries = [
        "Vox AC30",
        "Marshall Plexi",  # resolves to Cool Plex AND Hot Plex
        "Ibanez TS-808 Tube Screamer",
        "Electro-Harmonix Memory Man",
        "Fender Tweed Deluxe",
        "Boss HM-2",  # fuzzy match test
    ]

    _rows = []
    for _q in _queries:
        _hits = lookup_hardware(_q, index)
        for _h in _hits:
            _rows.append(
                {
                    "query": _q,
                    "component_name": _h["component_name"],
                    "component_id": _h["component_id"],
                    "confidence": _h["confidence"],
                }
            )
        if not _hits:
            _rows.append(
                {
                    "query": _q,
                    "component_name": "(no match)",
                    "component_id": None,
                    "confidence": None,
                }
            )

    lookup_results_df = pl.DataFrame(_rows)
    mo.ui.table(lookup_results_df)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Hardware Name Extraction from Phase 1 Output

    `extract_hardware_names()` uses a regex to parse lines in Phase 1 format:

    ```
    [ Unit name — unit type ] [DOCUMENTED/INFERRED/ESTIMATED]
    ```

    It uses only em dash `—` and en dash `\u2013` as separators, so hardware names
    containing hyphens (e.g. `Electro-Harmonix Memory Man`) are extracted correctly.
    """)
    return


@app.cell
def _():
    # Recorded Phase 1 output for "Where The Streets Have No Name" by U2
    # This is the example output from SYSTEM_PROMPT
    example_signal_chain = """Chain type: FULL_PRODUCTION — query references a specific recording

    GUITAR SIGNAL CHAIN

    [ Edge Custom Stratocaster-style guitar — single coil guitar ] [DOCUMENTED]
      ◆ Pickup selection: neck or middle position
    └─ Contributes chime and clarity
          ↓
    [ Electro-Harmonix Memory Man — analog delay ] [DOCUMENTED]
      ◆ Delay time: dotted eighth note at ~490ms
      ◆ Feedback: 10 o'clock (estimated)
      ◆ Blend: 2 o'clock (estimated)
          ↓
    [ Vox AC30 — tube amplifier ] [DOCUMENTED]
      ◆ Treble: 2 o'clock
      ◆ Bass: 10 o'clock
      ◆ Volume: 2-3 o'clock (estimated)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    CABINET AND MIC

    [ Vox 2x12 — open back cabinet ] [DOCUMENTED]
      ◆ Configuration: 2x12 open back
      ◆ Speaker: Celestion Alnico Blue
          ↓
    [ Shure SM57 — dynamic microphone ] [INFERRED]
      ◆ Placement: edge of dust cap, slightly off-axis (estimated)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    RECORDING CHAIN

    [ Neve 1073 — microphone preamp and EQ ] [INFERRED]
      ◆ Gain: approximately +40dB (estimated)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    STUDIO PROCESSING

    [ SSL G-series bus compressor — VCA compressor ] [INFERRED]
    [ Lexicon 480L — digital reverb ] [INFERRED]

    TAGS
    Characters: Clean, Spacious
    Genres: Rock, Alternative
    """
    return (example_signal_chain,)


@app.cell
def _(
    example_signal_chain,
    extract_hardware_names,
    index,
    lookup_hardware,
    manual_chunks,
    mo,
    schema,
):
    hardware_names = extract_hardware_names(example_signal_chain)

    _candidate_rows = []
    _seen_components = set()
    candidate_component_names = []

    for _hw in hardware_names:
        _hits = lookup_hardware(_hw, index)
        _candidate_rows.extend(_hits)
        for _h in _hits:
            _cn = _h["component_name"]
            if _cn not in _seen_components:
                _seen_components.add(_cn)
                candidate_component_names.append(_cn)

    mapping_ctx = _build_hardware_mapping_context(_candidate_rows)  # noqa: F821
    candidates_ctx = _build_component_candidates_context(candidate_component_names, manual_chunks)  # noqa: F821
    schema_ctx = _build_component_schema_context(candidate_component_names, schema)  # noqa: F821

    mo.vstack(
        [
            mo.md(f"""
        ### Extracted hardware names

        {len(hardware_names)} units parsed from the signal chain:
        """),
            mo.md("\n".join(f"- `{n}`" for n in hardware_names)),
            mo.md(f"""
        ### Resolved GR7 candidates

        {len(_candidate_rows)} mapping rows matched → {len(candidate_component_names)} unique components:
        {", ".join(f"**{c}**" for c in candidate_component_names)}

        > Note: Recording chain and studio processing units (Neve 1073, SSL compressor, Lexicon 480L)
        > have no GR7 equivalents and are correctly omitted. The guitar itself is also not a GR7 component.
        """),
        ]
    )
    return candidates_ctx, mapping_ctx, schema_ctx


@app.cell
def _(candidates_ctx, mapping_ctx, mo, schema_ctx):
    mo.md(f"""
    ## Prompt Context Assembled for LLM

    Three context blocks are injected into `COMPONENT_SELECTION_PROMPT`:

    **Hardware mapping table** ({len(mapping_ctx.splitlines())} rows):
    ```
    {mapping_ctx}
    ```

    **Component manual descriptions** (trimmed to 400 chars each):
    ```
    {candidates_ctx[:800]}{"..." if len(candidates_ctx) > 800 else ""}
    ```

    **Component schema** (param_id | param_name | default):
    ```
    {schema_ctx[:600]}{"..." if len(schema_ctx) > 600 else ""}
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## XML Builder

    `build_signal_chain_xml()` takes a list of component dicts and the schema,
    and produces a `<non-fix-components>` XML block matching the format
    Guitar Rig 7 expects — `id`, `name`, and `value` attributes on every
    `<parameter>` element.

    Here's the output for a manually constructed AC Box + Delay Man chain:
    """)
    return


@app.cell
def _(build_signal_chain_xml, mo, schema):
    _components = [
        {
            "component_name": "Delay Man",
            "component_id": 82000,
            "parameters": {"Pwr": 1.0, "Tm": 0.49, "Fb": 0.3, "Mix": 0.4},
        },
        {
            "component_name": "AC Box",
            "component_id": 38000,
            "parameters": {
                "Pwr": 1.0,
                "CASSt": 0.0,
                "Vol": 0.75,
                "Br": 0.7,
                "Tb": 0.7,
                "Bs": 0.25,
                "Tc": 0.2,
            },
        },
        {
            "component_name": "Matched Cabinet",
            "component_id": 88000,
            "parameters": {},
        },
    ]
    demo_xml = build_signal_chain_xml(_components, schema)

    mo.md(f"""
    ```xml
    {demo_xml.decode("utf-8")}
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Full Pipeline — LLM Phase 2 Call

    `map_components()` orchestrates the entire Phase 2 flow:
    1. Extracts hardware names from the signal chain
    2. Resolves candidates via the mapping index
    3. Assembles all prompt context strings
    4. Calls the Anthropic API with `COMPONENT_SELECTION_PROMPT`
    5. Parses and validates the JSON response
    6. Fills missing parameters with schema defaults

    Run the cell below to call the API. The result is an ordered list of
    GR7 component dicts ready for `build_signal_chain_xml()`.
    """)
    return


@app.cell
def _(anthropic, example_signal_chain, map_components, mo, os):
    _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    with mo.status.spinner("Running Phase 2 LLM call..."):
        components = map_components(example_signal_chain, _client)

    mo.md(f"Phase 2 returned **{len(components)} components**.")
    return (components,)


@app.cell
def _(components, json, mo):
    mo.md(f"""
    ### Component JSON output

    ```json
    {json.dumps(components, indent=2)}
    ```
    """)
    return


@app.cell
def _(build_signal_chain_xml, components, mo, schema):
    signal_chain_xml = build_signal_chain_xml(components, schema)
    mo.md(f"""
    ### Assembled XML

    ```xml
    {signal_chain_xml.decode("utf-8")}
    ```
    """)
    return (signal_chain_xml,)


@app.cell
def _(DATA_EXTERNAL, Path, mo, signal_chain_xml, transplant_preset):
    _template = DATA_EXTERNAL / "Blank_template.ngrr"
    _output_dir = Path(__file__).parent / "output_presets"
    _output_dir.mkdir(exist_ok=True)
    output_path = _output_dir / "streets_have_no_name.ngrr"

    transplant_preset(
        template_path=_template,
        signal_chain_xml=signal_chain_xml,
        output_path=output_path,
        preset_name="Streets Have No Name",
    )

    mo.md(f"""
    ## Preset Generated ✓

    Written to `{output_path}`

    Drag `streets_have_no_name.ngrr` into Guitar Rig 7's preset browser to load it.

    **Pipeline summary:**

    | Step | Module | Output |
    |------|--------|--------|
    | Phase 1 | `SYSTEM_PROMPT` (Anthropic) | Human-readable signal chain |
    | Hardware lookup | `component_mapper.build_hardware_index` | Candidate GR7 components |
    | Phase 2 | `COMPONENT_SELECTION_PROMPT` (Anthropic) | Component JSON with parameters |
    | XML assembly | `xml_builder.build_signal_chain_xml` | `<non-fix-components>` XML |
    | File generation | `ngrr_builder.transplant_preset` | `.ngrr` preset file |
    """)
    return


if __name__ == "__main__":
    app.run()
