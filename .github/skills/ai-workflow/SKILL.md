---
name: ai-workflow
description: >
  Start here for LLM features, RAG pipelines, agents, prompt changes, evals,
  schemas, cassettes, safety reviews, cost budgets, latency budgets.
user-invocable: true
---

# AI Workflow - ToneDef

# ai-assistant-quick-summary

- Define success, budget, and failure modes before code.
- Design Pydantic schemas before prompt iteration.
- Keep prompts in `src/tonedef/prompt_templates/`.
- Add deterministic tests before live evals.
- Record eval evidence for prompt or retrieval changes.

# workflow

RULE: Start every LLM feature by writing the user goal, expected output, cost budget, latency budget, and unacceptable failure modes.
RULE: Design input and output schemas in `src/tonedef/schemas/` before changing prompts.
RULE: Put prompt templates in `src/tonedef/prompt_templates/*.jinja`.
RULE: Route all production LLM call sites through `src/tonedef/client.py`; do not add direct provider SDK calls to app, notebook, or reusable pipeline code.
RULE: Add mocked tests that pass with `uv run pytest --record-mode=none`.
RULE: Freeze or update eval rows in `evals/datasets/` and `evals/golden/` before comparing prompt variants.
RULE: Use `/llm-safety` before exposing user input, retrieved context, tools, or traces.

# stage-order

RULE: Use `/llm-schemas` for contracts, then `/llm-prompts`, then `/llm-testing`, then `/llm-evaluation`.
RULE: Use `/llm-rag` only for retrieval work.
