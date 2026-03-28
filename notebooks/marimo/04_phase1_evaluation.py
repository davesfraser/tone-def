# applied-skills: marimo, ds-workflow
import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")

# Cell plan:
# cell 1: imports            params ()                          returns (mo,)
# cell 2: lib_imports        params ()                          returns (anthropic, settings, generate_signal_chain, parse_signal_chain, validate_phase1, format_tonal_target)
# cell 3: header             params (mo,)                       returns ()
# cell 4: query_input        params (mo,)                       returns (query,)
# cell 5: run_phase1         params (query, anthropic, settings, generate_signal_chain, parse_signal_chain, validate_phase1) returns (raw_output, parsed_chain, phase1_result)
# cell 6: validation_display params (mo, phase1_result)         returns ()
# cell 7: parsed_display     params (mo, parsed_chain)          returns ()
# cell 8: compact_view       params (mo, parsed_chain, format_tonal_target) returns ()
# cell 9: raw_vs_parsed      params (mo, raw_output, parsed_chain) returns ()
# cell 10: tags_display      params (mo, parsed_chain)          returns ()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import anthropic

    from tonedef.pipeline import generate_signal_chain
    from tonedef.settings import settings
    from tonedef.signal_chain_parser import format_tonal_target, parse_signal_chain
    from tonedef.validation import validate_phase1

    return (
        anthropic,
        format_tonal_target,
        generate_signal_chain,
        parse_signal_chain,
        settings,
        validate_phase1,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Phase 1 Evaluation

    Enter a tone query and inspect the Phase 1 signal chain output.
    This notebook validates the parser output, shows parsed sections,
    and compares raw vs compact representations.
    """)
    return


@app.cell
def _(mo):
    query = mo.ui.text_area(
        label="Tone query",
        placeholder="e.g. warm singing sustain with a slight chorus shimmer",
        full_width=True,
    )
    query
    return (query,)


@app.cell
def _(
    anthropic,
    generate_signal_chain,
    mo,
    parse_signal_chain,
    query,
    settings,
    validate_phase1,
):
    mo.stop(not query.value, mo.md("*Enter a query above to begin.*"))

    _client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    raw_output = generate_signal_chain(query.value, _client)
    parsed_chain = parse_signal_chain(raw_output)
    phase1_result = validate_phase1(parsed_chain)
    return (parsed_chain, phase1_result, raw_output)


@app.cell
def _(mo, phase1_result):
    def _():
        items = []
        for e in phase1_result.errors:
            items.append(mo.callout(mo.md(e), kind="danger"))
        for w in phase1_result.warnings:
            items.append(mo.callout(mo.md(w), kind="warn"))
        if phase1_result.is_valid and not phase1_result.warnings:
            items.append(mo.callout(mo.md("Phase 1 validation passed"), kind="success"))
        return mo.vstack(items)

    return _()


@app.cell
def _(mo, parsed_chain):
    def _():
        lines = [f"**Chain type:** {parsed_chain.chain_type} — {parsed_chain.chain_type_reason}"]
        if parsed_chain.confidence:
            lines.append(
                f"**Confidence:** {parsed_chain.confidence} — {parsed_chain.confidence_detail}"
            )
        for section in parsed_chain.sections:
            lines.append(f"\n### {section.title}")
            for unit in section.units:
                gr = f" → *{unit.gr_equivalent}*" if unit.gr_equivalent else ""
                lines.append(f"- **{unit.name}** ({unit.unit_type}) [{unit.provenance}]{gr}")
                for p in unit.parameters:
                    lines.append(f"  - {p.name}: {p.value}")
        return mo.md("\n".join(lines))

    return _()


@app.cell
def _(format_tonal_target, mo, parsed_chain):
    mo.md(
        f"### Compact tonal target (sent to Phase 2)\n\n```\n{format_tonal_target(parsed_chain)}\n```"
    )
    return


@app.cell
def _(mo, parsed_chain, raw_output):
    mo.hstack(
        [
            mo.vstack([mo.md("### Raw output"), mo.md(f"```\n{raw_output}\n```")]),
            mo.vstack(
                [
                    mo.md("### Parsed summary"),
                    mo.md(
                        f"- Sections: {len(parsed_chain.sections)}\n"
                        f"- Total units: {sum(len(s.units) for s in parsed_chain.sections)}\n"
                        f"- Chain type: {parsed_chain.chain_type}\n"
                        f"- Confidence: {parsed_chain.confidence}"
                    ),
                ]
            ),
        ],
        widths=[0.6, 0.4],
    )
    return


@app.cell
def _(mo, parsed_chain):
    def _():
        chars = (
            ", ".join(parsed_chain.tags_characters) if parsed_chain.tags_characters else "*(none)*"
        )
        genres = ", ".join(parsed_chain.tags_genres) if parsed_chain.tags_genres else "*(none)*"
        return mo.md(f"### Tags\n\n**Characters:** {chars}\n\n**Genres:** {genres}")

    return _()


if __name__ == "__main__":
    app.run()
