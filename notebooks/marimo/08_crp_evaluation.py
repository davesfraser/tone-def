# applied-skills: marimo, ds-evaluation
import marimo

app = marimo.App(width="medium")

# Cell plan:
# cell 1:  imports          params ()                                            returns (mo,)
# cell 2:  lib_imports      params ()                                            returns (json, pl, Path, DATA_PROCESSED, DATA_EXTERNAL, load_crp_enums, format_crp_reference, load_schema, load_amp_cabinet_lookup)
# cell 3:  header           params (mo,)                                         returns ()
# cell 4:  load_data        params (json, Path, DATA_PROCESSED, DATA_EXTERNAL, load_crp_enums, load_schema, load_amp_cabinet_lookup) returns (crp_enums, schema, amp_cab_lookup, exemplar_store)
# cell 5:  enum_summary     params (mo, crp_enums)                               returns ()
# cell 6:  cab_coverage     params (mo, pl, crp_enums, amp_cab_lookup)           returns ()
# cell 7:  factory_audit    params (mo, pl, exemplar_store, crp_enums)           returns (crp_presets_df,)
# cell 8:  cab_distribution params (mo, pl, crp_presets_df)                      returns ()
# cell 9:  prompt_preview   params (mo, format_crp_reference, crp_enums)         returns ()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import json
    from pathlib import Path

    import polars as pl

    from tonedef.component_mapper import load_amp_cabinet_lookup, load_schema
    from tonedef.crp_lookup import format_crp_reference, load_crp_enums
    from tonedef.paths import DATA_EXTERNAL, DATA_PROCESSED

    return (
        DATA_EXTERNAL,
        DATA_PROCESSED,
        Path,
        format_crp_reference,
        json,
        load_amp_cabinet_lookup,
        load_crp_enums,
        load_schema,
        pl,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # CRP Evaluation — Cabinet/Mic Enum Accuracy

    This notebook audits the Control Room Pro integer enum mappings used
    in FULL_PRODUCTION chains.  It verifies:

    1. **Enum completeness** — all cabinet, mic, and position IDs are present
    2. **Amp-cabinet coverage** — every amp in the lookup maps to a valid Cab enum
    3. **Factory preset audit** — CRP values in real presets match the enum table
    4. **Distribution** — which cabinets appear most often in factory presets
    """)
    return


@app.cell
def _(
    json, Path, DATA_PROCESSED, DATA_EXTERNAL, load_crp_enums, load_schema, load_amp_cabinet_lookup
):
    crp_enums = load_crp_enums()
    schema = load_schema()
    amp_cab_lookup = load_amp_cabinet_lookup()

    with open(DATA_PROCESSED / "exemplar_store.json", encoding="utf-8") as _f:
        exemplar_store = json.load(_f)

    return (crp_enums, schema, amp_cab_lookup, exemplar_store)


@app.cell
def _(mo, crp_enums):
    def _():
        cabs = crp_enums["cabinets"]
        mics = crp_enums["microphones"]
        mpos = crp_enums["mic_positions"]

        summary = mo.md(f"""
        ## Enum Summary

        | Category | Count | Range |
        |----------|-------|-------|
        | Cabinets | {len(cabs)} | 0-{max(int(k) for k in cabs)} |
        | Microphones | {len(mics)} | 0-{max(int(k) for k in mics)} |
        | Mic positions | {len(mpos)} | 0-{max(int(k) for k in mpos)} |

        **Key entries:**
        - Cab 0 = {cabs["0"]["name"]} (DI/bypass)
        - Cab 1 = {cabs["1"]["name"]} (nothing/bypass)
        - Cab 2 = {cabs["2"]["name"]} (first named cabinet)
        - Cab {max(int(k) for k in cabs)} = {cabs[str(max(int(k) for k in cabs))]["name"]}
        """)
        return summary

    return _()


@app.cell
def _(mo, pl, crp_enums, amp_cab_lookup):
    def _():
        valid_cab_ids = {int(k) for k in crp_enums["cabinets"]}
        rows = []
        for amp_name, info in sorted(amp_cab_lookup.items()):
            cab_val = info.get("cab_value")
            in_enum = cab_val in valid_cab_ids if cab_val is not None else False
            cab_name = (
                crp_enums["cabinets"].get(str(cab_val), {}).get("name", "UNKNOWN")
                if cab_val is not None
                else "MISSING"
            )
            rows.append(
                {
                    "amp": amp_name,
                    "cab_value": cab_val,
                    "cab_name": cab_name,
                    "in_enum": in_enum,
                }
            )

        df = pl.DataFrame(rows)
        n_valid = df.filter(pl.col("in_enum")).height
        n_total = df.height

        header = mo.md(f"""
        ## Amp → Cabinet Coverage

        **{n_valid}/{n_total}** amps map to a valid CRP cabinet enum value.
        """)

        _invalid = df.filter(~pl.col("in_enum"))
        if _invalid.height > 0:
            warning = mo.md(f"⚠️ **{_invalid.height} amps have invalid cab values:**")
            return mo.vstack([header, warning, mo.ui.table(_invalid)])

        return mo.vstack([header, mo.md("✅ All amp cabinet mappings are valid."), mo.ui.table(df)])

    return _()


@app.cell
def _(mo, pl, exemplar_store, crp_enums):
    _valid_cab_ids = {int(k) for k in crp_enums["cabinets"]}
    _valid_mic_ids = {int(k) for k in crp_enums["microphones"]}
    _valid_mpos_ids = {int(k) for k in crp_enums["mic_positions"]}

    _crp_names = {"Control Room", "Control Room Pro", "Matched Cabinet Pro"}
    _rows = []

    for _preset in exemplar_store:
        _pname = _preset.get("preset_name", "")
        for _comp in _preset.get("components", []):
            _cname = _comp.get("component_name", "")
            if _cname not in _crp_names:
                continue
            _params = {p["param_id"]: p["value"] for p in _comp.get("parameters", [])}
            _cab1 = _params.get("Cab1")
            _mic1 = _params.get("Mic1")
            _mpos1 = _params.get("MPos1")
            _rows.append(
                {
                    "preset": _pname,
                    "component": _cname,
                    "Cab1": int(_cab1) if _cab1 is not None else None,
                    "Mic1": int(_mic1) if _mic1 is not None else None,
                    "MPos1": int(_mpos1) if _mpos1 is not None else None,
                    "cab_valid": int(_cab1) in _valid_cab_ids if _cab1 is not None else True,
                    "mic_valid": int(_mic1) in _valid_mic_ids if _mic1 is not None else True,
                    "mpos_valid": int(_mpos1) in _valid_mpos_ids if _mpos1 is not None else True,
                }
            )

    crp_presets_df = (
        pl.DataFrame(_rows)
        if _rows
        else pl.DataFrame(
            schema={
                "preset": pl.Utf8,
                "component": pl.Utf8,
                "Cab1": pl.Int64,
                "Mic1": pl.Int64,
                "MPos1": pl.Int64,
                "cab_valid": pl.Boolean,
                "mic_valid": pl.Boolean,
                "mpos_valid": pl.Boolean,
            }
        )
    )

    _n_total = crp_presets_df.height
    _n_cab_invalid = crp_presets_df.filter(~pl.col("cab_valid")).height
    _n_mic_invalid = crp_presets_df.filter(~pl.col("mic_valid")).height
    _n_mpos_invalid = crp_presets_df.filter(~pl.col("mpos_valid")).height

    mo.vstack(
        [
            mo.md(f"""
        ## Factory Preset CRP Audit

        Found **{_n_total}** CRP components across factory presets.

        | Check | Invalid | Status |
        |-------|---------|--------|
        | Cab1 in enum range | {_n_cab_invalid} | {"✅" if _n_cab_invalid == 0 else "❌"} |
        | Mic1 in enum range | {_n_mic_invalid} | {"✅" if _n_mic_invalid == 0 else "❌"} |
        | MPos1 in enum range | {_n_mpos_invalid} | {"✅" if _n_mpos_invalid == 0 else "❌"} |
        """),
            mo.ui.table(crp_presets_df.head(20), pagination=True),
        ]
    )
    return (crp_presets_df,)


@app.cell
def _(mo, pl, crp_presets_df):
    def _():
        if crp_presets_df.height == 0:
            return mo.md("_No CRP components found in factory presets._")

        cab_counts = (
            crp_presets_df.filter(pl.col("Cab1").is_not_null())
            .group_by("Cab1")
            .agg(pl.len().alias("count"))
            .sort("count", descending=True)
        )

        header = mo.md(f"""
        ## Cabinet Distribution in Factory Presets

        Top cabinet enum values used across {crp_presets_df.height} CRP components:
        """)
        return mo.vstack([header, mo.ui.table(cab_counts, pagination=True)])

    return _()


@app.cell
def _(mo, format_crp_reference, crp_enums):
    def _():
        ref_text = format_crp_reference(crp_enums)
        return mo.vstack(
            [
                mo.md("## Prompt Reference Preview"),
                mo.md(
                    "This is the exact text injected into the Phase 2 prompt for `FULL_PRODUCTION` chains:"
                ),
                mo.md(f"```\n{ref_text}\n```"),
            ]
        )

    return _()


if __name__ == "__main__":
    app.run()
