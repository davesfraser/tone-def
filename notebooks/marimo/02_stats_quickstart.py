import marimo

app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import polars as pl
    import statsmodels.formula.api as smf
    from scipy import stats
    from statsmodels.stats.anova import anova_lm

    return anova_lm, mo, np, pl, smf, stats


@app.cell
def _(np, pl):
    # All data lives in polars DataFrames
    # scipy accepts numpy arrays directly — use .to_numpy() at the call site
    # statsmodels formula API requires pandas — convert explicitly with .to_pandas()
    # where needed, and label that conversion clearly

    n = 80
    rng = np.random.default_rng(42)

    # Two independent samples for the t-test
    df_ttest = pl.DataFrame(
        {
            "a": rng.normal(loc=0.0, scale=1.0, size=n),
            "b": rng.normal(loc=0.4, scale=1.1, size=n),
        }
    )

    # Correlated pair for Pearson test
    x = rng.normal(size=n)
    df_corr = pl.DataFrame(
        {
            "x": x,
            "y": 0.6 * x + rng.normal(scale=0.8, size=n),
        }
    )

    # Contingency table as a polars DataFrame
    df_contingency = pl.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "outcome": ["Yes", "No", "Yes", "No"],
            "count": [30, 10, 15, 25],
        }
    )

    # One-way ANOVA — three treatment groups
    df_anova = pl.DataFrame(
        {
            "group": (["control"] * n + ["treat_a"] * n + ["treat_b"] * n),
            "value": np.concatenate(
                [
                    rng.normal(loc=0.0, scale=1.0, size=n),
                    rng.normal(loc=0.3, scale=1.0, size=n),
                    rng.normal(loc=0.7, scale=1.0, size=n),
                ]
            ),
        }
    )

    # OLS regression with two predictors
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    df_reg = pl.DataFrame(
        {
            "x1": x1,
            "x2": x2,
            "y": 1.2 + 0.9 * x1 - 0.4 * x2 + rng.normal(scale=1.0, size=n),
        }
    )

    return df_anova, df_contingency, df_corr, df_reg, df_ttest


@app.cell
def _(df_ttest, mo, np, pl, stats):
    # Welch t-test — does not assume equal variances
    # scipy works directly on numpy arrays, so extract with .to_numpy()
    a = df_ttest["a"].to_numpy()
    b = df_ttest["b"].to_numpy()

    ttest_res = stats.ttest_ind(a, b, equal_var=False)

    ci = ttest_res.confidence_interval(confidence_level=0.95)
    cohen_d = (np.mean(a) - np.mean(b)) / np.sqrt(
        ((np.std(a, ddof=1) ** 2) + (np.std(b, ddof=1) ** 2)) / 2
    )

    ttest_df = pl.DataFrame(
        {
            "statistic": [ttest_res.statistic],
            "pvalue": [ttest_res.pvalue],
            "df": [float(ttest_res.df)],
            "ci_low_95": [ci.low],
            "ci_high_95": [ci.high],
            "cohen_d": [cohen_d],
        }
    )

    mo.vstack(
        [
            mo.md("## 1 Welch t-test"),
            mo.ui.table(data=ttest_df.to_pandas(), pagination=False, label="t-test results"),
        ]
    )
    return


@app.cell
def _(df_corr, mo, pl, stats):
    # Pearson correlation
    # Extract numpy arrays for scipy, keep the result in a polars DataFrame
    corr_res = stats.pearsonr(
        df_corr["x"].to_numpy(),
        df_corr["y"].to_numpy(),
    )

    corr_df = pl.DataFrame(
        {
            "r": [corr_res.statistic],
            "pvalue": [corr_res.pvalue],
            "n": [len(df_corr)],
        }
    )

    mo.vstack(
        [
            mo.md("## 2 Pearson correlation"),
            mo.ui.table(data=corr_df.to_pandas(), pagination=False, label="Correlation results"),
        ]
    )
    return


@app.cell
def _(df_contingency, mo, pl, stats):
    # Pivot the tidy polars DataFrame to a contingency matrix for scipy
    contingency_matrix = df_contingency.pivot(on="outcome", index="group", values="count").sort(
        "group"
    )

    chi2, p, dof, _ = stats.chi2_contingency(
        contingency_matrix.select(pl.exclude("group")).to_numpy()
    )

    chi2_df = pl.DataFrame(
        {
            "chi2": [chi2],
            "pvalue": [p],
            "dof": [dof],
        }
    )

    mo.vstack(
        [
            mo.md("## 3 Chi-square test of independence"),
            mo.ui.table(data=chi2_df.to_pandas(), pagination=False, label="Test results"),
        ]
    )
    return


@app.cell
def _(anova_lm, df_anova, mo, smf):
    # statsmodels formula API requires a pandas DataFrame
    # This is an explicit interop boundary — polars is the project default,
    # pandas is used here only because statsmodels requires it
    anova_model = smf.ols("value ~ C(group)", data=df_anova.to_pandas()).fit()
    anova_df = anova_lm(anova_model, typ=2)

    mo.vstack(
        [
            mo.md("## 4 One-way ANOVA"),
            mo.ui.table(data=anova_df, pagination=False, label="ANOVA table"),
        ]
    )
    return


@app.cell
def _(df_reg, mo, smf):
    # Same interop boundary — to_pandas() only because statsmodels requires it
    ols_model = smf.ols("y ~ x1 + x2", data=df_reg.to_pandas()).fit()
    summary_text = ols_model.summary().as_text()

    mo.vstack(
        [
            mo.md("## 5 OLS regression"),
            mo.plain_text(summary_text),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
