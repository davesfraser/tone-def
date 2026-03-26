import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import chromadb
    import marimo as mo

    from tonedef.paths import DATA_PROCESSED

    return DATA_PROCESSED, chromadb, mo


@app.cell
def _(DATA_PROCESSED, chromadb, mo):
    _persist_dir = str(DATA_PROCESSED / "chromadb")
    _chroma = chromadb.PersistentClient(path=_persist_dir)

    exemplar_col = _chroma.get_collection("gr_exemplars")
    manual_col = _chroma.get_collection("gr_manual")

    mo.md(
        f"**Connected to ChromaDB** at `{_persist_dir}`\n\n"
        f"- `gr_exemplars`: **{exemplar_col.count():,}** documents\n"
        f"- `gr_manual`: **{manual_col.count():,}** documents"
    )
    return exemplar_col, manual_col


@app.cell
def _(mo):
    _EXAMPLE = (
        "Amp: Lead 800 on high-gain channel, gain 7, bass 5, mid 7, treble 6, presence 6\n"
        "Cabinet: Matched Cabinet with SM57 close mic\n"
        "Stomp: Tube Screamer style overdrive, drive 3, tone 6\n"
        "Modulation: Chorus with slow rate, subtle depth\n"
        "Delay: Tape echo, 350ms, moderate feedback\n"
        "Reverb: Spring reverb, medium mix\n"
        "\n"
        "TAGS\n"
        "Characters: Warm Crunch Bluesy Sustained Vintage\n"
        "Genres: Blues Rock Classic Rock\n"
    )

    query_text = mo.ui.text_area(
        value=_EXAMPLE,
        label="Query text (edit or paste Phase 1 output)",
        full_width=True,
        rows=12,
    )
    n_results_slider = mo.ui.slider(start=1, stop=20, value=5, step=1, label="Results")

    mo.vstack([query_text, n_results_slider])
    return n_results_slider, query_text


@app.cell
def _(exemplar_col, mo, n_results_slider, query_text):
    _results = exemplar_col.query(
        query_texts=[query_text.value],
        n_results=n_results_slider.value,
        include=["documents", "metadatas", "distances"],
    )

    _rows = [
        {
            "rank": i + 1,
            "preset_name": meta.get("preset_name", ""),
            "distance": round(dist, 4),
            "document": doc,
        }
        for i, (doc, meta, dist) in enumerate(
            zip(
                _results["documents"][0],
                _results["metadatas"][0],
                _results["distances"][0],
                strict=False,
            )
        )
    ]

    mo.vstack(
        [
            mo.md("### Exemplar Results (`gr_exemplars`)"),
            mo.ui.table(_rows, pagination=False),
        ]
    )
    return


@app.cell
def _(manual_col, mo, n_results_slider, query_text):
    _results = manual_col.query(
        query_texts=[query_text.value],
        n_results=n_results_slider.value,
        include=["documents", "metadatas", "distances"],
    )

    _rows = [
        {
            "rank": i + 1,
            "component_name": meta.get("component_name", ""),
            "category": meta.get("category", ""),
            "distance": round(dist, 4),
            "text": doc[:200],
        }
        for i, (doc, meta, dist) in enumerate(
            zip(
                _results["documents"][0],
                _results["metadatas"][0],
                _results["distances"][0],
                strict=False,
            )
        )
    ]

    mo.vstack(
        [
            mo.md("### Manual Results (`gr_manual`)"),
            mo.ui.table(_rows, pagination=False),
        ]
    )
    return


@app.cell
def _(exemplar_col, manual_col, mo):
    def _():
        _ex_sample = exemplar_col.peek(limit=3)
        _man_sample = manual_col.peek(limit=3)

        _ex_docs = "\n".join(
            f"- **{_ex_sample['ids'][i]}**: {_ex_sample['documents'][i]}"
            for i in range(len(_ex_sample["ids"]))
        )
        _man_docs = "\n".join(
            f"- **{_man_sample['ids'][i]}**: {_man_sample['documents'][i][:150]}..."
            for i in range(len(_man_sample["ids"]))
        )

        return mo.vstack(
            [
                mo.md("### Sample Documents"),
                mo.md(f"**gr_exemplars** (first 3):\n\n{_ex_docs}"),
                mo.md(f"**gr_manual** (first 3):\n\n{_man_docs}"),
            ]
        )

    _()
    return


if __name__ == "__main__":
    app.run()
