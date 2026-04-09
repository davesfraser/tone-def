import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    # NGRR Preset Builder

    This notebook documents and tests the Guitar Rig 7 `.ngrr` preset generation
    pipeline discovered through binary analysis of real preset files.

    ## How .ngrr files work

    Guitar Rig 7 presets are NI Monolith binary containers with two embedded XML chunks:

    1. **XML1** (`guitarrig7-database-info`) — preset metadata: name, tags, version
    2. **XML2** (`gr-instrument-chunk`) — the actual rack: amp models, effects, parameters

    The signal chain lives inside XML2 in a `<non-fix-components>` block. Everything
    else (tuner, metronome, loop machine, I/O routing) is in `<fix-components>` and
    stays constant across presets.

    The binary container maintains **four internal size/offset fields** that must be
    kept consistent whenever the file content changes:

    | Field | Location | Value |
    |-------|----------|-------|
    | File size | Byte 0 | Total file length |
    | LMX field 1 | 8 bytes before LMX marker | xml2_size + 13 |
    | LMX field 2 | 8 bytes after LMX marker | xml2_size + 1 |
    | Remaining bytes (x3) | Various positions | bytes remaining to EOF from that position |

    Each preset also has a main UUID at bytes 24-40 and multiple hsin chunk UUIDs
    that must be unique to avoid conflicts in GR's browser.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Setup
    """)
    return


@app.cell
def _():
    import struct
    import uuid
    from pathlib import Path

    import tonedef.paths as paths
    from tonedef.ngrr_builder import (
        _compute_xml_chunk_sizes as compute_xml_chunk_sizes,
    )
    from tonedef.ngrr_builder import (
        _find_lmx_positions as find_lmx_positions,
    )
    from tonedef.ngrr_builder import (
        _find_remaining_bytes_fields as find_remaining_bytes_fields,
    )
    from tonedef.ngrr_builder import (
        extract_signal_chain,
        refresh_uuids,
        transplant_preset,
        update_lmx_fields,
        update_remaining_bytes_fields,
        verify_preset,
    )

    return (
        compute_xml_chunk_sizes,
        extract_signal_chain,
        find_lmx_positions,
        find_remaining_bytes_fields,
        paths,
        struct,
        transplant_preset,
        verify_preset,
    )


@app.cell
def _(mo):
    mo.md("""
    ## Configure paths
    """)
    return


@app.cell
def _(paths):
    # Adjust these paths to match your environment
    TEMPLATE_PATH = paths.DATA_EXTERNAL / "Blank_template.ngrr"
    DONOR_PATH = (
        paths.DATA_EXTERNAL / "EC - Beano.ngrr"
    )  ### USER NEEDS TO PROVIDE A DONOR PRESET FILE!
    OUTPUT_DIR = paths.DATA_PROCESSED

    print(f"Template exists: {TEMPLATE_PATH.exists()}")
    print(f"Donor exists:    {DONOR_PATH.exists()}")
    return DONOR_PATH, OUTPUT_DIR, TEMPLATE_PATH


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 1: Inspect the template

    Verify the blank template has the structure we expect before using it.
    """)
    return


@app.cell
def _(
    TEMPLATE_PATH,
    compute_xml_chunk_sizes,
    find_lmx_positions,
    find_remaining_bytes_fields,
    struct,
):
    with open(TEMPLATE_PATH, "rb") as f:
        template_bytes = f.read()

    template_size = len(template_bytes)
    xml1_size, xml2_size = compute_xml_chunk_sizes(template_bytes)
    lmx_positions = find_lmx_positions(template_bytes)
    rb_fields = find_remaining_bytes_fields(template_bytes, template_size)

    print(f"Template file size:       {template_size} bytes")
    print(f"XML1 chunk size:          {xml1_size} bytes")
    print(f"XML2 chunk size:          {xml2_size} bytes")
    print(f"LMX markers at bytes:     {lmx_positions}")
    for lmx_pos in lmx_positions:
        f1 = struct.unpack("<I", template_bytes[lmx_pos - 8 : lmx_pos - 4])[0]
        f2 = struct.unpack("<I", template_bytes[lmx_pos + 8 : lmx_pos + 12])[0]
        print(f"  LMX at {lmx_pos}: field1={f1}, field2={f2}")
    print(f"Remaining-bytes fields:   {rb_fields}")
    for pos in rb_fields:
        val = struct.unpack("<I", template_bytes[pos : pos + 4])[0]
        print(f"  Byte {pos}: {val} (= {template_size} - {pos})")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 2: Extract a donor signal chain

    Pull the `<non-fix-components>` block from an existing preset to use
    as a test case.
    """)
    return


@app.cell
def _(DONOR_PATH, extract_signal_chain):
    donor_chain = extract_signal_chain(DONOR_PATH)

    # Parse out the component names for display
    import re

    component_names = re.findall(rb'<component id="\d+" name="([^"]+)"', donor_chain)

    print(f"Extracted signal chain: {len(donor_chain)} bytes")
    print(f"Components ({len(component_names)}):")
    for name in component_names:
        print(f"  - {name.decode()}")
    return (donor_chain,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 3: Generate a preset

    Transplant the donor signal chain into the blank template.
    """)
    return


@app.cell
def _(OUTPUT_DIR, TEMPLATE_PATH, donor_chain, transplant_preset):
    output_path = OUTPUT_DIR / "EC_Beano_generated.ngrr"

    transplant_preset(
        template_path=TEMPLATE_PATH,
        signal_chain_xml=donor_chain,
        output_path=output_path,
        preset_name="EC - Beano (generated)",
        template_name="Blank template",
    )

    print(f"Preset written to: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")
    return (output_path,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 4: Verify the output

    Check all binary fields are internally consistent.
    """)
    return


@app.cell
def _(output_path, verify_preset):
    result = verify_preset(output_path)

    print(f"Valid: {result['valid']}")
    print(f"File size field:         {'✓' if result['file_size_field'] else '✗'}")
    print(f"LMX fields:              {'✓' if result['lmx_fields'] else '✗'}")
    print(f"Remaining-bytes valid:   {'✓' if result['remaining_bytes_valid'] else '✗'}")

    if result["errors"]:
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  - {e}")
    else:
        print("\nAll checks passed.")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Step 5: Binary field comparison

    Compare our generated file against the original donor to confirm
    the binary structure is correct.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Usage in ToneDef pipeline

    The full V2 flow will call `transplant_preset` with model-generated XML:

    ```python
    from ngrr_builder import transplant_preset

    # signal_chain_xml comes from the LLM output pipeline
    transplant_preset(
        template_path="Blank_template.ngrr",
        signal_chain_xml=signal_chain_xml,
        output_path="output_presets/MyTone.ngrr",
        preset_name="My Tone",
    )
    ```

    The only remaining piece before this is production-ready is the
    hardware-to-Guitar Rig component mapping layer (Step 3 in the build plan)
    which translates LLM output like "Vox AC30" into the correct
    `<component id="..." name="AC Box">` XML block with normalised 0.0-1.0
    parameter values.
    """)
    return


if __name__ == "__main__":
    app.run()
