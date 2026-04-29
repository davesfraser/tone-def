# ToneDef Eval Fixtures

`evals/datasets/` contains frozen deterministic inputs for prompt rendering,
retrieval quality, and preset component validity checks. `evals/golden/`
contains the matching expected labels, rubrics, or assertions.

These files are regression evidence. Prompt or retrieval changes should update
the relevant fixture rows, add new rows, or state clearly that no eval applies.

Live LLM evals stay manual-only through `.github/workflows/evals.yaml`; default
pytest and CI runs must not require provider API keys.
