---
name: ds-stats
description: >
  Use when writing statistical tests, designing experiments, or interpreting
  results. Triggers on: hypothesis test, p-value, significance, confidence
  interval, effect size, Cohen's d, t-test, chi-square, ANOVA, Welch,
  Mann-Whitney, Shapiro, normality, power analysis, sample size, A/B test,
  bootstrap, Bonferroni, Benjamini-Hochberg, multiple comparisons, HARKing,
  null hypothesis, alternative hypothesis, ttest_ind, scipy.stats, statsmodels,
  odds ratio, correlation coefficient, Bayesian, prior, posterior.
user-invocable: true
---

# Statistical Standards — ToneDef

---

# ai-assistant-quick-summary

- State hypotheses before seeing the data
- Report effect sizes and confidence intervals alongside every p-value
- Statistical and practical significance are independent — evaluate both
- Choose the test before seeing the data — not after
- Never interpret non-significant results as evidence of no effect

---

# experimental-design

RULE: State research questions precisely before touching the data — vague questions produce vague analyses.
RULE: Distinguish exploratory from confirmatory work — the same data cannot be used to both generate and test a hypothesis.
RULE: Avoid HARKing (Hypothesizing After Results are Known) — do not present a hypothesis as if it was specified in advance when it was developed after seeing the data.
RULE: Pre-specify primary metrics before analysis — deciding which metric to optimise after seeing results is p-hacking.
RULE: Pre-specify the minimum effect size that would be practically meaningful for this domain before analysis — this cannot be determined from the result itself.
RULE: Identify and document confounding variables before analysis, not after.
RULE: For A/B tests: define minimum detectable effect, run a power analysis, and do not peek at results before reaching the required sample size.
RULE: For observational studies: explicitly state that correlation is not causation and identify alternative explanations.
RULE: Document researcher degrees of freedom — every analysis decision that could have gone another way should be noted.

---

# hypothesis-testing

RULE: State null and alternative hypotheses in plain language before running any test — if you cannot state them plainly you do not yet understand the question.
RULE: Choose the test before seeing the data — choosing the test that produces significance from a menu of options is p-hacking.
RULE: Use Welch's t-test by default for comparing two means — Student's t-test assumes equal variance which is rarely justified.
RULE: Statistical significance and practical significance are independent — always evaluate both. A very low p-value on a small effect size means the sample is large enough to detect noise, not that the finding is actionable. What constitutes a meaningful effect is domain-specific and must be defined before analysis.
RULE: Report effect sizes alongside every p-value — Cohen's d for means, r for correlations, odds ratio for proportions.
RULE: Report confidence intervals, not just point estimates — they convey both magnitude and precision.
RULE: Apply multiple comparisons correction when running more than one test — Bonferroni is conservative but simple, Benjamini-Hochberg is more appropriate for large numbers of tests.
RULE: Never interpret a non-significant result as evidence of no effect — report the power of the test.
RULE: Bootstrap confidence intervals are more appropriate than parametric tests for small samples (n < 30) or non-normal distributions.
GUIDELINE: Treat p-values as guides, not bright lines — p=0.049 and p=0.051 are not meaningfully different.
GUIDELINE: Consider Bayesian methods when genuine prior knowledge exists or when you want to make probability statements about hypotheses directly.

---

# reproducibility

RULE: Fix random seeds using `numpy.random.default_rng(seed)` for any bootstrap or resampling procedure.
RULE: Pin the seed in `settings.py`: `rng = np.random.default_rng(settings.random_seed)`.
RULE: Document data version alongside every result.
