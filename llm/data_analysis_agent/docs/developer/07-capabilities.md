# Supported data, analysis, and visualizations

## Read the support levels

**Built in** means an implemented contract, UI, or helper exists. **Generated** means chat must create suitable Python or native chart options using installed libraries. Generated support is not a guarantee of correct model output. **Outside current scope** means the product has no supported workflow for it, even if trusted Python could theoretically perform it.

## Input and data support

| Area | Support | Important boundary |
| --- | --- | --- |
| CSV | Built-in upload, replacement, and builder `--csv` startup option | One current CSV per project; default/runtime upload limit 100 MiB |
| Parsed columns | string, number, integer, boolean, datetime | Explicit nullable/type/date contract; reject incompatible replacement input |
| Encoding/delimiter | Revision contract supports encoding and one-character delimiter | Profiling starts with pandas CSV defaults, UTF-8 then Latin-1 fallback; no general import-format wizard |
| Numeric, categorical, date-based tables | Built-in contracts and generated analysis | Column meanings and units come from business context/source definitions |
| Missing/duplicate/constant-value checks | Built-in profiling | Flags do not automatically justify removal or imputation |
| Excel, JSON, SQL, Parquet, APIs, multiple-file joins | Outside the supported input UI | Convert to one documented CSV first; Excel conversion is tutorial preparation only |
| Streaming or scheduled data refresh | Outside current scope | Manual upload/Run/Refresh workflows |
| Very large/out-of-core data | Outside declared capacity | pandas processing and complete in-memory artifacts; 100 MiB is a file-size bound, not a latency guarantee |

## Analysis matrix

| Analysis family | Examples | Implementation path | Evidence or limit |
| --- | --- | --- | --- |
| Descriptive statistics | Counts, sums, mean, median, min/max, grouped averages | Generated pandas/NumPy; built-in profiler summaries | Penguins and retail tutorials |
| Cleaning | Parse dates, normalize strings, fill missing values, documented row rules | Generated cleanup DataFrame steps | Review cleanup effects; retain raw input |
| Grouped comparison/ranking | Country revenue, species counts, top items | Generated groupby/sort/aggregation | Define denominator and metric before charting |
| Composition | Share by species or segment | Generated counts/shares plus pie/stacked chart | Shares must use a stated denominator |
| Distributions | Histograms, quantiles, box-plot summaries | NumPy/pandas; advanced native chart options | Wine tutorial; explicit bins/whisker definition |
| Relationships | Pearson or Spearman correlation, grouped comparisons | Generated pandas/SciPy | Wine/Penguins; association is not causation |
| Statistical tests or custom estimates | Suitable tests and confidence calculations | Generated SciPy/statsmodels | No dedicated test-selection wizard; assumptions and numerical validation required |
| Time-series summaries | Daily aggregation, rolling mean, calendar effects | Generated pandas date operations | Bike tutorial; sorting and date semantics matter |
| Forecasts | Naive, ARIMA(1,1,0), additive exponential smoothing | Built-in statistics.forecast helper called by saved code | Chronological holdout, MAE, baseline; intervals for ARIMA only |
| Scenario calculations | Discount multiplier, quality threshold, forecast horizon | Typed parameter plus explicit saved formula | A what-if formula does not predict behavioral change |
| Computed findings | Counts, correlation notes, forecast assumptions | Generated text from current artifacts | Saved app does not ask the LLM to narrate each target refresh |
| General ML training, AutoML, model registry | Classification/training workflows | Outside current scope | No supported sklearn or runtime package-install workflow |
| Causal inference or automated business decisions | Causal effects/decision policies | No built-in validated workflow | Requires additional design and evidence |

The numerical package contract names pandas, NumPy, SciPy, and statsmodels. Additional third-party packages require a compatible runtime release; users cannot install packages through the saved dashboard.

## Visualization matrix

The four widget kinds are **metric, chart, table, and text**. A native ECharts series name is not an additional widget kind or stage type.

| View | Editing path | Artifact | Current support |
| --- | --- | --- | --- |
| Metric | Properties: title, format, unit | Scalar number or scalar value | Built in |
| Table | Select a declared output; CSV export | DataFrame | Built in; 500-row preview, complete CSV |
| Computed text | Chat calculation; supported display properties | String or scalar | Built in |
| Vertical bar | Properties: bar binding, X, Y columns | DataFrame | Direct binding |
| Line, including multiple Y series | Properties: line binding, X, Y columns | DataFrame | Direct binding |
| Scatter | Properties: numeric X and numeric Y | DataFrame | Direct binding; no automatic causal interpretation |
| Pie | Properties: pie binding, category X and exactly one numeric Y | DataFrame | Direct binding |
| Horizontal ranked bar | Chat; native ECharts axes/options | JSON option dictionary | Generated; retail tutorial |
| Stacked bar | Chat; native series with shared stack | JSON option dictionary | Generated; retail tutorial |
| Stacked area | Chat; native line series with stack and areaStyle | JSON option dictionary | Generated; bike tutorial |
| Histogram | Chat bins/counts, then bar view | Binned DataFrame or native options | Generated; histogram is not a direct binding kind |
| Box plot | Chat five-number arrays and native boxplot options | JSON option dictionary | Generated; wine tutorial |
| Correlation/calendar heatmap | Chat axes, zero-based cell coordinates, visualMap | JSON option dictionary | Generated; wine/bike tutorials |
| Forecast interval band | Chat actual/forecast series plus lower/width stack | JSON option dictionary | Generated; helper supplies model values, not chart options |
| Other ECharts-native structures | Chat and per-feature validation | JSON-only options | Renderer can accept valid native options; not a blanket tested product guarantee |
| Remote maps, external images, JavaScript callbacks, arbitrary React widgets | No supported path | Rejected or unsupported | Chart external assets/links are blocked; no generated JS evaluation |

Do not advertise every ECharts chart family as tested. The renderer uses ECharts, but a product-ready chart needs valid data, source rules, labels, interactions, and export checks. Standard binding choices are limited to bar, line, scatter, and pie.

## Binding examples

```json
{"kind":"bar","x":"species","y":["count"],"x_label":"Species","y_label":"Observations"}
```

A saved native chart output uses `{'option': {...}}`; its widget has `chart_binding=null`. For tables, keep every row in the returned DataFrame. For a large chart, return an explicitly aggregated or sampled view rather than silently truncating the source.

Formats supported by the renderer include automatic, integer, `.1f`, `.2f`, and percent; compatible zero masks such as `0.00` are also read. The Properties dropdown exposes the common choices. Unit labels do not convert values. For example, changing grams to kilograms in a label does not divide the metric by 1000.

## Shared interaction and limits

The designer, live target, and exported app share the renderer and a desktop 12-column layout. Charts use local assets, rich-text tooltips, and supported ECharts legend/zoom interactions. Long standard category axes can receive automatic zoom controls. The application uses SVG for display and a temporary canvas for PNG export. PNG saved-file confirmation in the tutorial browser remains unverified; see [tutorial QA](../../tutorials/qa.json).

Charts are limited to 5000 items per series/dataset. Tables export every saved result row. Filters offer equality/range/literal contains through parameter contracts; control forms offer select, number, integer, string, and boolean. Target changes run only when Apply is selected. Reset changes the form; Apply performs the calculation.
