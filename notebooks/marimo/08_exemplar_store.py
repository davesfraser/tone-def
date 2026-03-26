import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # Cell plan:
    # cell 1:  imports              params ()                                                  returns (mo,)
    # cell 2:  setup                params (mo,)                                               returns (store, search_exemplars, format_exemplar_context, n_presets,)
    # cell 3:  intro_md             params (mo, n_presets,)                                    returns ()
    # cell 4:  store_sample_df      params (mo, store,)                                        returns (store_sample_df,)
    # cell 5:  store_sample_display params (mo, store_sample_df,)                              returns ()
    # cell 6:  tag_coverage         params (mo, store,)                                        returns (tag_coverage_df,)
    # cell 7:  tag_coverage_display params (mo, tag_coverage_df,)                              returns ()
    # cell 8:  query_input          params (mo,)                                               returns (query_input,)
    # cell 9:  exemplar_results     params (mo, query_input, search_exemplars,)                returns (exemplar_results,)
    # cell 10: results_display      params (mo, exemplar_results, format_exemplar_context,)    returns ()
    # cell 11: prompt_block         params (mo, exemplar_results, format_exemplar_context,)    returns ()

    import json

    import polars as pl

    from tonedef.exemplar_store import format_exemplar_context
    from tonedef.paths import DATA_PROCESSED
    from tonedef.retriever import search_exemplars

    _store_path = DATA_PROCESSED / "exemplar_store.json"
    store: list[dict] = json.loads(_store_path.read_text(encoding="utf-8"))
    n_presets = len(store)

    mo.md(f"Exemplar store loaded — **{n_presets} records**.")
    return format_exemplar_context, json, n_presets, pl, search_exemplars, store


@app.cell
def _(mo, n_presets):
    mo.md(f"""
# Exemplar Store — `exemplar_store.py`

`exemplar_store.py` builds a dataset of **{n_presets} factory preset exemplars**
that are injected as few-shot examples into the Phase 2 LLM prompts.

## Why exemplars?

Without grounding, the LLM must guess parameter values from first principles
(clock-position arithmetic and description alone). Real factory presets give it
concrete, validated reference points — actual parameter combinations for
specific tonal characters authored by expert engineers.

## Pipeline

```
data/external/presets/*.ngrr          →   build_exemplar_records()
data/processed/tag_catalogue.json     →   tags per preset (tonal vocabulary)
                                      →   data/processed/exemplar_store.json
                                      →   ChromaDB "gr_exemplars" collection
```

## Runtime flow (inside `map_components()`)

```
signal_chain  →  search_exemplars(query, n=3)  →  format_exemplar_context()
                                               →  {{EXEMPLAR_PRESETS}} injected
```

| Step | Function | Location |
|---|---|---|
| Build records | `build_exemplar_records()` | `exemplar_store.py` |
| Index into ChromaDB | `scripts/build_exemplar_index.py` | script |
| Runtime retrieval | `search_exemplars()` | `retriever.py` |
| Prompt formatting | `format_exemplar_context()` | `exemplar_store.py` |
| Injection | `map_components()` | `component_mapper.py` |
""")
    return


@app.cell
def _(mo, pl, store):
    import random

    _sample = random.sample(store, min(10, len(store)))
    store_sample_df = pl.DataFrame(
        [
            {
                "preset_name": r["preset_name"],
                "tags": ", ".join(r["tags"]) if r["tags"] else "(untagged)",
                "n_components": len(r["components"]),
            }
            for r in _sample
        ]
    )

    mo.md("## Store Sample\n\n10 randomly selected records:")
    return (store_sample_df,)


@app.cell
def _(mo, store_sample_df):
    mo.ui.table(store_sample_df, pagination=False)
    return


@app.cell
def _(mo, pl, store):
    _tagged = sum(1 for r in store if r["tags"])
    _untagged = len(store) - _tagged
    _all_tags: list[str] = [t for r in store for t in r["tags"]]
    _tag_counts: dict[str, int] = {}
    for _t in _all_tags:
        _tag_counts[_t] = _tag_counts.get(_t, 0) + 1

    _top = sorted(_tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    tag_coverage_df = pl.DataFrame([{"tag": k, "preset_count": v} for k, v in _top])

    mo.md(
        f"## Tag Coverage\n\n"
        f"**{_tagged}** presets tagged · **{_untagged}** untagged · "
        f"**{len(_tag_counts)}** unique tags. Top 15 tags by frequency:"
    )
    return (tag_coverage_df,)


@app.cell
def _(mo, tag_coverage_df):
    mo.ui.table(tag_coverage_df, pagination=False)
    return


@app.cell
def _(mo):
    query_input = mo.ui.text_area(
        label="Signal chain / tonal description query",
        placeholder=(
            "e.g. warm clean Fender-style tone with slapback delay and light spring reverb"
        ),
        value="warm clean Fender-style tone with slapback delay and light spring reverb",
        full_width=True,
    )
    mo.vstack(
        [
            mo.md(
                "## Live Exemplar Retrieval\n\nEnter a tonal description to retrieve the 3 most similar factory presets:"
            ),
            query_input,
        ]
    )
    return (query_input,)


@app.cell
def _(mo, query_input, search_exemplars):
    exemplar_results: list[dict] = []
    if query_input.value.strip():
        exemplar_results = search_exemplars(query_input.value.strip(), n_results=3)

    mo.md(
        f"Retrieved **{len(exemplar_results)}** exemplar(s) for query: "
        f'*"{query_input.value.strip()}"*'
    ) if query_input.value.strip() else mo.callout(mo.md("Enter a query above."), kind="warn")
    return (exemplar_results,)


@app.cell
def _(exemplar_results, mo):
    if not exemplar_results:
        _display = mo.callout(mo.md("No exemplars retrieved."), kind="warn")
    else:
        _cards = []
        for _ex in exemplar_results:
            _tag_str = ", ".join(_ex["tags"]) if _ex["tags"] else "*(untagged)*"
            _dist = _ex.get("distance", 0.0)
            _comp_lines = []
            for _c in _ex["components"]:
                _params = "  ".join(f"`{k}`={v:.3f}" for k, v in list(_c["parameters"].items())[:6])
                _ellipsis = " …" if len(_c["parameters"]) > 6 else ""
                _comp_lines.append(
                    f"- **{_c['component_name']}** (id {_c['component_id']}): {_params}{_ellipsis}"
                )
            _comps_md = "\n".join(_comp_lines)
            _cards.append(
                mo.callout(
                    mo.md(
                        f"**{_ex['preset_name']}** — distance `{_dist:.4f}`\n\n"
                        f"Tags: {_tag_str}\n\n"
                        f"{_comps_md}"
                    ),
                    kind="success",
                )
            )
        _display = mo.vstack([mo.md("### Matched Exemplars"), *_cards])
    _display


@app.cell
def _(exemplar_results, format_exemplar_context, mo):
    if exemplar_results:
        _ctx = format_exemplar_context(exemplar_results)
        _display = mo.vstack(
            [
                mo.md(
                    "### Formatted `{{EXEMPLAR_PRESETS}}` Block\n\nThis is the exact text injected into the LLM prompt:"
                ),
                mo.md(f"```text\n{_ctx}\n```"),
            ]
        )
    else:
        _display = mo.md("")
    _display


if __name__ == "__main__":
    app.run()
