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
    # Tag Catalogue Builder

    Demonstrates parsing the Guitar Rig 7 preset tag taxonomy from a
    single preset before running the full catalogue build script.

    The companion script `scripts/build_tag_catalogue.py` runs this
    logic across all presets in `data/external` and writes the full
    catalogue to `data/processed/tag_catalogue.json`.

    ## What we are extracting

    Each .ngrr file contains metadata in XML1 (`guitarrig7-database-info`)
    including a set of hierarchical tags that classify the preset. We extract
    four tag categories:

    - **Characters** — tonal character (Clean, Distorted, Crunch, Spacious)
    - **FX Types** — effect categories and subcategories (Amps & Cabinets > Hi Gain)
    - **Genres** — musical genre (Rock, Pop, Blues, Alternative)
    - **Input Sources** — instrument type (Guitar, Bass)

    The Amplifiers category is excluded — amp identity is captured at finer
    grain in the component mapping.
    """)
    return


@app.cell
def _():
    import json

    import tonedef.paths as paths
    from tonedef.ngrr_parser import (
        extract_xml1,
        finalise_tag_catalogue,
        merge_tags_into_catalogue,
        parse_preset_metadata,
    )

    PRESET_FILE_PATH = paths.DATA_EXTERNAL / "presets"
    return (
        PRESET_FILE_PATH,
        extract_xml1,
        finalise_tag_catalogue,
        json,
        merge_tags_into_catalogue,
        parse_preset_metadata,
    )


@app.cell
def _(mo):
    mo.md("""
    ## Available presets
    """)
    return


@app.cell
def _(PRESET_FILE_PATH):
    tag_preset_files = sorted(PRESET_FILE_PATH.glob("*.ngrr"))
    print(f"Found {len(tag_preset_files)} preset file(s) in {PRESET_FILE_PATH}")
    for tag_p in tag_preset_files[:10]:
        print(f"  {tag_p.name}")
    if len(tag_preset_files) > 10:
        print(f"  ... and {len(tag_preset_files) - 10} more")
    return (tag_preset_files,)


@app.cell
def _(mo):
    mo.md("""
    ## Select a preset to inspect
    """)
    return


@app.cell
def _(PRESET_FILE_PATH):
    # Change this to inspect a different preset
    tag_target = PRESET_FILE_PATH / "80s Stadium Rig.ngrr"
    return (tag_target,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 1: Extract XML1
    """)
    return


@app.cell
def _(extract_xml1, tag_target):
    tag_xml1 = extract_xml1(tag_target)
    print(f"Target: {tag_target.name}")
    print(f"XML1 extracted: {len(tag_xml1)} bytes")
    print(f"\nFull XML1:\n{tag_xml1}")
    return (tag_xml1,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 2: Parse preset metadata and tags
    """)
    return


@app.cell
def _(parse_preset_metadata, tag_xml1):
    tag_metadata = parse_preset_metadata(tag_xml1)

    print(f"Name:       {tag_metadata['name']}")
    print(f"Author:     {tag_metadata['author']}")
    print(f"Comment:    {tag_metadata['comment'] or '(none)'}")
    print(f"Factory:    {tag_metadata['is_factory']}")
    print(f"\nTags ({len(tag_metadata['tags'])}):")
    for tag_t in tag_metadata["tags"]:
        print(f"  [{tag_t['root']:<15}] {tag_t['path']}")
    return (tag_metadata,)


@app.cell
def _(mo):
    mo.md("""
    ## Step 3: What the catalogue entry looks like
    """)
    return


@app.cell
def _(finalise_tag_catalogue, json, merge_tags_into_catalogue, tag_metadata):
    tag_catalogue = merge_tags_into_catalogue({}, tag_metadata)
    tag_list = finalise_tag_catalogue(tag_catalogue)

    print(f"Unique tags from this preset: {len(tag_list)}")
    print("\nExample entries:")
    print(json.dumps(tag_list[:3], indent=2))
    return


@app.cell
def _(mo):
    mo.md("""
    ## Step 4: Run across multiple presets
    """)
    return


@app.cell
def _(
    extract_xml1,
    finalise_tag_catalogue,
    merge_tags_into_catalogue,
    parse_preset_metadata,
    tag_preset_files,
):
    tag_multi_catalogue = {}
    tag_processed = 0

    # Run across first 20 presets as a sample
    for tag_path in tag_preset_files[:20]:
        tag_x1 = extract_xml1(tag_path)
        if tag_x1 is None:
            continue
        tag_meta = parse_preset_metadata(tag_x1)
        if not tag_meta:
            continue
        tag_multi_catalogue = merge_tags_into_catalogue(tag_multi_catalogue, tag_meta)
        tag_processed += 1

    tag_multi_list = finalise_tag_catalogue(tag_multi_catalogue)

    print(f"Processed {tag_processed} presets")
    print(f"Unique tags found: {len(tag_multi_list)}")

    from collections import Counter

    tag_by_root = Counter(t["root"] for t in tag_multi_list)
    print("\nTags by category:")
    for tag_root, tag_count in sorted(tag_by_root.items()):
        print(f"  {tag_root:<20} {tag_count} unique values")

    print("\nTop 10 most common tags:")
    tag_top = sorted(tag_multi_list, key=lambda t: -t["occurrence_count"])[:10]
    for tag_t1 in tag_top:
        print(f"  {tag_t1['occurrence_count']:>3}x  {tag_t1['path']}")
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Next steps

    Run `scripts/build_tag_catalogue.py` to process all presets:

    ```
    uv run python scripts/build_tag_catalogue.py
    ```

    The tag catalogue feeds into two places:

    1. **`SYSTEM_PROMPT` extension** — the LLM infers appropriate GR tags
       for any tone query so generated presets appear in the right browser
       categories in Guitar Rig.

    2. **`EXEMPLAR_REFINEMENT_PROMPT`** — tags provide tonal context that
       helps ground component and parameter selection against known exemplars.
    """)
    return


if __name__ == "__main__":
    app.run()
