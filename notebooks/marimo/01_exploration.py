# marimo is our notebook-style workflow
# Unlike .ipynb files, this stays as normal Python code in git

import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    # Starter variable for the next cell to use
    name = "world"
    return (name,)


@app.cell
def _(mo, name):
    # Show markdown output in the notebook/app
    mo.md(f"# Hello, {name}!")
    return


if __name__ == "__main__":
    app.run()
