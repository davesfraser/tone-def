---
name: marimo
description: >
  Use when creating, writing, editing, or debugging marimo notebooks for ToneDef.
  Activate for any .py file containing @app.cell decorators, marimo notebook
  structure, reactive execution, cell outputs, UI elements, dataframe display,
  plotting, layout, mo.md, mo.ui, mo.hstack, mo.vstack, marimo App definition,
  cell dependencies, variable scoping, or converting Jupyter notebooks to marimo.
  Triggers on: marimo, @app.cell, mo.ui, mo.md, app = marimo.App, reactive notebook.
user-invocable: true
---

# Marimo Notebook Standards - ToneDef

---

# plan-first

RULE: Before writing any notebook code, produce a cell dependency plan as a
comment block:
```
# Cell plan:
# cell 1: imports           params ()           returns (mo, pl)
# cell 2: load_raw_data     params (pl)         returns (df_raw,)
# cell 3: display_schema    params (mo, df_raw) returns ()
# cell 4: clean_data        params (df_raw)     returns (df_clean,)
```

RULE: Every variable that appears in a cell's parameter list must be returned
by exactly one upstream cell — verify this in the plan before writing any code.
RULE: No variable name may appear in more than one cell's return tuple.
RULE: Generate cells that exactly match the plan.

---

# ai-assistant-quick-summary

- Plan the cell dependency graph before writing any code
- Every global variable must be defined in exactly one cell
- Cell parameters = variables needed from upstream; return tuple = variables exported downstream
- The last expression of a cell is its visual output — not a return statement
- Never use `plt.show()` — return `fig` from the inner `def _():` as the last expression
- Never use `mo.mpl.interactive()` — it has known rendering bugs across platforms
- Never write raw HTML strings — use marimo's built-in components
- Never mutate a variable defined in another cell — use a new variable name
- For cells with mostly throwaway variables, wrap the body in `def _():` and call it as the last expression with `return _()`
- Only prefix with `_` when mixing one or two locals with exported variables
- `print()` appears in the console, not the cell output area

---

# file-structure

RULE: Every marimo notebook must follow this exact module-level structure:
```python
import marimo                          # module-level import — no alias here
app = marimo.App(width="medium")       # must immediately follow import marimo

@app.cell
def _():
    import marimo as mo                # mo alias lives inside cells only
    return (mo,)

# ... remaining cells ...

if __name__ == "__main__":
    app.run()
```

RULE: `import marimo` and `app = marimo.App()` at module level — VS Code requires this to recognise the file as a marimo notebook.
RULE: `import marimo as mo` belongs inside the first cell, not at module level.
RULE: `if __name__ == "__main__": app.run()` must be the last line.
RULE: Do not add `__generated_with = ...` manually — marimo writes this itself.

---

# variable-scoping

RULE: Every global variable must be defined by exactly one cell — reusing a
name across cells causes MultipleDefinitionError.
RULE: Execution order is determined by variable dependencies, not cell position.
RULE: Cell function parameters must exactly match variable names returned by
upstream cells — marimo injects dependencies by name. A missing parameter
causes NameError at runtime.
RULE: Never mutate a variable from another cell — assign to a new name instead.
RULE: Never use `global`.

**Two patterns for local variables — choose based on how many locals the cell has:**

**Pattern 1 — `_` prefix:** use when a cell exports some variables and has
one or two local intermediates:
```python
@app.cell
def _(df):
    _mask = df["price"] > 0       # local intermediate — prefixed
    df_clean = df.filter(_mask)   # exported — no prefix
    return (df_clean,)
```

**Pattern 2 — inner `def _():`:** use for cells where most variables are
throwaway cells, diagnostics, temporary subsets. Variables inside
the function are fully local and common names like `fig`, `ax`, `result`,
`stats` can be reused freely across multiple cells without conflict.
Call the function as the last expression with `return _()`:
```python
@app.cell
def _(df):
    def _():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()        # fully local — no conflict with other cells
        ax.hist(df["price"], bins=30)
        ax.set_xlabel("Price (£)")
        plt.tight_layout()
        return fig
    return _()                          # call and return — displays the figure
```

**ANTI-PATTERN — parameter missing from signature:**
```python
@app.cell
def _(mo):
    mo.ui.table(stats_df)    # NameError — stats_df not declared as parameter
    return
```
```python
@app.cell
def _(mo, stats_df):         # correct — stats_df declared, marimo injects it
    mo.ui.table(stats_df)
    return
```

**ANTI-PATTERN — variable redefined across cells:**
```python
@app.cell
def _(df):
    df = df.filter(...)      # MultipleDefinitionError — df already defined above
    return (df,)
```
```python
@app.cell
def _(df):
    df_filtered = df.filter(...)   # correct — new variable name
    return (df_filtered,)
```

---

# cell-outputs

RULE: The last expression of a cell is its visual output.
RULE: Do not use `print()` for outputs — appears in console only.
RULE: Do not use `return` for display — return is for passing values downstream.
RULE: To display multiple outputs, use `mo.vstack([...])` or `mo.hstack([...])`.
RULE: To display output during a running loop, use `mo.output.append()`.

---

# cell-return-values

RULE: Return as a tuple — even for a single value: `return (df,)` not `return df`.
RULE: Variables not returned are invisible to all other cells.
RULE: When using an inner `def _():`, call it and return the result:
`return _()` — this is both the display expression and the cell return.

---

# displaying-dataframes

RULE: Use `mo.ui.table(df, pagination=True)` for interactive paginated tables.
RULE: A bare dataframe as the last expression renders marimo's rich viewer — fine for quick inspection.
RULE: Never construct raw HTML table strings.

---

# displaying-plots

RULE: Never use `mo.mpl.interactive()` — it has known rendering bugs and
produces blank output unreliably across platforms.
RULE: Always wrap matplotlib plot code in an inner `def _():` to keep `fig`,
`ax`, and all intermediate variables fully local — they can be reused freely
across multiple plot cells without conflict.
RULE: Always return `fig` from the inner function — never `plt.gca()` or
`plt.gcf()`. `plt.gca()` returns only the last active axes and fails for
multi-axes figures.
RULE: Never call `plt.show()` — it clears the figure and produces no output.
RULE: Call the inner function as the last expression: `return _()`.
RULE: Call `plt.tight_layout()` inside the inner function before returning.
RULE: For plotly / altair — return the figure object directly as the last
expression, no inner function needed.
RULE: Use path constants from `tonedef.paths` when saving notebook artifacts.
```python
# correct — single axes
@app.cell
def _(df):
    def _():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.hist(df["price"], bins=30)
        ax.set_xlabel("Price (£)")
        plt.tight_layout()
        return fig              # always return fig, not plt.gca()
    return _()

# correct — multiple axes
@app.cell
def _(df):
    def _():
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        axes[0].hist(df["price"], bins=30)
        axes[1].hist(df["mileage"], bins=30)
        plt.tight_layout()
        return fig              # must return fig for multi-axes
    return _()

# another plot cell — fig and ax reused freely, no conflict
@app.cell
def _(df):
    def _():
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.scatter(df["mileage"], df["price"])
        ax.set_xlabel("Mileage")
        ax.set_ylabel("Price (£)")
        plt.tight_layout()
        return fig
    return _()
```

---

# layout-and-composition

RULE: Use `mo.hstack([...])` for side-by-side, `mo.vstack([...])` for vertical stacking.
RULE: Use `mo.tabs({"Tab": content})` for tabbed layouts.
RULE: Use `mo.callout(mo.md("..."), kind="warn")` for callouts — kinds: `neutral`, `danger`, `warn`, `success`, `info`.
RULE: Never use raw HTML strings for layout.

---

# markdown-and-text

RULE: Use `mo.md("...")` for all text output.
RULE: Use f-strings inside `mo.md()` to interpolate Python values.
```python
@app.cell
def _(df, mo):
    mo.md(f"Dataset contains **{df.height:,} rows** and **{df.width} columns**.")
    return
```

---

# ui-elements

RULE: Assign UI elements to a variable, display as last expression, return the variable.
RULE: Never access `.value` in the same cell where the element is defined — only in downstream cells.
```python
@app.cell
def _(df, mo):
    year_filter = mo.ui.slider.from_series(df["year"], label="Year")
    year_filter
    return (year_filter,)

@app.cell
def _(df, mo, pl, year_filter):
    filtered = df.filter(pl.col("year") == year_filter.value)
    mo.ui.table(filtered)
    return (filtered,)
```

Common elements: `mo.ui.slider`, `mo.ui.dropdown`, `mo.ui.checkbox`, `mo.ui.text`,
`mo.ui.table`, `mo.ui.dataframe`, `mo.ui.altair_chart`, `mo.ui.run_button`.

---

# expensive-cells

RULE: Use `@mo.cache` to cache expensive cell results across re-runs.
RULE: Use `mo.stop(condition, mo.md("reason"))` to halt a cell and its dependents conditionally.

---

# notebook-conventions

RULE: One notebook, one question.
RULE: All reusable logic belongs in `src/tonedef` - notebooks call functions, they do not reimplement them.
RULE: Keep data loading cells at the top.
RULE: Use descriptive cell function names when the cell has a clear purpose — e.g. `def load_raw_data_(pl):`.
RULE: Use `@app.cell(hide_code=True)` for cells where the output is the point.
