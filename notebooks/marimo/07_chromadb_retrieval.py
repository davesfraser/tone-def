import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    # Cell plan:
    # cell 1: imports          params ()                                      returns (mo,)
    # cell 2: setup            params (mo,)                                   returns (search_by_hardware, search_by_descriptor, n_indexed, peek_data,)
    # cell 3: collection_stats params (mo, n_indexed, peek_data,)             returns (peek_df,)
    # cell 4: peek_display     params (mo, peek_df,)                          returns ()
    # cell 5: hw_queries       params (mo, search_by_hardware,)               returns (hw_results,)
    # cell 6: hw_display       params (mo, hw_results,)                       returns ()
    # cell 7: desc_queries     params (mo, search_by_descriptor,)             returns (desc_results,)
    # cell 8: desc_display     params (mo, desc_results,)                     returns ()
    # cell 9: context_assembly params (mo, desc_results,)                     returns ()

    from tonedef.retriever import (
        _get_collection,
        search_by_descriptor,
        search_by_hardware,
    )

    _col = _get_collection()
    n_indexed = _col.count()

    _peek = _col.peek(10)
    peek_data = [
        {
            "component_name": _peek["metadatas"][i]["component_name"],
            "category": _peek["metadatas"][i]["category"],
            "text_preview": (
                _peek["documents"][i][:120] + "..."
                if len(_peek["documents"][i]) > 120
                else _peek["documents"][i]
            ),
        }
        for i in range(len(_peek["ids"]))
    ]

    mo.md(f"Collection loaded — **{n_indexed} documents** indexed.")
    return (n_indexed, peek_data, search_by_descriptor, search_by_hardware)


@app.cell
def _(mo):
    mo.md("""
    # ChromaDB Retrieval Layer — `retriever.py`

    `retriever.py` provides the semantic search layer used by Phase 2 when the
    hardware mapping table cannot resolve a component.

    The ChromaDB collection `"gr_manual"` indexes all 121 components from
    `gr_manual_chunks.json` using `all-MiniLM-L6-v2` embeddings (cosine space).
    It is built once by `scripts/build_retrieval_index.py` and queried at runtime.

    **Two retrieval functions — same collection, different query intent:**

    | Function | Query string | Used when |
    |---|---|---|
    | `search_by_hardware(name)` | `"Guitar effect or amplifier similar to: {name}"` | Hardware name has no mapping row |
    | `search_by_descriptor(descriptor)` | Raw tonal description | Signal chain contains no recognisable hardware names |
    """)
    return


@app.cell
def _(mo, n_indexed, peek_data):
    import polars as pl

    peek_df = pl.DataFrame(peek_data)

    mo.vstack(
        [
            mo.md(f"## Collection Overview\n\n**{n_indexed} components** indexed. Sample of 10:"),
            mo.ui.table(peek_df, pagination=False),
        ]
    )
    return (peek_df,)


@app.cell
def _(mo, peek_df):
    import polars as pl

    _cat_counts = (
        peek_df.group_by("category").agg(pl.len().alias("count")).sort("count", descending=True)
    )
    mo.vstack(
        [
            mo.md("Category breakdown in the peek sample:"),
            mo.ui.table(_cat_counts, pagination=False),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## `search_by_hardware()` — Hardware Name Fallback

    When `lookup_hardware()` returns no mapping rows for a hardware name, Phase 2
    calls `search_by_hardware()` to semantically retrieve the closest GR7 components.

    The query is prefixed: `"Guitar effect or amplifier similar to: {name}"` — this
    tilts the embedding toward gear descriptions rather than generic text matches.

    Lower distance = more similar (cosine space, values 0.0-2.0).
    """)
    return


@app.cell
def _(search_by_hardware):
    _queries = [
        "Dallas Arbiter Fuzz Face",
        "Univox Uni-Vibe",
        "Tape echo",
        "Electro-Harmonix Big Muff Pi",
        "MXR Phase 90",
        "Roland Space Echo RE-201",
        "Boss HM-2 Heavy Metal",
    ]

    hw_results = {name: search_by_hardware(name, n_results=4) for name in _queries}
    return (hw_results,)


@app.cell
def _(hw_results, mo):
    import polars as pl

    _rows = []
    for _hw_name, _hits in hw_results.items():
        for _hit in _hits:
            _rows.append(
                {
                    "query": _hw_name,
                    "component_name": _hit["component_name"],
                    "category": _hit["category"],
                    "distance": round(_hit["distance"], 3),
                }
            )

    _df = pl.DataFrame(_rows)

    mo.vstack(
        [
            mo.md(f"Results across {len(hw_results)} hardware name queries:"),
            mo.ui.table(_df, pagination=True),
            mo.callout(
                mo.md(
                    "**Distance interpretation:** values below ~0.4 indicate strong semantic overlap. "
                    "Values above ~0.6 are weak matches — the component shares little tonal vocabulary "
                    "with the hardware description."
                ),
                kind="info",
            ),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## `search_by_descriptor()` — Descriptor Route

    Used when the Phase 1 signal chain contains **no recognisable hardware names** at all.
    The tonal description is used directly as the query — no prefix added.

    This is the fallback for purely descriptive queries like *"give me something warm and
    fuzzy with tape echo"* where Phase 1 produces a descriptive signal chain rather than
    specific hardware recommendations.

    `n_results=8` (vs 5 for hardware) to give the LLM broader coverage across component
    categories.
    """)
    return


@app.cell
def _(search_by_descriptor):
    _descriptors = [
        "bright clean jangly chime with tremolo and spring reverb, low gain",
        "high gain scooped metal rhythm, tight low end, fizzy top end",
        "warm bluesy overdrive, edge of breakup, mid-forward, open dynamics",
        "ambient shimmer with long reverb decay, clean tone, wide stereo",
    ]

    desc_results = {desc: search_by_descriptor(desc, n_results=8) for desc in _descriptors}
    return (desc_results,)


@app.cell
def _(desc_results, mo):
    import polars as pl

    _tabs = {}
    for _desc_text, _hits in desc_results.items():
        _rows = [
            {
                "rank": i + 1,
                "component_name": r["component_name"],
                "category": r["category"],
                "distance": round(r["distance"], 3),
            }
            for i, r in enumerate(_hits)
        ]
        _short_label = _desc_text[:50] + "..." if len(_desc_text) > 50 else _desc_text
        _tabs[_short_label] = mo.ui.table(pl.DataFrame(_rows), pagination=False)

    mo.vstack(
        [
            mo.md("Results for each tonal descriptor query (8 results each):"),
            mo.tabs(_tabs),
            mo.callout(
                mo.md(
                    "**Stratified retrieval:** results are fetched per category "
                    "(Amplifiers x2, Distortion x2, Dynamics x1, Modulation x1, "
                    "Delay/Echo x1, Reverb x1) then merged by distance. "
                    "A query dominated by a single tonal noun (e.g. 'reverb') "
                    "still returns amps and drive units for the full signal chain."
                ),
                kind="success",
            ),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Context Assembly for `DESCRIPTOR_SELECTION_PROMPT`

    When Phase 2 takes the descriptor route, `_build_retrieved_candidates_context()`
    formats the retrieval results into a numbered block injected into
    `{{RETRIEVED_CANDIDATES}}` in `DESCRIPTOR_SELECTION_PROMPT`.

    The format for each result is:
    ```
    [Component Name] (Category)
    First 400 characters of the manual description...
    ```
    """)
    return


@app.cell
def _(desc_results, mo):
    def _format_context(results: list) -> str:
        sections = []
        for r in results:
            name = r["component_name"]
            category = r.get("category", "")
            text = r.get("text", "")
            trimmed = text[:400].rstrip()
            if len(text) > 400:
                trimmed += " ..."
            sections.append(f"[{name}] ({category})\n{trimmed}")
        return "\n\n".join(sections)

    _first_query = next(iter(desc_results.keys()))
    _first_results = desc_results[_first_query]
    _context_block = _format_context(_first_results)

    mo.vstack(
        [
            mo.md(
                f"**Query:** *{_first_query}*\n\n**Assembled `{{RETRIEVED_CANDIDATES}}` block ({len(_first_results)} entries):**"
            ),
            mo.md(
                f"```\n{_context_block[:1200]}{'...' if len(_context_block) > 1200 else ''}\n```"
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
