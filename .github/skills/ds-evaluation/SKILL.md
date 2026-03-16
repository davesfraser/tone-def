---
name: ds-evaluation
description: >
  Use when evaluating model performance or reporting results. Triggers on:
  accuracy, precision, recall, F1, AUC, ROC, confusion matrix, classification
  report, log loss, Brier score, calibration curve, SHAP, feature importance,
  MAE, RMSE, R2, mean absolute error, subgroup, fairness, baseline comparison,
  predict_proba, score, evaluate, metrics, test set, held-out, explainability,
  shap.Explainer, shap_values, CalibratedClassifierCV, cross_val_predict.
user-invocable: true
---

# Evaluation Standards — ToneDef

---

# ai-assistant-quick-summary

- Never evaluate on the training set
- Reserve the final test set until all development is complete
- No single metric tells the complete story — use multiple
- Always establish and report a baseline
- Calibrate probability outputs
- Evaluate on meaningful subgroups, not just overall

---

# model-evaluation

RULE: Never evaluate on the training set — this is a category error, not a simplification.
RULE: Reserve a final test set untouched until all model development and tuning is complete — evaluating on test during development and reporting that performance as if it were a fresh evaluation is a form of leakage.
RULE: Use cross-validation for model selection and hyperparameter tuning, not the test set.
RULE: No single metric tells the complete story — select a combination appropriate to the problem and interpret them together.
RULE: Never report accuracy alone for classification — it is misleading for imbalanced classes. Report precision, recall, F1, and AUC together at minimum.
RULE: For classifiers outputting probability scores use log loss — it rewards calibrated probabilities which accuracy and F1 do not.
RULE: Calibrate probability outputs — a model that says 80% probability should be right 80% of the time. Use calibration curves and Brier scores to diagnose this.
RULE: Establish a simple baseline before evaluating any complex model — mean predictor for regression, majority class for classification, logistic regression for tabular data.
RULE: Use SHAP values to explain predictions — prefer `shap.Explainer` over model-specific explainers. Built-in feature importances are misleading for correlated features.
RULE: For regression report MAE alongside RMSE — MAE is interpretable in domain units, RMSE penalises large errors more heavily. Report both and explain the tradeoff.
RULE: Evaluate model performance on meaningful subgroups not just overall — a model that performs well on average but poorly on a minority subgroup is not a good model.
RULE: Report effect sizes and confidence intervals on evaluation metrics, not just point estimates.
RULE: Document negative results and rejected approaches — what you tried and why it was rejected is as valuable as what worked.

---

# evaluation-checklist

RULE: Follow this checklist before reporting any evaluation results:

1. Confirm the test set was untouched during development.
2. Report baseline metrics alongside model metrics.
3. Report multiple metrics appropriate to the problem.
4. Calibrate probability outputs and report calibration curve.
5. Run SHAP analysis and document key drivers.
6. Evaluate on meaningful subgroups.
7. Report confidence intervals on all metrics.
8. Document results in `reports/` including visualisations and tables.
9. Document what was tried and rejected.
