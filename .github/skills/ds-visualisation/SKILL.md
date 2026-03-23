---
name: ds-visualisation
description: >
  Use when creating charts, plots, figures, or tables. Triggers on: matplotlib,
  seaborn, plotly, altair, plt.plot, sns.histplot, fig, ax, subplot, histogram,
  bar chart, scatter plot, line chart, violin plot, heatmap, colour palette,
  viridis, annotation, legend, axis label, title, figure, savefig, FIGURES_DIR,
  table, report, colour blindness, dual axis, pie chart, visualise, visualize,
  chart, plot, dashboard.
user-invocable: true
---

# Visualisation Standards — ToneDef

---

# ai-assistant-quick-summary

- Match chart type to the question — never default to whatever is easiest
- Exploratory visualisations are for analysts, explanatory are for audiences
- Every explanatory figure needs a title stating the finding, not just the variables
- Design for colour blindness — never red/green only
- Use viridis as the default sequential palette
- Tables for exact values, charts for patterns — never both for the same information

---

# visualisation-and-charts

The core distinction: exploratory visualisations are for you to understand
the data, explanatory visualisations are for communicating a finding to an
audience. These have different standards — exploratory can be rough,
explanatory must be self-contained and unambiguous.

**Chart selection**

RULE: Match chart type to the question — bar for comparing categories, line for trends over time, scatter for relationships between continuous variables, histogram or violin for distributions.
RULE: Avoid pie charts — human perception is poor at comparing arc lengths and angles. A bar chart is almost always better.
RULE: Never use 3D charts for 2D data — the third dimension adds visual noise and distorts perception without adding information.
RULE: Avoid dual-axis charts — they almost always mislead by making the visual relationship between two series appear artificially strong or weak.
RULE: Save figures to `FIGURES_DIR` from `tonedef.paths` — never hardcode output paths.

**Truthfulness**

RULE: Y-axis should start at zero for bar charts — truncating the axis exaggerates differences visually.
RULE: For line charts the zero baseline is context-dependent — the choice must be deliberate and labelled.
RULE: Area must be proportional to value in area-based charts — scaling bubble size by radius rather than area is a common and misleading error.

**Colour**

RULE: Use sequential palettes for continuous magnitude data.
RULE: Use diverging palettes for data with a meaningful centre such as deviation from a target.
RULE: Use qualitative palettes for distinct categories — limit to 5-7 colours maximum before perception degrades.
RULE: Never use red/green as the only distinguishing encoding — check all figures with a colour blindness simulator.
RULE: Use `viridis` as the default sequential palette — it is perceptually uniform and colour-blindness safe.

**Labelling and annotation**

RULE: Every explanatory figure must have a descriptive title stating the finding, not just the variable names.
RULE: Every explanatory figure must have labelled axes with units, a data source note, and an n count.
RULE: Annotate directly on the chart where possible rather than relying on a legend — legends require the reader to look back and forth.
RULE: Show effect sizes and confidence intervals on figures — not just p-values or asterisks.

**Tables**

RULE: Use tables for exact values, charts for patterns and comparisons — do not use both for the same information.
RULE: Right-align numeric columns and align decimal points — misaligned numbers are harder to compare.
RULE: Round to meaningful precision — excess decimal places imply false accuracy.
RULE: Sort tables by the column that matters most — the reader should not have to hunt for the important row.
RULE: Include units in column headers, not in every cell.
RULE: For model comparison tables always include the baseline row and make it visually distinct.

---

# reporting

RULE: Document generated figures in `reports/README.md` — what each figure shows, what data version produced it, and when.
RULE: Figures saved to `reports/figures/` must be reproducible from source code — no manually edited outputs.
RULE: Report results in `reports/` including visualisations, tables, and effect sizes.
