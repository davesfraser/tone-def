---
name: ds-eda
description: >
  Use when exploring data, loading raw data for the first time, or writing
  initial data inspection code. Triggers on: missing values, null counts,
  duplicates, cardinality, class balance, distribution, histogram, value_counts,
  describe, schema validation, data types, outliers, correlation, pairwise,
  df.shape, head, tail, unique, nunique, missingness, data quality, skew,
  imbalance, EDA, exploratory, profiling, sanity check, raw data, interim data.
user-invocable: true
---

# EDA Standards — ToneDef

---

# ai-assistant-quick-summary

- EDA before any modelling or confirmatory analysis
- Treat all EDA findings as exploratory — validate on held-out data
- Raw data is read-only — never write to `data/raw/`
- Document findings in `reports/` not just in notebook cells
- Exploratory visualisations are for analysts — explanatory ones are separate

---

# data-integrity

RULE: Raw data is read-only.
RULE: Never write outputs to `data/raw/`.
RULE: Validate schemas at ingestion boundaries — check columns, types, and nullability before any processing.
RULE: State data types explicitly on load — never allow implicit casting to hide mismatches.
RULE: Null handling must be explicit — document how many nulls exist and why they are present.
RULE: Document every data transformation from raw to processed so the pipeline is fully reproducible.

---

# exploratory-data-analysis

RULE: Conduct EDA before modelling or confirmatory analysis.
RULE: Treat EDA as genuinely exploratory — findings that look significant must be tested on fresh or held-out data.
RULE: For every variable examine: distribution shape, central tendency, spread, missingness, outliers, and cardinality.
RULE: Examine pairwise correlations, conditional distributions, and whether relationships are linear, monotonic, or neither before assuming any functional form.
RULE: Check class balance before any classification work — document the imbalance ratio and decide on a handling strategy before modelling.
RULE: Detect duplicate rows and near-duplicate records — duplicates spanning train and test sets cause leakage.
RULE: Examine the relationship between missingness and other variables — missing not at random is a substantive finding, not just a data quality issue.
RULE: Document EDA findings explicitly in `reports/` — insights that live only in a notebook cell are lost.
RULE: Distinguish between outliers that are data errors and outliers that are genuine extreme values — the treatment is different and must be documented.
RULE: Exploratory visualisations are for analysts — explanatory visualisations for communication are a separate task with higher standards.

---

# reproducibility

RULE: Fix random seeds using `numpy.random.default_rng(seed)` — never `random.seed()` or `np.random.seed()`.
RULE: Pin the seed in `settings.py`: `rng = np.random.default_rng(settings.random_seed)`.
RULE: Every analysis producing outputs must be runnable end-to-end from raw data with a single command.
RULE: Document data version alongside every result — a result without a data version is not reproducible.
RULE: Persist expensive intermediate computations to `data/interim/` to avoid recomputation.

---

# notebook-hygiene

RULE: One notebook, one question — do not let a notebook grow to answer multiple unrelated questions.
RULE: No business logic in notebook cells — reusable logic belongs in `src/`.
RULE: Keep data loading cells isolated at the top — makes data sources easy to swap.
RULE: Cells should be stateless where possible — avoid side effects that depend on execution order.
RULE: Exploratory notebooks can be rough — the standard rises when a notebook becomes a deliverable.
RULE: Use marimo's built-in components (`mo.ui.table`, `mo.stat`) rather than raw HTML strings.
RULE: Every cell that produces a value used by another cell must return it explicitly.
