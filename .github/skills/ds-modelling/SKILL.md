---
name: ds-modelling
description: >
  Use when building models, writing preprocessing code, or setting up training
  pipelines. Triggers on: Pipeline, fit, transform, train_test_split,
  cross_val_score, GridSearchCV, RandomizedSearchCV, ColumnTransformer,
  StandardScaler, OneHotEncoder, feature engineering, feature selection,
  class_weight, imbalanced, SMOTE, random_state, baseline model, logistic
  regression, decision tree, random forest, xgboost, lightgbm, sklearn,
  hyperparameter, overfitting, underfitting, leakage, group split, TimeSeriesSplit,
  StratifiedKFold, train set, validation set, modelling, pipeline.
user-invocable: true
---

# Modelling Standards — ToneDef

---

# ai-assistant-quick-summary

- Train/test split before any preprocessing
- Use scikit-learn Pipeline to encapsulate all preprocessing
- Establish a baseline before any complex model
- Never tune hyperparameters on the test set
- Use class_weight='balanced' for imbalanced classes — not SMOTE
- Set random_state on all stochastic components

---

# data-leakage-prevention

RULE: Split train/test before any preprocessing — fit all transformers on train only, transform both.
RULE: Use scikit-learn `Pipeline` to encapsulate preprocessing — this structurally prevents most common leakage patterns.
RULE: For time-series data always use temporal splits — random splits allow future data to predict the past.
RULE: Watch for group leakage — if related records such as the same patient, user, or location can appear in both train and test, split by group not by row.
RULE: Prefer `class_weight='balanced'` for imbalanced classes — avoid SMOTE unless its distributional assumptions are explicitly understood and justified.
RULE: Feature selection must occur inside the cross-validation loop, not before splitting.
RULE: Hyperparameter tuning must use the validation set or inner CV loop — never the test set.

---

# modelling

RULE: Establish a simple baseline before any complex model — mean predictor for regression, majority class for classification, logistic regression for tabular data. Complexity is not justified if it does not beat the baseline convincingly.
RULE: Set `random_state` in all stochastic models and scikit-learn components.
RULE: Parameterize all model hyperparameters via `settings.py` — never hardcode them.
RULE: Use cross-validation for model selection and hyperparameter tuning.
RULE: Document what was tried and what did not work — negative results are information.
RULE: Feature engineering transformations must be reproducible functions in `src/` — not ad-hoc notebook code.

---

# reproducibility

RULE: Fix the train/test split index and store it — if you re-split you cannot compare results.
RULE: Set `random_state` in all stochastic components.
RULE: Every pipeline must be runnable end-to-end from raw data with a single command.
RULE: Persist trained models to `models/` with a clear naming convention that includes the model type and version.

---

# structured-modelling-checklist

RULE: Follow this checklist before generating any modelling code:

1. Confirm EDA is complete and findings are documented.
2. Confirm research question and primary metric are pre-specified.
3. Confirm minimum effect size is pre-specified.
4. Split train/test (and validation) before any preprocessing.
5. Apply transformations inside a scikit-learn Pipeline on train only.
6. Establish baseline model and record its metrics.
7. Check for data leakage and confirm all assumptions.
8. Select modelling approach and pre-specify hyperparameter tuning plan.
9. Tune using cross-validation on training data only.
10. Document each approach tried and why it was accepted or rejected.
