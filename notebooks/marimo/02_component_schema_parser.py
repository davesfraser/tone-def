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
    # NGRR Component Schema Parser

    Demonstrates parsing a single .ngrr preset to extract its signal
    chain components and parameter schemas.

    The companion script `scripts/build_component_schema.py` runs this
    logic across all presets in `data/external` and writes the full
    catalogue to `data/processed/component_schema.json`.

    ## What we are extracting

    Each .ngrr file contains two XML chunks. XML2 (`gr-instrument-chunk`)
    holds the rack. Within the rack, `non-fix-components` contains the
    signal chain -- the amps, pedals, and effects placed by the user.

    Each component has a numeric `id`, a display `name`, and a list of
    parameters each stored as a normalised 0.0-1.0 float.
    """)
    return


@app.cell
def _():
    import json

    import tonedef.paths as paths
    from tonedef.ngrr_parser import (
        extract_preset_name,
        extract_xml2,
        finalise_catalogue,
        merge_into_catalogue,
        parse_non_fix_components,
    )

    PRESET_FILE_PATH = paths.DATA_EXTERNAL / "presets"
    return (
        PRESET_FILE_PATH,
        extract_preset_name,
        extract_xml2,
        finalise_catalogue,
        json,
        merge_into_catalogue,
        parse_non_fix_components,
    )


@app.cell
def _(mo):
    mo.md("""
    ## Available presets
    """)
    return


@app.cell
def _(PRESET_FILE_PATH):
    parser_preset_files = sorted(PRESET_FILE_PATH.glob("*.ngrr"))
    print(f"Found {len(parser_preset_files)} preset file(s) in {PRESET_FILE_PATH}")
    for parser_p in parser_preset_files:
        print(f"  {parser_p.name}")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Select a preset to inspect
    """)
    return


@app.cell
def _(PRESET_FILE_PATH):
    # Change this to inspect a different preset
    parser_target = PRESET_FILE_PATH / "SRV - Little Wing.ngrr"
    return (parser_target,)


@app.cell
def _(parser_target):
    with open(parser_target, "rb") as f:
        parser_raw = f.read()

    # Count XML declarations
    parser_xml_count = parser_raw.count(b"<?xml")
    print(f"Number of <?xml declarations: {parser_xml_count}")

    # Check closing tags
    print(f"Has </guitarrig7-database-info>: {b'</guitarrig7-database-info>' in parser_raw}")
    print(f"Has </gr-instrument-chunk>: {b'</gr-instrument-chunk>' in parser_raw}")

    # Show first <?xml position and second if it exists
    parser_first = parser_raw.find(b"<?xml")
    parser_second = parser_raw.find(b"<?xml", parser_first + 1)
    print(f"First <?xml at byte: {parser_first}")
    print(f"Second <?xml at byte: {parser_second}")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step 1: Extract preset name and XML2
    """)
    return


@app.cell
def _(extract_preset_name, extract_xml2, parser_target):
    parser_name = extract_preset_name(parser_target)
    parser_xml2 = extract_xml2(parser_target)

    print(f"Preset name: {parser_name}")
    print(f"XML2 size:   {len(parser_xml2)} bytes")
    print(f"First 200 chars:\n{parser_xml2[:200]}")
    return parser_name, parser_xml2


@app.cell
def _(mo):
    mo.md("""
    ## Step 2: Parse signal chain components
    """)
    return


@app.cell
def _(parse_non_fix_components, parser_xml2):
    parser_components = parse_non_fix_components(parser_xml2)

    print(f"Signal chain components found: {len(parser_components)}")
    for parser_c in parser_components:
        print(f"  [{parser_c['component_id']:>6}] {parser_c['component_name']}")
    return (parser_components,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 3: Inspect parameters for each component
    """)
    return


@app.cell
def _(parser_components):
    for parser_entry in parser_components:
        print(f"\n[{parser_entry['component_id']}] {parser_entry['component_name']}")
        for parser_param in parser_entry["parameters"]:
            print(
                f"  {parser_param['param_id']:<8} "
                f"{parser_param['param_name']:<25} "
                f"{parser_param['value']:.6f}"
            )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step 4: What the catalogue entry looks like
    """)
    return


@app.cell
def _(
    finalise_catalogue,
    json,
    merge_into_catalogue,
    parser_components,
    parser_name,
):
    parser_catalogue = merge_into_catalogue({}, parser_components, parser_name)
    parser_catalogue = finalise_catalogue(parser_catalogue)

    parser_first_key = next(iter(parser_catalogue))
    print(f"Example catalogue entry for '{parser_first_key}':")
    print(json.dumps(parser_catalogue[parser_first_key], indent=2))
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Next steps

    Run `scripts/build_component_schema.py` to parse all presets and
    produce the full catalogue at `data/processed/component_schema.json`.

    ```
    uv run python scripts/build_component_schema.py
    ```

    The catalogue feeds into the hardware-to-Guitar Rig mapping table
    which translates LLM output (e.g. "Vox AC30") into the correct
    `component_id` and parameter schema needed to generate valid preset XML.
    """)
    return


if __name__ == "__main__":
    app.run()
