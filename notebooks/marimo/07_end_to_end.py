# applied-skills: marimo, ds-workflow

import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from tonedef.component_mapper import load_amp_cabinet_lookup, load_schema, map_components
    from tonedef.ngrr_builder import transplant_preset
    from tonedef.paths import DATA_EXTERNAL
    from tonedef.pipeline import generate_signal_chain
    from tonedef.retriever import search_exemplars
    from tonedef.schemas import ComponentOutput
    from tonedef.signal_chain_parser import format_tonal_target, parse_signal_chain
    from tonedef.validation import (
        validate_phase1,
        validate_phase2,
        validate_pre_build,
        validate_retrieval,
        validate_signal_chain_order,
    )
    from tonedef.xml_builder import build_signal_chain_xml

    return (
        ComponentOutput,
        DATA_EXTERNAL,
        build_signal_chain_xml,
        generate_signal_chain,
        load_amp_cabinet_lookup,
        load_schema,
        map_components,
        parse_signal_chain,
        search_exemplars,
        transplant_preset,
        validate_phase1,
        validate_phase2,
        validate_pre_build,
        validate_retrieval,
        validate_signal_chain_order,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # End-to-End Pipeline Evaluation

    Enter a tone query to run the full pipeline: Phase 1 → validation →
    retrieval → Phase 2 → validation → build.  All validation results are
    shown stage-by-stage as a cascading report.
    """)
    return


@app.cell
def _(mo):
    e2e_query = mo.ui.text_area(
        label="Tone query",
        placeholder="e.g. crunchy blues tone like Stevie Ray Vaughan",
        full_width=True,
    )
    e2e_query
    return (e2e_query,)


@app.cell
def _(
    ComponentOutput,
    e2e_query,
    generate_signal_chain,
    load_amp_cabinet_lookup,
    load_schema,
    map_components,
    mo,
    parse_signal_chain,
    search_exemplars,
    validate_phase1,
    validate_phase2,
    validate_pre_build,
    validate_retrieval,
    validate_signal_chain_order,
):
    mo.stop(not e2e_query.value, mo.md("*Enter a query above to begin.*"))

    # Phase 1
    e2e_raw = generate_signal_chain(e2e_query.value)
    e2e_parsed = parse_signal_chain(e2e_raw)
    e2e_p1v = validate_phase1(e2e_parsed)

    # Retrieval
    _tags = e2e_parsed.tags_characters + e2e_parsed.tags_genres
    _comps = [u.name for s in e2e_parsed.sections for u in s.units]
    e2e_exemplars = search_exemplars(e2e_raw, tags=_tags, components=_comps)
    e2e_rv = validate_retrieval(e2e_exemplars)

    # Phase 2
    e2e_components, _e2e_exemplars = map_components(e2e_raw, e2e_parsed)

    _schema = load_schema()
    _amp_cab = load_amp_cabinet_lookup()

    import contextlib

    e2e_validated = []
    for _c in e2e_components:
        with contextlib.suppress(Exception):
            e2e_validated.append(ComponentOutput.model_validate(_c))

    e2e_p2v = validate_phase2(e2e_validated, _schema) if e2e_validated else None
    e2e_ov = validate_signal_chain_order(e2e_validated, _amp_cab) if e2e_validated else None
    e2e_pv = validate_pre_build(e2e_validated) if e2e_validated else None
    return e2e_components, e2e_ov, e2e_p1v, e2e_p2v, e2e_pv, e2e_rv


@app.cell
def _(e2e_ov, e2e_p1v, e2e_p2v, e2e_pv, e2e_rv, mo):
    def _():
        stages = [
            ("Phase 1", e2e_p1v),
            ("Retrieval", e2e_rv),
            ("Phase 2", e2e_p2v),
            ("Signal Chain Order", e2e_ov),
            ("Pre-Build", e2e_pv),
        ]
        items = []
        total_errors = 0
        total_warnings = 0
        for label, res in stages:
            if res is None:
                items.append(mo.callout(mo.md(f"**{label}:** skipped"), kind="neutral"))
                continue
            total_errors += len(res.errors)
            total_warnings += len(res.warnings)
            if res.errors:
                for e in res.errors:
                    items.append(mo.callout(mo.md(f"**{label}:** {e}"), kind="danger"))
            if res.warnings:
                for w in res.warnings:
                    items.append(mo.callout(mo.md(f"**{label}:** {w}"), kind="warn"))
            if res.is_valid and not res.warnings:
                items.append(mo.callout(mo.md(f"**{label}:** passed"), kind="success"))

        summary = mo.md(
            f"### Validation Summary\n\n**Errors:** {total_errors} · **Warnings:** {total_warnings}"
        )
        return mo.vstack([summary, *items])

    _()
    return


@app.cell
def _(e2e_components, mo):
    def _():
        if not e2e_components:
            return mo.md("*No components.*")
        rows = []
        for c in e2e_components:
            rows.append(
                {
                    "Name": c.get("component_name", "?"),
                    "ID": c.get("component_id", "?"),
                    "Modification": c.get("modification", "?"),
                    "Confidence": c.get("confidence", "?"),
                    "Base Exemplar": c.get("base_exemplar", ""),
                }
            )
        return mo.ui.table(rows, label="Final component list")

    _()
    return


@app.cell
def _(
    DATA_EXTERNAL,
    build_signal_chain_xml,
    e2e_components,
    e2e_query,
    load_schema,
    mo,
    transplant_preset,
):
    def _():
        import tempfile
        from pathlib import Path

        if not e2e_components:
            return mo.md("*No components to build.*")

        _schema = load_schema()
        _xml = build_signal_chain_xml(e2e_components, _schema)
        _template = DATA_EXTERNAL / "Blank_template.ngrr"

        with tempfile.NamedTemporaryFile(suffix=".ngrr", delete=False) as tmp:
            _tmp_path = Path(tmp.name)

        _name = e2e_query.value[:40] if e2e_query.value else "ToneDef Preset"
        transplant_preset(
            template_path=_template,
            signal_chain_xml=_xml,
            output_path=_tmp_path,
            preset_name=_name,
        )
        _data = _tmp_path.read_bytes()
        _tmp_path.unlink()

        return mo.vstack(
            [
                mo.md(f"### Preset built\n\n**{_name}** — {len(_data):,} bytes"),
                mo.md(f"#### XML preview\n\n```xml\n{_xml[:2000]}\n```"),
                mo.download(_data, filename=f"{_name}.ngrr", label="Download preset"),
            ]
        )

    _()
    return


if __name__ == "__main__":
    app.run()
