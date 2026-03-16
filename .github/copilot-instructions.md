<!-- This file loads automatically in GitHub Copilot for every request       -->
<!-- It contains project conventions that apply to all tasks                  -->
<!-- Analytical standards are handled by the following skills:                -->
<!--   ds-workflow    — workflow orchestration, invoke first for any analysis -->
<!--   ds-eda         — exploratory data analysis                             -->
<!--   ds-stats       — hypothesis testing and statistical analysis           -->
<!--   ds-modelling   — feature engineering, pipelines, and model building    -->
<!--   ds-evaluation  — model evaluation and diagnostics                      -->
<!--   ds-visualisation — charts, figures, and reporting                      -->
<!--   marimo         — notebook structure and reactive execution             -->
<!-- These skills load automatically based on task context                    -->

# ToneDef

Web application and prompt interface for guitarists to find ther ultimate tone

This repository contains a reproducible data science analysis project.
AI coding assistants must follow the rules in this document when generating code.

---

# Core rules

RULE: When given a business question or analytical goal, always invoke the
ds-workflow skill before generating any code. Do not begin coding until the
workflow stages relevant to the task have been identified and the outputs for
each stage have been listed.
RULE: For every stage that produces a notebook, the marimo skill applies.
RULE: For every stage that produces figures, the ds-visualisation skill
applies and all mandatory figures must be saved to FIGURES_DIR.
RULE: Before writing any code, list the planned deliverables and confirm
they match the required set.
RULE: Every analytical task must produce marimo notebooks in
notebooks/marimo/ for all exploratory stages.
RULE: Every analytical task must produce reusable functions in src/
organised by responsibility — data loading, features, models, visualisation,
and evaluation as separate modules.
RULE: Every analytical task must produce pytest tests covering all src/
functions.
RULE: Every analytical task must produce a script in scripts/ under 100 lines
that orchestrates src/ functions end-to-end.
RULE: Every analytical task must produce a report in reports/ following the
report template.
RULE: Every analytical task must produce figures in reports/figures/
following the naming convention.
RULE: All reusable code lives in `src/tonedef`.
RULE: Notebooks are for exploration only — do not implement reusable logic
inside notebooks.
RULE: Notebooks must remain lightweight and primarily call functions from
`src/`.
RULE: All filesystem paths must be imported from `tonedef.paths`.
RULE: Never construct filesystem paths manually using strings.
RULE: All configuration values must be imported from
`tonedef.settings`.
RULE: All dataframe operations must use Polars.
EXCEPTION: Pandas may only be used when required by an external library.
RULE: When an external library requires pandas, convert at the call site only.
RULE: Label every pandas conversion with a comment identifying which library
requires it.
RULE: Functions in `src/` must include type annotations on all arguments and
return values.
RULE: All Python commands must be executed via `uv run`.
RULE: Scripts must produce deterministic outputs when given the same inputs.
RULE: Scripts orchestrate pipelines — they call `src/` functions, they do
not implement logic directly.
RULE: Scripts must never exceed 100 lines excluding comments and imports — if
a script grows beyond this, logic is leaking out of src/ into the script.
RULE: At the top of every generated file, include a comment stating which
skills were applied — e.g. `# applied-skills: ds-eda, ds-visualisation`.
If no skills were applied, omit the comment.
RULE: Notebooks are named `<stage>_<activity>.py` using underscores —
e.g. `01_eda.py`, `02_hypothesis_testing.py`, `03_modelling.py`.
RULE: Reports are named `YYYY-MM-DD_<activity>.md` using hyphens —
e.g. `2026-03-12_eda_findings.md`, `2026-03-12_model_evaluation.md`.
RULE: Figures are named `<subject>_<chart_type>.png` using underscores —
e.g. `price_distribution_histogram.png`, `mileage_vs_price_scatter.png`.

---

# Project stack

- Python 3.13+
- polars for dataframe operations
- marimo for notebooks
- uv for environment and dependency management
- ruff for linting and formatting
- pytest for testing
- mypy for static type checking

---

# Project structure
```text
src/tonedef/     reusable project code
tests/                      pytest tests
scripts/                    reproducible analysis entrypoints
notebooks/marimo/           exploratory notebooks
data/raw/                   source data — read only, never modified
data/interim/               intermediate data
data/processed/             final datasets
models/                     serialised model artefacts
reports/figures/            generated plots
.github/skills/             Copilot skill definitions
```

---

# Coding rules

RULE: Analysis logic must be implemented as reusable functions in `src/`.
RULE: Notebooks must call functions from `src/`.
RULE: Do not duplicate logic across notebooks.
RULE: Functions must be deterministic and avoid hidden global state.
RULE: New functionality in `src/` must include pytest tests.
RULE: Never write stage functions that combine multiple analytical steps —
e.g. `def stage_3_eda()`, `def stage_6_prepare_data()`. These are
untestable, non-reusable, and conflate data computation, visualisation,
and IO.
RULE: src/ functions must have a single responsibility — data computation,
visualisation, and IO are always separate functions.

---

# Commands

All commands must be executed using `uv run`:
```bash
uv run pytest              # run tests
uv run mypy src tests      # type check
uv run ruff check .        # lint
uv run ruff format .       # format
```

---

# Data science standards

When given a business question or analytical goal, invoke `/ds-workflow`
first. It sequences all other skills in the correct order.
