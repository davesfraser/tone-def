---
name: llm-evaluation
description: >
  LLM evals, DeepEval, golden datasets, judge models, rubrics, RAGAS,
  regression thresholds, prompt comparisons, eval reports.
user-invocable: true
---

# LLM Evaluation - ToneDef

# ai-assistant-quick-summary

- Freeze eval data before prompt iteration.
- Pin judge models.
- Compare against a simple baseline.
- Store datasets and golden answers in `evals/`.
- Keep live evals manually gated.

# eval-discipline

RULE: Store evaluation inputs in `evals/datasets/`.
RULE: Store expected answers, rubrics, or labels in `evals/golden/`.
RULE: Do not edit golden data to hide a regression.
RULE: Pin judge model strings, do not use family aliases.
RULE: Report baseline, candidate, cost, and latency together.
RULE: Live evals must run through explicit commands or `workflow_dispatch`, never normal CI.

# metrics

RULE: Use deterministic assertions where possible before using LLM-as-judge metrics.
RULE: For RAG, evaluate retrieval quality separately from answer quality.
