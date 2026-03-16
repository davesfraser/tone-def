# ToneDef

Web application and prompt interface for guitarists to find ther ultimate tone

## What this project assumes

This project is set up for code-first data science work.

Use `src/` for reusable project code.

Use `notebooks/marimo/` for exploration and quick analysis.

## First steps

```bash
uv sync
uv run pre-commit install
git add .
git add uv.lock
git commit -m "Initial project setup"
```

Open the project in VS Code after that:

```bash
code .
```

## Common commands

Format code:

```bash
uv run ruff format .
```

Lint:

```bash
uv run ruff check src tests notebooks
```

Check marimo notebooks:

```bash
uv run marimo check notebooks/marimo
```

Type check:

```bash
uv run mypy src tests
```

Run tests:

```bash
uv run pytest
```

Optional packaging check:

```bash
uv build
```

Open the starter notebook:

```bash
uv run marimo edit notebooks/marimo/01_exploration.py
```

## Project layout

```text
src/                    reusable project code
tests/                  automated tests
notebooks/marimo/       exploratory notebook-style work
data/                   raw, interim, processed, external
models/                 model artefacts
reports/figures/        generated figures
```

## Dependency groups

By default, `uv sync` installs:

- base dependencies
- `dev`
- `notebook`
- `data`
- `stats`

Optional groups are available when needed:

- `validation`
- `vis-static`
- `vis-interactive`
- `ml`
- `app`

Examples:

```bash
uv sync --group validation
uv sync --group vis-static --group vis-interactive
uv sync --group ml
uv sync --all-groups
```

## Adding dependencies

Use `uv add` to keep the project metadata and lockfile in sync.

Examples:

```bash
uv add duckdb
uv add --dev mypy
uv add --group vis-static matplotlib seaborn
uv add --group ml xgboost
```

If code in `src/` imports a package, that package belongs in base dependencies.

If a dependency is only for a particular optional workflow, put it in a named group.

## Lockfile

This project expects `uv.lock` to be committed.

The first `uv sync` creates it.

CI uses the committed lockfile and runs with `--frozen`.
