# Algorithm guide

Open [index.html](index.html) in a browser. Start with **Group and compare**, then use **Next topic**. Change the example above each chart. Read the steps, inspect the values, and open **Project connection** to see the saved output and chart binding.

The explanations use short sentences and define technical terms. They follow an approximately 80% ASD-STE100 style; they are not certified controlled English.

The guide works from a local file. It uses the existing ECharts asset in `tutorials/assets`, without a CDN, model, builder, or network request. Keep it in this checkout. Browser controls select precomputed examples. They do not execute Python in the browser or edit a project.

## Topics

1. Group totals, filters, and discount arithmetic → metrics, bars, and tables.
2. Histogram bins and quantiles → histogram and box plot.
3. Pearson and Spearman correlation → scatter plot and heatmap.
4. Trailing moving average → two-series line chart.
5. Naive, exponential smoothing, and ARIMA forecasts → holdout check and future line.
6. Beam search and Welch comparison → subgroup spotlight.
7. Ridge and rate–mix attribution → floating waterfall.
8. PELT change points and lag checks → aligned timelines.
9. Ridge prediction and Mahalanobis distance → scenario estimate and range check.
10. Constrained goal search and Monte Carlo draws → recipe comparison and outcome box plot.

Each topic states its integration level. A Python helper that returns chart options is different from a dedicated builder control. The what-if service has registered session API routes; the current `frontend/src` does not call those routes.

## Rebuild

From the repository root, use the project environment:

```bash
python scripts/build_algorithm_guide.py
```

The script reads bundled CSVs and calls the current calculation helpers. It writes `examples.js` and performs numeric and chart-contract checks. The handwritten page, styles, and interaction code remain separate. It makes no model calls and writes no project state.

## Design and verification contract

This is an explanatory comparison tool, not a live monitoring dashboard. One topic is visible at a time, with at most two SVG ECharts instances. The page owns navigation and accessible tables. ECharts owns chart geometry. The URL fragment stores topic and example; Back, Forward, and copied links restore the selection. Unknown fragments return to the first example. No local storage is required.

Read each topic in this order: question → chart and result → calculation steps → values → project connection → limits. On narrow screens, navigation becomes a horizontal list and the same reading order remains. Controls have visible labels, keyboard focus, and at least 44-pixel targets. Values remain available in a table without hover. A missing chart library leaves the text and tables available. Reduced-motion mode uses the same static charts; all chart animation is disabled. Print styles retain the selected example, values, source links, and limits.

| Visual layer | Data and purpose | Encoding and primary specialist | Check |
| --- | --- | --- | --- |
| Totals | Ten synthetic invoice lines; compare selected groups | Zero-based bars, scalar metrics; standard ECharts bindings | 800 CU total; India 530 CU; 10% discount 720 CU |
| Distribution | Bundled wine alcohol values; show spread | Fixed bins and min/max box plots; statistical visualization | Histogram counts conserve observations; quantiles ordered |
| Relationship | Bundled penguins and wine; show association | Numeric scatter and fixed −1…+1 matrix; statistical visualization | pandas correlations; complete 6×6 matrix |
| Time summary | First 21 bundled bike days; show smoothing | Raw and trailing-average lines; statistical visualization | First value unchanged; seventh mean checked |
| Forecast | 60 seeded synthetic daily values; compare methods | Observed/forecast lines, ARIMA interval, holdout panel; statistical visualization | Real helper outputs; chronological split; interval type explicit |
| Spotlight | Seeded subgroup fixture; locate a low mean | Group mean bars and reference line; statistical visualization | Actual helper ranking; sample counts and search limits |
| Attribution | Two seeded cohorts; reconcile a mean change | Floating bars and exact residual; statistical visualization | Baseline plus displayed deltas equals current |
| Timeline | Three seeded series; locate change order | Aligned line panels and change markers; statistical visualization | Actual PELT results; no-break case; no causal claim |
| Scenario | Seeded two-input sample; inspect predictions | Baseline/scenario bars and joint-distance check; statistical visualization | Actual ridge weights, predictions, and OOD flags |
| Recipes | Same fitted sample; seek a target | Prediction bars and outcome quantiles; statistical visualization | Actual optimizer results; achieved target checked; ordered percentiles |
| Calculation flow | One selected algorithm and artifact route | Numbered HTML steps, output → binding → renderer; SVG/DOM guidance | Source paths, output fields, and renderer calls checked |

The statistical and SVG/DOM specialist passes are performed locally. Neutral slate shows context, teal shows the selected result, blue shows an observed or comparison series, and amber shows a limit. Signed heatmap colours have their own labelled scale. Each chart has a text takeaway and a tabular equivalent.

The build checks formulas and saved chart contracts. The timeline needs a small adapter: its helper emits local `axisPointer.link` entries, but the current chart validator rejects every `link` key. The guide removes those entries and shows the adapter in the calculation tab. This preserves detected data and removes linked-pointer interaction.

Browser QA checks every example, browser errors, offline loading, URL restoration, keyboard operation, 390/768/1440-pixel layouts, and print rendering. This guide explains current behaviour. It does not change or certify the underlying statistical helpers.
