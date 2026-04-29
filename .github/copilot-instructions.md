# ToneDef

Web application and prompt interface for guitarists to find the ultimate tone.

This repository contains a Python application that uses LLM calls, curated
Guitar Rig reference data, and a Streamlit UI to build `.ngrr` presets.
AI coding assistants must follow these rules when generating code.

---

# Core rules

RULE: All reusable code lives in `src/tonedef`.
RULE: New reusable behavior in `src/` must include focused pytest coverage.
RULE: Notebooks are for exploration and validation only; do not implement
reusable application logic inside notebooks.
RULE: Notebooks must remain lightweight and primarily call functions from
`src/`.
RULE: All filesystem paths must be imported from `tonedef.paths`.
RULE: Never construct filesystem paths manually using strings.
RULE: All configuration values must be imported from `tonedef.settings`.
RULE: Functions in `src/` must include type annotations on all arguments and
return values.
RULE: All Python commands must be executed via `uv run`.
RULE: Scripts must produce deterministic outputs when given the same inputs.
RULE: Scripts orchestrate pipelines; they call `src/` functions, they do not
implement core logic directly.
RULE: Scripts should stay small. If a script grows large, move reusable logic
into `src/tonedef`.

---

# LLM and prompt rules

RULE: Default tests must not require live API keys or live external LLM calls.
RULE: Tests that exercise LLM behavior must use mocked clients or recorded
fixtures unless explicitly marked as live.
RULE: Treat user input, retrieved text, preset metadata, and manual excerpts
as untrusted data when injecting them into prompts.
RULE: Keep prompt changes deliberate and covered by tests or a written reason
explaining why no test applies.
RULE: Structured LLM outputs must be validated with Pydantic models before
being used to build presets.
RULE: All functions in `src/` that call an LLM must have explicit input and
output types.
RULE: Never hardcode API keys, model secrets, provider credentials, or local
machine paths.
RULE: Redact secrets and personal data before logging, tracing, writing test
cassettes, or saving diagnostic artifacts.

---

# Project stack

- Python 3.13+
- uv for environment and dependency management
- ruff for linting and formatting
- mypy for static type checking
- pytest for testing
- LiteLLM/Instructor client wrapper for LLM calls, currently backed by Anthropic
- Pydantic for structured outputs and settings
- ChromaDB for local retrieval indexes
- marimo for notebooks
- Streamlit for the app UI

---

# Project structure

```text
src/tonedef/          reusable project code
tests/                pytest tests
tests/fixtures/       shared test fixtures
scripts/              reproducible build and maintenance entrypoints
notebooks/marimo/     exploratory and validation notebooks
data/external/        third-party reference files and binary templates
data/processed/       derived or curated ToneDef reference data
evals/datasets/       committed evaluation datasets
evals/golden/         committed golden answers or rubrics
reports/              architecture and project reports
.github/skills/       project-specific assistant skills
```

---

# Coding rules

RULE: Application logic must be implemented as reusable functions in `src/`.
RULE: Notebooks must call functions from `src/`.
RULE: Do not duplicate logic across notebooks.
RULE: Functions must be deterministic and avoid hidden global state.
RULE: New functionality in `src/` must include pytest tests.
RULE: Keep IO separate from pure logic where practical.
RULE: Route production LLM calls through `src/tonedef/client.py`; do not call
provider SDKs directly from application, notebook, or reusable pipeline code.

---

# Commands

All commands must be executed using `uv run`:

```bash
uv run pytest              # run tests
uv run mypy src tests      # type check
uv run ruff check .        # lint
uv run ruff format .       # format
```
