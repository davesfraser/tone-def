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
    from tonedef.retriever import score_exemplar, search_exemplars
    from tonedef.signal_chain_parser import parse_signal_chain
    from tonedef.validation import validate_retrieval

    return parse_signal_chain, search_exemplars, validate_retrieval


@app.cell
def _(mo):
    mo.md(r"""
    # Retrieval Evaluation

    Paste a Phase 1 signal chain output below to evaluate exemplar retrieval
    quality.  Adjust the number of results and score threshold interactively.
    """)
    return


@app.cell
def _(mo):
    signal_chain_input = mo.ui.text_area(
        label="Phase 1 signal chain output",
        placeholder="Paste raw Phase 1 output here...",
        full_width=True,
    )
    n_slider = mo.ui.slider(start=1, stop=20, value=5, step=1, label="Number of exemplars")
    threshold_slider = mo.ui.slider(
        start=0.0, stop=1.0, value=0.1, step=0.05, label="Min score threshold"
    )
    mo.vstack([signal_chain_input, mo.hstack([n_slider, threshold_slider])])
    return n_slider, signal_chain_input, threshold_slider


@app.cell
def _(
    mo,
    n_slider,
    parse_signal_chain,
    search_exemplars,
    signal_chain_input,
    threshold_slider,
    validate_retrieval,
):
    mo.stop(
        not signal_chain_input.value,
        mo.md("*Paste a Phase 1 output above to begin.*"),
    )

    parsed_for_retrieval = parse_signal_chain(signal_chain_input.value)
    _tags = parsed_for_retrieval.tags_characters + parsed_for_retrieval.tags_genres
    _components = [unit.name for section in parsed_for_retrieval.sections for unit in section.units]
    exemplars = search_exemplars(
        signal_chain_input.value,
        n_results=n_slider.value,
        tags=_tags,
        components=_components,
    )
    retrieval_result = validate_retrieval(exemplars, min_score=threshold_slider.value)
    return exemplars, parsed_for_retrieval, retrieval_result


@app.cell
def _(mo, retrieval_result):
    def _():
        items = []
        for w in retrieval_result.warnings:
            items.append(mo.callout(mo.md(w), kind="warn"))
        if not retrieval_result.warnings:
            items.append(mo.callout(mo.md("Retrieval quality OK"), kind="success"))
        return mo.vstack(items)

    _()
    return


@app.cell
def _(exemplars, mo):
    def _():
        if not exemplars:
            return mo.md("*No exemplars found.*")
        rows = []
        for ex in exemplars:
            score = 1.0 - ex.get("distance", 1.0)
            tags = ", ".join(ex.get("tags", [])[:8])
            n_comps = len(ex.get("components", []))
            rows.append(
                {
                    "Preset": ex.get("preset_name", "?"),
                    "Score": round(score, 3),
                    "Tags": tags,
                    "Components": n_comps,
                    "Distance": ex.get("distance", "?"),
                }
            )
        return mo.ui.table(rows, label="Exemplar results")

    _()
    return


@app.cell
def _(exemplars, mo, parsed_for_retrieval):
    def _():
        query_tags = {
            t.lower()
            for t in parsed_for_retrieval.tags_characters + parsed_for_retrieval.tags_genres
        }
        if not query_tags:
            return mo.md("*No query tags to compare.*")

        items = []
        for ex in exemplars[:5]:
            ex_tags = {t.lower() for t in ex.get("tags", [])}
            intersection = query_tags & ex_tags
            union = query_tags | ex_tags
            jaccard = len(intersection) / len(union) if union else 0.0
            items.append(
                mo.md(
                    f"**{ex.get('preset_name', '?')}** — "
                    f"Jaccard: {jaccard:.2f}, "
                    f"overlap: {', '.join(sorted(intersection)) or '(none)'}"
                )
            )
        return mo.vstack(
            [mo.md(f"### Tag overlap (query tags: {', '.join(sorted(query_tags))})"), *items]
        )

    _()
    return


if __name__ == "__main__":
    app.run()
