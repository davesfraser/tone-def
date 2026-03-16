---
name: ds-workflow
description: >
  ALWAYS activate this skill first when given a business question, an
  analytical goal, a dataset to explore, or a modelling task. This skill
  sequences all other skills in the correct order. Do not begin any
  analysis without first consulting this skill. Triggers on: analyse,
  question, dataset, model, predict, explore, investigate, value, estimate,
  forecast, classify, what is, how much, which, why, should I.
user-invocable: true
---

# DS Workflow Orchestrator — ToneDef

This skill sequences the canonical data science workflow. When given an
analytical goal, follow these stages in order. Do not skip stages. Do not
begin modelling before EDA is complete and documented.

---

# canonical-workflow
```
Stage 1 — Problem Definition
Stage 2 — Data Acquisition and Validation    → ds-eda, marimo
Stage 3 — Exploratory Data Analysis         → ds-eda, ds-visualisation, marimo
Stage 4 — Hypothesis Generation             → output: documented in reports/
Stage 5 — Confirmatory Design               → ds-stats, ds-visualisation, marimo
Stage 6 — Data Preparation                  → ds-modelling, ds-eda, marimo
Stage 7 — Modelling                         → ds-modelling, marimo
Stage 8 — Evaluation                        → ds-evaluation, ds-visualisation, marimo
Stage 9 — Communication                     → ds-visualisation
```

For each stage, apply the corresponding skill. Do not proceed to the next
stage until the current stage outputs are documented.

---

# stage-1-problem-definition

Before touching any data:

RULE: State the business question in one sentence.
RULE: Identify the primary metric that will answer it.
RULE: Pre-specify the minimum effect size that would be practically meaningful.
RULE: Identify known confounders and data limitations.
RULE: Distinguish whether this is exploratory work (hypothesis generation)
or confirmatory work (hypothesis testing) — they require different designs
and cannot use the same data for both.

Output: a markdown summary at the top of the first notebook cell.

---

# stage-2-data-acquisition-and-validation

Apply skill: `ds-eda`, `marimo`

RULE: Load raw data using functions from `src/tonedef` — never
load data directly in notebook cells.
RULE: Validate schema immediately on load — columns, types, nullability.
RULE: Document data provenance in `data/raw/README.md`.
RULE: Never modify `data/raw/` — write all outputs to `data/interim/`.

---

# stage-3-exploratory-data-analysis

Apply skills: `ds-eda`, `ds-visualisation`, `marimo`

RULE: EDA generates hypotheses — it does not test them.
RULE: Examine every variable before examining any relationships.
RULE: Check distributions, missingness, outliers, cardinality, and class
balance before any transformation or modelling.
RULE: Document all findings in `reports/` before proceeding to stage 4.
RULE: EDA outputs belong in a dedicated notebook —
`notebooks/marimo/01_eda.py`.

---

# stage-4-hypothesis-generation

RULE: Based on EDA findings, state hypotheses explicitly in plain language.
RULE: Record these as the starting point of `reports/analysis.md`.
RULE: Hypotheses generated from EDA must be tested on held-out or fresh
data — not the data they were generated from. This is the HARKing boundary.
RULE: If no held-out data is available, treat all findings as exploratory
and state this explicitly in the report.

---

# stage-5-confirmatory-design

Apply skills: `ds-stats`, `ds-visualisation`, `marimo`

RULE: For each hypothesis from stage 4, pre-specify before analysis:
  - null and alternative hypothesis in plain language
  - the statistical test to use and why
  - the significance threshold
  - the minimum effect size for practical relevance
  - multiple comparisons correction method if running more than one test
RULE: Do not run any tests until all of the above are documented.

---

# stage-6-data-preparation

Apply skills: `ds-modelling`, `ds-eda`, `marimo`

RULE: Train/test split happens here — before any preprocessing.
RULE: Fix the split index and store it in `data/interim/`.
RULE: All preprocessing goes inside a scikit-learn Pipeline.
RULE: Feature engineering functions live in `src/tonedef` —
not in notebooks.

---

# stage-7-modelling

Apply skills: `ds-modelling`, `ds-evaluation`, `ds-visualisation`, `marimo`

RULE: Baseline model first — always. Record baseline metrics before
building anything more complex.
RULE: Work in `notebooks/marimo/02_modelling.py`.
RULE: Serialise trained models to `models/` with a versioned filename.

---

# stage-8-evaluation

Apply skill: `ds-evaluation`, `marimo`

RULE: Evaluate on the held-out test set only — once, at the end.
RULE: Report multiple metrics. Never accuracy alone.
RULE: Run SHAP analysis. Evaluate subgroups.
RULE: Document all results in `reports/` before proceeding to stage 9.

---

# stage-9-communication

Apply skill: `ds-visualisation`, `marimo`

RULE: Produce explanatory visualisations for the report — these are
different from the exploratory ones produced in stage 3.
RULE: Every figure saved to `reports/figures/` must be registered in
`reports/figures/README.md`.
RULE: Every report in `reports/` must follow the template in
`reports/README.md`.
RULE: Document what was tried and rejected alongside what worked.

---

# resuming-mid-workflow

If the user asks to continue an existing analysis rather than start a
new one, first check:

1. What stage has been completed — look for evidence in `reports/` and
   `notebooks/marimo/`.
2. Whether EDA findings are documented before attempting modelling.
3. Whether train/test split has been performed before any preprocessing.

State which stage you are resuming from before generating any code.
