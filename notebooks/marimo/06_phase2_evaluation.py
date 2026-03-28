# applied-skills: marimo, ds-workflow
import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")

# Cell plan:
# cell 1:  imports            params ()                                      returns (mo,)
# cell 2:  lib_imports        params ()                                      returns (anthropic, settings, parse_signal_chain, format_tonal_target, map_components, load_schema, load_amp_cabinet_lookup, ComponentOutput, validate_phase2, validate_signal_chain_order)
# cell 3:  header             params (mo,)                                   returns ()
# cell 4:  query_input        params (mo,)                                   returns (phase1_input,)
# cell 5:  run_phase2         params (phase1_input, anthropic, settings, parse_signal_chain, map_components, load_schema, load_amp_cabinet_lookup, ComponentOutput, validate_phase2, validate_signal_chain_order) returns (components, validated_comps, p2_result, order_result, schema)
# cell 6:  validation_display params (mo, p2_result, order_result)           returns ()
# cell 7:  component_table    params (mo, components)                        returns ()
# cell 8:  param_drilldown    params (mo, validated_comps, schema)           returns ()
# cell 9:  compact_view       params (mo, phase1_input, parse_signal_chain, format_tonal_target) returns ()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import anthropic

    from tonedef.component_mapper import load_amp_cabinet_lookup, load_schema, map_components
    from tonedef.models import ComponentOutput
    from tonedef.settings import settings
    from tonedef.signal_chain_parser import format_tonal_target, parse_signal_chain
    from tonedef.validation import validate_phase2, validate_signal_chain_order

    return (
        ComponentOutput,
        anthropic,
        format_tonal_target,
        load_amp_cabinet_lookup,
        load_schema,
        map_components,
        parse_signal_chain,
        settings,
        validate_phase2,
        validate_signal_chain_order,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Phase 2 Evaluation — Component Mapping

    Paste a Phase 1 signal chain output below.  This notebook runs
    the full Phase 2 mapping pipeline and presents validation results,
    component details, and parameter drill-downs.
    """)
    return


@app.cell
def _(mo):
    phase1_input = mo.ui.text_area(
        label="Phase 1 signal chain output",
        placeholder="Paste raw Phase 1 output here...",
        full_width=True,
    )
    phase1_input
    return (phase1_input,)


@app.cell
def _(
    ComponentOutput,
    anthropic,
    load_amp_cabinet_lookup,
    load_schema,
    map_components,
    mo,
    parse_signal_chain,
    phase1_input,
    settings,
    validate_phase2,
    validate_signal_chain_order,
):
    mo.stop(
        not phase1_input.value,
        mo.md("*Paste a Phase 1 output above to begin.*"),
    )

    _client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    _parsed = parse_signal_chain(phase1_input.value)
    components = map_components(phase1_input.value, _parsed, _client)

    schema = load_schema()
    _amp_cab = load_amp_cabinet_lookup()

    # Validate through Pydantic
    import contextlib

    validated_comps = []
    for _c in components:
        with contextlib.suppress(Exception):
            validated_comps.append(ComponentOutput.model_validate(_c))

    p2_result = validate_phase2(validated_comps, schema) if validated_comps else None
    order_result = (
        validate_signal_chain_order(validated_comps, _amp_cab) if validated_comps else None
    )
    return (components, order_result, p2_result, schema, validated_comps)


@app.cell
def _(mo, order_result, p2_result):
    def _():
        items = []
        for res in [p2_result, order_result]:
            if res is None:
                continue
            for e in res.errors:
                items.append(mo.callout(mo.md(e), kind="danger"))
            for w in res.warnings:
                items.append(mo.callout(mo.md(w), kind="warn"))
        if not items:
            items.append(mo.callout(mo.md("Phase 2 validation passed"), kind="success"))
        return mo.vstack(items)

    return _()


@app.cell
def _(components, mo):
    def _():
        if not components:
            return mo.md("*No components returned.*")
        rows = []
        for c in components:
            rows.append(
                {
                    "Name": c.get("component_name", "?"),
                    "ID": c.get("component_id", "?"),
                    "Modification": c.get("modification", "?"),
                    "Confidence": c.get("confidence", "?"),
                    "Base Exemplar": c.get("base_exemplar", ""),
                    "Params": len(c.get("parameters", {})),
                }
            )
        return mo.ui.table(rows, label="Component list")

    return _()


@app.cell
def _(mo, schema, validated_comps):
    def _():
        if not validated_comps:
            return mo.md("*No validated components to drill down.*")

        tabs = {}
        for comp in validated_comps:
            name = comp.component_name
            schema_entry = schema.get(name, {})
            param_lookup = {p["param_id"]: p for p in schema_entry.get("parameters", [])}
            rows = []
            for pid, val in comp.parameters.items():
                entry = param_lookup.get(pid, {})
                default = entry.get("default_value", "?")
                stats = entry.get("stats", {})
                lo = stats.get("min", "?")
                hi = stats.get("max", "?")
                in_range = "✓" if isinstance(lo, (int, float)) and lo <= val <= hi else "✗"
                rows.append(
                    {
                        "Param": pid,
                        "Value": round(val, 4) if isinstance(val, float) else val,
                        "Default": default,
                        "Min": lo,
                        "Max": hi,
                        "In range": in_range,
                    }
                )
            tabs[name] = mo.ui.table(rows, label=f"{name} parameters")

        return mo.tabs(tabs)

    return _()


@app.cell
def _(format_tonal_target, mo, parse_signal_chain, phase1_input):
    def _():
        if not phase1_input.value:
            return mo.md("")
        _parsed = parse_signal_chain(phase1_input.value)
        _compact = format_tonal_target(_parsed)
        return mo.md(f"### Compact tonal target sent to Phase 2\n\n```\n{_compact}\n```")

    return _()


if __name__ == "__main__":
    app.run()
