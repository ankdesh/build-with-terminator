"""Build offline worked examples from current project algorithms, without model calls."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.whatif_service import WhatIfService
from pipeline_core.engine import chart_from_frame, safe_json, validate_chart
from pipeline_core.models import ChartBinding
from pipeline_core.statistics import AnomalySpotlight, BlameBridge, DominoTimeline, forecast

OUT = ROOT / "docs/algorithms/examples.js"
TEAL, BLUE, SLATE = "#087f75", "#3569b7", "#95a3b5"


def frame_chart(frame, kind, x, y):
    labels = {"sales_value":"Sales value (CU)", "count":"Samples", "flipper_length_mm":"Flipper length (mm)",
              "body_mass_g":"Body mass (g)", "dteday":"Date", "alcohol_bin":"Alcohol (% ABV)",
              "predicted_revenue":"Predicted revenue"}
    binding = {"kind": kind, "x": x, "y": y, "x_label":labels.get(x, x.replace("_", " ").capitalize()),
               "y_label":"Rentals" if "cnt" in y else ", ".join(labels.get(c, c.replace("_", " ")) for c in y)}
    return chart_from_frame(frame, ChartBinding.model_validate(binding))["option"], binding


def chart(title, option, note):
    # Keep data and series from the helper; move titles into accessible HTML.
    clean = copy.deepcopy(option)
    clean.pop("title", None)
    if isinstance(clean.get("grid"), dict):
        clean["grid"].update(top=40, bottom=42, containLabel=True)
    return {"title": title, "option": clean, "note": note}


def variant(key, label, metrics, charts, columns, rows, takeaway, worked, output, binding):
    return dict(key=key, label=label, metrics=metrics, charts=charts, columns=columns,
                rows=rows, takeaway=takeaway, worked=worked, output=output, binding=binding)


def lesson(key, short, title, question, intro, status, steps, formula, route, sources, code, limits, data, variants):
    return dict(key=key, short=short, title=title, question=question, intro=intro, status=status,
                steps=steps, formula=formula, route=route, sources=sources, code=code,
                limits=limits, data=data, variants=variants)


def build():
    rng = np.random.default_rng(42)
    lessons = []
    sales = pd.read_csv(ROOT / "docs/scenarios/data/sales_january.csv", dtype={"InvoiceNo": "string"})
    mask = ~sales.InvoiceNo.str.upper().str.startswith("C") & sales.Quantity.gt(0) & sales.UnitPrice.gt(0)
    sales["is_valid_sale"] = mask
    variants = []
    for key, country, discount, kind in [("all", None, 0, "bar"), ("discount", None, 10, "bar"), ("india", "India", 10, "bar"), ("share", None, 0, "pie")]:
        selected = sales if country is None else sales.loc[sales.Country.eq(country)]
        valid = selected.loc[selected.is_valid_sale].assign(sales_value=lambda f: f.Quantity * f.UnitPrice)
        groups = valid.groupby("Country", as_index=False).sales_value.sum()
        total = float(valid.sales_value.sum())
        scenario = total * (1 - discount / 100)
        option, binding = frame_chart(groups, kind, "Country", ["sales_value"])
        assert total == (530 if country else 800)
        variants.append(variant(key, {"all":"All countries", "discount":"10% discount", "india":"India + 10%", "share":"Same totals as a pie"}[key],
            [["Sales value", f"{total:,.2f} CU"], ["Scenario value", f"{scenario:,.2f} CU"], ["Excluded lines", str(int((~selected.is_valid_sale).sum()))]],
            [chart("Sales by country", option, "Bar length shows sales value. The pie uses the same group totals and a total of 800 CU." if kind == "pie" else "Each bar starts at zero. Discount changes the scenario metric only.")],
            ["Country", "Sales value (CU)"], groups.values.tolist(),
            f"Selected sales total {total:,.0f} CU. A {discount}% discount gives {scenario:,.0f} CU if quantities stay the same.",
            f"{total:g} × (1 − {discount}/100) = {scenario:g} CU. The CSV stays unchanged.",
            {"sales_value": total, "scenario_sales_value": scenario, "country_totals": groups.to_dict("records")}, binding))
    lessons.append(lesson("summary", "Group and compare", "Turn rows into a useful total.", "Which country contributes more to sales?",
        "Select the rows. Calculate each valid line. Then add the values within each country.", "Saved Python + standard binding",
        [["Check the rule", "Exclude cancelled lines, zero quantities, and zero prices from sales."], ["Apply the filter", "Select a country before the analysis. All means keep both countries."], ["Group and add", "Multiply quantity by price. Add the valid values for each country."]],
        "sales = Σ(quantity × unit price)", ["CSV + sale rule", "Group totals: DataFrame", "bar / pie binding", "Metric + chart + table"],
        ["docs/scenarios/02-sales-report.md", "pipeline_core/engine.py", "frontend/src/components/Dashboard.tsx"],
        "valid = cleaned.loc[cleaned.is_valid_sale].copy()\nvalid['sales_value'] = valid.Quantity * valid.UnitPrice\ncountry_totals = valid.groupby('Country', as_index=False).sales_value.sum()\nreturn {'country_totals': country_totals}",
        ["Sales value is not profit or refund-adjusted net revenue.", "A discount is an arithmetic assumption. It does not predict customer demand.", "Changing the binding from bar to pie changes the view. It does not recalculate the group totals."],
        "Ten synthetic invoice lines from docs/scenarios/data/sales_january.csv. All prices use one common currency, CU.", variants))

    wine = pd.read_csv(ROOT / "tutorials/data/wine_quality.csv")
    variants = []
    for key, width, wine_type in [("half", .5, None), ("wide", 1, None), ("red", .5, "red")]:
        df = wine if wine_type is None else wine.loc[wine.wine_type.eq(wine_type)]
        edges = np.arange(8, 15 + width / 2, width)
        counts, _ = np.histogram(df.alcohol, bins=edges)
        assert int(counts.sum()) == len(df)
        labels = [f"{a:g}–{b:g}" for a, b in zip(edges[:-1], edges[1:])]
        bins = pd.DataFrame({"alcohol_bin": labels, "count": counts})
        opt, binding = frame_chart(bins, "bar", "alcohol_bin", ["count"])
        names = sorted(df.wine_type.unique())
        q = [np.quantile(df.loc[df.wine_type.eq(n), "alcohol"], [0, .25, .5, .75, 1]).tolist() for n in names]
        assert all(all(a <= b for a, b in zip(v, v[1:])) for v in q)
        box = {"xAxis":{"type":"category", "data":names}, "yAxis":{"type":"value", "name":"Alcohol (% ABV)"}, "series":[{"type":"boxplot", "data":q}]}
        variants.append(variant(key, {"half":"0.5-point bins", "wide":"1-point bins", "red":"Red wine only"}[key],
            [["Samples", f"{len(df):,}"], ["Bin width", f"{width:g} % ABV"], ["Median alcohol", f"{df.alcohol.median():.2f} % ABV"]],
            [chart("Count the values in each bin", opt, "A bin includes its left edge. The last bin also includes the final right edge."), chart("Show the five-number summary", box, "The box spans the 25th to 75th percentiles. The centre line is the median. Whiskers show observed minimum and maximum.")],
            ["Type", "Minimum", "25%", "Median", "75%", "Maximum"], [[n, *v] for n, v in zip(names, q)],
            "Wider bins combine neighbouring counts. They change the chart detail, not the sample count.",
            f"The {len(counts)} bin counts add to {len(df):,}. Quantiles use NumPy's linear interpolation.",
            {"histogram": bins.to_dict("records"), "five_numbers": dict(zip(names, q))}, {"histogram": binding, "boxplot": "Native option; chart_binding=null"}))
    lessons.append(lesson("distribution", "Bins and quantiles", "Show the spread, not only the mean.", "Are the values concentrated or widely spread?",
        "A histogram counts values in ranges. A box plot compresses the sorted values into five positions.", "Tutorial Python + native options",
        [["Set the ranges", "Choose fixed bin edges so comparisons use the same ranges."], ["Count each bin", "Assign each observation to one bin. Check that no observation is lost."], ["Find the quantiles", "Sort values. Find the minimum, 25%, median, 75%, and maximum."]],
        "bin count = number of values within the bin", ["Alcohol values", "Bin table + quantiles", "bar binding / boxplot option", "Histogram + box plot"],
        ["scripts/tutorial_specs.py", "tutorials/reference/wine.json", "pipeline_core/engine.py"],
        "counts, edges = np.histogram(df.alcohol, bins=np.arange(8, 15.5, .5))\nfive = np.quantile(df.alcohol, [0, .25, .5, .75, 1])\nbox = {'option': {'series': [{'type': 'boxplot', 'data': [five.tolist()]}]}}",
        ["These whiskers are min/max. They are not the 1.5 × IQR rule used to identify potential outliers.", "A different bin width can change the apparent shape. Retain the count and unit labels.", "The outcome box plot in Goal search uses 10th/90th percentiles instead. Read each chart's whisker definition."],
        "Bundled UCI wine data, all 6,497 rows. Source and licence: tutorials/ATTRIBUTION.txt.", variants))

    penguins = pd.read_csv(ROOT / "tutorials/data/penguins.csv").dropna(subset=["flipper_length_mm", "body_mass_g"])
    variants = []
    for key, species in [("all", None), ("adelie", "Adelie")]:
        df = penguins if species is None else penguins.loc[penguins.species.eq(species)]
        pearson = float(df.flipper_length_mm.corr(df.body_mass_g))
        spearman = float(df.flipper_length_mm.corr(df.body_mass_g, method="spearman"))
        opt, binding = frame_chart(df, "scatter", "flipper_length_mm", ["body_mass_g"])
        variants.append(variant(key, "All species" if species is None else "Adelie only",
            [["Paired observations", str(len(df))], ["Pearson r", f"{pearson:.3f}"], ["Spearman ρ", f"{spearman:.3f}"]],
            [chart("Flipper length and body mass", opt, "One point is one observation. X is millimetres; Y is grams. Species selection changes the paired sample.")],
            ["Measure", "Value"], [["Pearson: linear association", pearson], ["Spearman: rank association", spearman], ["Paired count", len(df)]],
            "The points rise together in this sample. Filtering one species changes the association you measure.",
            "Pearson compares centred values. Spearman applies Pearson's calculation to ranks; ties receive average ranks.",
            {"pearson": pearson, "spearman": spearman, "paired_rows":len(df), "first_five_points": df[["flipper_length_mm", "body_mass_g"]].head().values.tolist()}, binding))
    fields = ["alcohol", "density", "residual sugar", "volatile acidity", "sulphates", "quality"]
    corr = wine[fields].corr(method="spearman")
    cells = [[x, y, float(corr.iloc[y, x])] for y in range(6) for x in range(6)]
    matrix = {"xAxis":{"type":"category", "data":fields}, "yAxis":{"type":"category", "data":fields},
              "visualMap":{"min":-1, "max":1, "orient":"horizontal", "left":"center", "bottom":0, "inRange":{"color":["#3569b7", "#f7f8fa", "#a44157"]}},
              "grid":{"top":20,"left":115,"right":30,"bottom":105},
              "series":[{"type":"heatmap", "data":cells, "label":{"show":True,"fontSize":11}}]}
    variants.append(variant("matrix", "Wine rank matrix", [["Measurements", "6"], ["Cells", "36"], ["Colour scale", "−1 to +1"]],
        [chart("Compare all ranked pairs", matrix, "Blue is negative. Rose is positive. The diagonal is 1 because each variable is compared with itself.")],
        ["Measurement", *fields], [[f, *corr.loc[f].tolist()] for f in fields],
        "Each cell compares a pair of ranked measurements. The colour scale stays fixed across all pairs.",
        "Cell [x, y, value] uses zero-based axis indices. Row y and column x select the pair.",
        {"labels": fields, "cells": cells}, "Native ECharts heatmap; chart_binding=null"))
    lessons.append(lesson("correlation", "Relationships", "Measure how two values move together.", "Does a larger value tend to occur with a larger partner?",
        "Pearson measures a linear relationship. Spearman measures a relationship between ranks. Both range from −1 to +1.", "Tutorial Python + chart binding",
        [["Keep paired values", "Use rows that contain both measurements. Report how many pairs remain."], ["Compare values or ranks", "Pearson uses measured values. Spearman first replaces each value with its rank."], ["Map the result", "A scatter shows paired observations. A heatmap shows one correlation per pair of columns."]],
        "r = Σ((x − x̄)(y − ȳ)) / √(Σ(x − x̄)² × Σ(y − ȳ)²)", ["Paired numeric columns", "Points + correlation matrix", "scatter / heatmap option", "Relationship view"],
        ["scripts/tutorial_specs.py", "pipeline_core/engine.py", "tutorials/reference/penguins.json"],
        "r = df.flipper_length_mm.corr(df.body_mass_g)\nrho = df[fields].corr(method='spearman')\ncells = [[x, y, float(rho.iloc[y, x])]\n         for y in range(len(fields)) for x in range(len(fields))]",
        ["Association does not establish cause.", "A constant column has no defined correlation. Small samples can be unstable.", "The all-species relationship includes differences between species. It need not match a within-species relationship."],
        "Bundled Palmer Penguins and UCI wine observations. Missing penguin pairs are omitted only for the displayed pair. See tutorials/ATTRIBUTION.txt.", variants))

    bike = pd.read_csv(ROOT / "tutorials/data/bike_daily.csv").sort_values("dteday").head(21).copy()
    variants = []
    for window in [1, 3, 7]:
        df = bike[["dteday", "cnt"]].copy()
        df["rolling_mean"] = df.cnt.rolling(window, min_periods=1).mean()
        assert df.rolling_mean.iloc[0] == df.cnt.iloc[0] == 985
        if window == 7:
            assert round(df.rolling_mean.iloc[6], 2) == 1344.71
        opt, binding = frame_chart(df, "line", "dteday", ["cnt", "rolling_mean"])
        opt["legend"] = {"data":["cnt", "rolling_mean"], "top":0}
        opt["series"][1]["lineStyle"] = {"width":3}
        variants.append(variant(str(window), f"{window}-day window", [["Days shown", "21"], ["Window", f"{window} day(s)"], ["First average", "985"]],
            [chart("Daily rentals and the trailing average", opt, "Blue is the daily count. Teal is the trailing average. The average uses no future observations.")],
            ["Date", "Daily rentals", "Trailing average"], df.values.tolist(),
            "A wider window smooths short swings. It can also respond more slowly to a sudden change.",
            f"On day 7: sum the latest {window} count(s) and divide by {window}. Result = {df.rolling_mean.iloc[6]:,.2f} rentals.",
            {"first_seven_rows": df.head(7).to_dict("records")}, binding))
    lessons.append(lesson("rolling", "Moving average", "Make a noisy trend easier to see.", "What changes when we use a longer averaging window?",
        "Sort by date. At each date, average that day's value and the preceding values inside the window.", "Tutorial Python + line binding",
        [["Order the days", "Sort dates before calculating a window."], ["Move the window", "Use the current day and up to six earlier days for a 7-day window."], ["Draw both series", "Retain daily values so the smoothed line does not hide the original variation."]],
        "trailing mean = sum of available window values / count", ["Ordered daily counts", "DataFrame: date + two series", "line binding", "Daily + average lines"],
        ["docs/scenarios/03-demand-trend.md", "scripts/tutorial_specs.py", "pipeline_core/engine.py"],
        "df = cleaned.sort_values('dteday').copy()\ndf['rolling_mean'] = df.cnt.rolling(7, min_periods=1).mean()\nreturn {'daily_demand': df[['dteday', 'cnt', 'rolling_mean']]}",
        ["A moving average describes observations. It is not a forecast.", "These first 21 days are consecutive. Missing calendar dates would make a seven-row window different from seven calendar days.", "The tutorial calculates the average after filtering. The first selected date therefore starts a new window."],
        "First 21 dates from the bundled daily Bike Sharing CSV. See tutorials/ATTRIBUTION.txt.", variants))

    dates = pd.date_range("2026-01-01", periods=60, freq="D")
    series = pd.Series(100 + np.arange(60) * .8 + 3 * np.sin(np.arange(60) / 3) + rng.normal(0, .8, 60), index=dates)
    variants = []
    for method in ["naive", "exponential_smoothing", "arima"]:
        for horizon in [4, 8]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = forecast(series, horizon=horizon, method=method)
                n_hold = result["holdout_observations"]
                train = series.iloc[:-n_hold]
                check = forecast(train, horizon=n_hold, method=method)
            assert len(result["forecast"]) == horizon
            assert result["training_observations"] + n_hold == len(series)
            labels = series.index.strftime("%m-%d").tolist() + [s[5:] for s in result["timestamps"]]
            future = [None] * len(series) + result["forecast"]
            sers = [{"name":"Observed", "type":"line", "data": series.tolist() + [None] * horizon, "showSymbol":False},
                    {"name":"Forecast", "type":"line", "data": future, "lineStyle":{"type":"dashed", "width":3}, "symbolSize":6}]
            if result["prediction_intervals_95"]:
                lower = [v[0] for v in result["prediction_intervals_95"]]
                width = [v[1] - v[0] for v in result["prediction_intervals_95"]]
                sers += [{"name":"Interval base", "type":"line", "data":[None]*60 + lower, "stack":"interval", "stackStrategy":"all", "symbol":"none", "lineStyle":{"opacity":0}, "itemStyle":{"opacity":0}},
                         {"name":"95% interval", "type":"line", "data":[None]*60 + width, "stack":"interval", "stackStrategy":"all", "symbol":"none", "lineStyle":{"opacity":0}, "areaStyle":{"color":"rgba(8,127,117,.16)"}}]
            opt = {"xAxis":{"type":"category", "data":labels}, "yAxis":{"type":"value", "name":"Demand (units)", "min":80}, "legend":{"data":["Observed", "Forecast"], "top":0}, "series":sers}
            hold_opt = {"xAxis":{"type":"category", "data": series.index[-n_hold:].strftime("%m-%d").tolist()}, "yAxis":{"type":"value", "name":"Demand (units)", "scale":True},
                        "legend":{"data":["Held-out actual", "Model estimate", "Naive baseline"], "top":0},
                        "series":[{"name":"Held-out actual", "type":"line", "data":series.iloc[-n_hold:].tolist()}, {"name":"Model estimate", "type":"line", "data":check["forecast"]}, {"name":"Naive baseline", "type":"line", "data":[float(train.iloc[-1])]*n_hold, "lineStyle":{"type":"dotted"}}]}
            variants.append(variant(f"{method}-{horizon}", f"{ {'naive':'Naive', 'exponential_smoothing':'Smoothing', 'arima':'ARIMA'}[method]} · {horizon} days",
                [["Holdout MAE", f"{result['backtest_mae']:.2f}"], ["Naive MAE", f"{result['baseline_mae']:.2f}"], ["Training / holdout", f"{len(train)} / {n_hold}"]],
                [chart("Fit the full history, then estimate future values", opt, "The dashed forecast is separate from observations. The shaded band appears only for the ARIMA 95% model interval."), chart("Check the method on the last observed days", hold_opt, "These days were held out from the test fit. MAE is the mean absolute error. Lower is better on this holdout.")],
                ["Future date", "Point estimate", "95% lower", "95% upper"], [[t, v, *(result["prediction_intervals_95"][i] if result["prediction_intervals_95"] else [None, None])] for i, (t, v) in enumerate(zip(result["timestamps"], result["forecast"]))],
                "The holdout tests the method on recent unseen values. The final fit then uses all 60 observations.",
                {"naive":"Next estimate = last training value. Every future step receives that same value.",
                 "exponential_smoothing":"Level = α × observed + (1 − α) × (previous level + previous trend). Trend = β × level change + (1 − β) × previous trend. Future = level + steps × trend. The fit estimates α and β; this example has no seasonal term.",
                 "arima":"First take changes: Δy[t] = y[t] − y[t−1]. Fit one autoregressive weight: Δy[t] = φ × Δy[t−1] + error. Forecast the changes, then add them to the last level. The 95% band comes from this fitted ARIMA model."}[method]
                + f" Holdout size = max(2, min({horizon}, 60 // 5)) = {n_hold}.",
                result, "Native line options; chart_binding=null. The helper returns numbers, not a complete chart."))
    lessons.append(lesson("forecast", "Forecasts", "Test a forecast before you trust it.", "How do the three saved forecast methods differ?",
        "Naive repeats the last value. Additive exponential smoothing fits a level and trend. ARIMA(1,1,0) models changes using one previous change.", "Built-in helper → saved chart code",
        [["Hold out recent days", "Use the last observations as a test. Fit without those observations."], ["Compare with a baseline", "Calculate absolute errors. Compare the model with repeating the last training value."], ["Refit and forecast", "Fit on the full series. Return future values and the available uncertainty fields."]],
        "MAE = Σ |forecast − actual| / held-out observations", ["Ordered, equally spaced series", "forecast() numeric result", "Saved code builds line options", "Future line + test metrics"],
        ["pipeline_core/statistics/forecast.py", "examples/electric_dashboard.py", "scripts/tutorial_specs.py"],
        "from pipeline_core.statistics import forecast\nresult = forecast(series, horizon=4, method='arima')\nvalues = result['forecast']\nbounds = result['prediction_intervals_95']\n# Saved analysis code builds the ECharts line series.",
        ["At least ten finite values are required. A date index must be ordered, unique, and equally spaced. Season length, if set, requires three full seasons.", "ARIMA returns 95% model intervals. In this code, p10 and p90 copy those same bounds; their field names do not make them 10th/90th percentiles.", "Other methods use ±1.28 × holdout residual standard deviation for p10/p90. These are not calibrated intervals. They are omitted from this chart.", "The smoothing path can fall back to a linear trend if fitting fails. Constant series use a repeated-value path. A lower holdout error is not a guarantee of future accuracy."],
        "60 synthetic daily demand values with a trend, a smooth fluctuation, and seeded noise. All forecast values come from the current helper.", variants))

    records = []
    for region in ["East", "West"]:
        for device in ["Mobile", "Desktop"]:
            level = 55 if (region, device) == ("East", "Mobile") else 100
            for value in level + rng.normal(0, 3, 40):
                records.append({"Region":region, "Device":device, "Revenue":float(value)})
    cohort = pd.DataFrame(records)
    variants = []
    for key, depth, support in [("single", 1, 5), ("pair", 2, 5), ("small", 2, 70)]:
        result = AnomalySpotlight().isolate_slices(cohort, "Revenue", baseline_val=100, dimension_columns=["Region", "Device"], max_depth=depth, min_support=support)
        top = result.get("culprits", [{}])[0]
        assert top
        rows = [[c["predicate_label"], c["sample_size"], c["slice_mean"], c["rest_mean"], c["score"], c["p_value"]] for c in result["culprits"]]
        variants.append(variant(key, {"single":"One condition", "pair":"Up to two conditions", "small":"Minimum group size 70"}[key],
            [["Selected group", top["predicate_label"].replace(" = ", " ").replace("'", "")], ["Group rows", str(top["sample_size"])], ["Group mean", f"{top['slice_mean']:.2f}"]],
            [chart("Compare the selected group with the remaining rows", result["echarts_option"], "Bars show group means. The dashed line is the supplied reference of 100 CU per row.")],
            ["Condition", "Rows", "Group mean", "Rest mean", "Search score", "Raw p-value"], rows,
            "Two conditions can locate East + Mobile. A larger minimum group size blocks that 40-row group.",
            "Search single conditions. Keep five strong seeds. Add a second condition only if its score improves by more than 5%. Welch t = (group mean − rest mean) / √(group variance/group count + rest variance/rest count).",
            {"selected":top, "candidates":len(result["culprits"])}, "Helper returns echarts_option; wrap as {'option': result['echarts_option']} for a chart widget."))
    lessons.append(lesson("spotlight", "Subgroup search", "Find a group that differs from the rest.", "Which combination of labels contains the low values?",
        "Beam search keeps a few promising groups, then tries a second condition. Welch's test compares each group's mean with the remaining rows.", "Python helper; no dedicated builder page",
        [["Create conditions", "Try category values. Numeric dimensions may be split into Low, Medium, and High groups."], ["Search and score", "Reject groups below the minimum size. Rank their impact. Expand only the strongest seeds."], ["Compare means", "Return the group, remaining-row mean, sample count, score, and raw Welch p-value."]],
        "primary score = max(0, impact) × (1 − group size / total size)", ["Metric + group columns", "Beam search + Welch test", "Native bar + reference", "Spotlight + finding table"],
        ["pipeline_core/statistics/anomaly_spotlight.py", "tests/test_anomaly_spotlight.py", "pipeline_core/engine.py"],
        "from pipeline_core.statistics import AnomalySpotlight\nr = AnomalySpotlight().isolate_slices(\n    df, 'Revenue', baseline_val=100, max_depth=2)\nreturn {'spotlight': {'option': r['echarts_option']}}",
        ["Search scores are not probabilities. With no supplied baseline, comparison uses the remaining rows.", "The helper tests many overlapping groups. Its p-values are not corrected for that search. Use them for exploration, not proof.", "The implementation searches at most two conditions. It is not an exhaustive search over all combinations.", "The confidence badge uses p-value and sample-size thresholds. It is a rule-based label, not a calibrated certainty."],
        "160 synthetic rows: 40 per Region × Device group. East + Mobile has a lower revenue mean. Noise uses a fixed seed.", variants))

    n = 80
    base = pd.DataFrame({"spend":rng.normal(20, 3, n), "price":rng.normal(10, 1, n)})
    current = pd.DataFrame({"spend":rng.normal(25, 3, n), "price":rng.normal(12, 1, n)})
    for df in [base, current]:
        df["Revenue"] = 30 + 4 * df.spend - 2 * df.price + rng.normal(0, 2, n)
    variants = []
    for k in [1, 2]:
        r = BlameBridge().attribute_shift(base, current, "Revenue", ["spend", "price"], top_k=k)
        assert abs(r["baseline_mean"] + sum(s["delta"] for s in r["steps"]) - r["current_mean"]) < 1e-7
        variants.append(variant(f"ridge-{k}", f"Ridge · show {k} driver(s)",
            [["Baseline mean", f"{r['baseline_mean']:.2f}"], ["Current mean", f"{r['current_mean']:.2f}"], ["Mean change", f"{r['total_delta']:+.2f}"]],
            [chart("Reconcile the change in the mean", r["echarts_option"], "Transparent base bars position each signed change. Other factors keeps the displayed sum equal to the current mean.")],
            ["Step", "Signed change", "Running value"], [[s["feature"], s["delta"], s["accumulated_value"]] for s in r["steps"]],
            "A pooled ridge model assigns part of the mean shift to changed feature averages. The remainder stays visible.",
            f"{r['baseline_mean']:.4f} + ({' + '.join(str(s['delta']) for s in r['steps'])}) = {r['current_mean']:.4f}",
            {k:r[k] for k in ["baseline_mean", "current_mean", "steps", "residual"]}, "Native floating waterfall: transparent Base + visible Shift, both stack='bridge'."))
    b = pd.DataFrame({"Channel":["Online"]*30+["Store"]*10,"Revenue":[100]*30+[50]*10})
    c = pd.DataFrame({"Channel":["Online"]*20+["Store"]*20,"Revenue":[110]*20+[60]*20})
    r = BlameBridge().attribute_shift(b,c,"Revenue",["Channel"],method="rate_mix")
    assert abs(r["baseline_mean"] + sum(s["delta"] for s in r["steps"]) - r["current_mean"]) < 1e-7
    variants.append(variant("mix", "Category rate + mix", [["Baseline mean", "87.50"], ["Current mean", "85.00"], ["Mean change", "−2.50"]],
        [chart("A better rate can be offset by a different mix",r["echarts_option"],"Online rate rises from 100 to 110; Store rises from 50 to 60. More lower-rate Store rows reduce the overall mean.")],
        ["Step","Signed change","Running value"], [[s["feature"],s["delta"],s["accumulated_value"]] for s in r["steps"]],
        "Both categories improve, but the combined mean falls because the category shares change.",
        "Rate effect = average share × rate change. Mix effect = average rate × share change. Add both for each category.",
        {k:r[k] for k in ["baseline_mean","current_mean","steps"]}, "Same native waterfall; this example uses the categorical rate–mix path."))
    lessons.append(lesson("bridge", "Change attribution", "Explain a change with a balanced bridge.", "Which terms account for the change between two cohort means?",
        "BlameBridge uses a ridge approximation for numeric features or a rate–mix identity for one categorical feature. The bars must reconcile.", "Python helper; native chart output",
        [["Compare two cohorts", "Compute the baseline and current means of the same metric."], ["Allocate the change", "For numeric inputs, multiply each fitted weight by its mean input change. For one category column, combine rate and share changes."], ["Keep the remainder", "Rank driver sizes. Pool the remainder in Other factors so the bridge balances."]],
        "baseline mean + displayed driver changes + other factors = current mean", ["Baseline + current rows", "Ridge / rate–mix terms", "Floating bar options", "Waterfall + reconciliation"],
        ["pipeline_core/statistics/blame_bridge.py","tests/test_blame_bridge.py","pipeline_core/engine.py"],
        "from pipeline_core.statistics import BlameBridge\nr = BlameBridge().attribute_shift(\n    baseline, current, 'Revenue', ['spend', 'price'])\nreturn {'bridge': {'option': r['echarts_option']}}",
        ["This code uses ridge and rate–mix calculations. It does not calculate SHAP values.", "The target is a mean, not a period sales total. Cohort sizes and metric definitions matter.", "Exact reconciliation does not prove a causal explanation. Correlated inputs can share attribution differently.", "The rate–mix branch assigns r2=0.95 as a fixed value. Its badge is not evidence of a measured regression fit."],
        "Numeric example: two seeded 80-row cohorts. Category example: 40 rows per cohort with explicit rates and shares.",variants))

    variants=[]
    t = np.arange(60)
    for key, penalty in [("detect",None),("strict",200.0)]:
        df=pd.DataFrame({"step":[f"{i:02d}" for i in t], "Load":20+1.5*np.sin(t)+30*(t>=20), "Latency":60+2*np.sin(t/2)+40*(t>=27), "Errors":5+.4*np.cos(t)+10*(t>=34)})
        r=DominoTimeline().detect_cascade(df,"step",["Load","Latency","Errors"],penalty=penalty)
        opt=copy.deepcopy(r["echarts_option"])
        # The saved-chart validator rejects every key named link, including
        # ECharts' local axis-pointer links. Remove those two display links.
        opt.get("axisPointer", {}).pop("link", None)
        opt.get("tooltip", {}).get("axisPointer", {}).pop("link", None)
        # Replace causal wording in display labels; retain detected indices and series.
        for axis in opt["yAxis"]:
            axis["name"] = axis["name"].replace("Root Cause","First change")
            axis["nameLocation"]="end"
            axis["nameTextStyle"].update(fontSize=11)
        for s in opt["series"]:
            for item in s.get("markPoint",{}).get("data",[]):
                if item.get("value")=="T=0 Root": item["value"]="First"
        assert (r["metrics_with_changepoint"]>0) if key=="detect" else (r["metrics_with_changepoint"]==0)
        variants.append(variant(key,"Default penalty" if key=="detect" else "High penalty · no breaks",
            [["Detected metrics",str(r["metrics_with_changepoint"])],["First detected metric",r["root_cause_metric"] if r["metrics_with_changepoint"] else "None"],["Penalty",f"{2*np.log(60):.2f}" if penalty is None else "200"]],
            [chart("Align the detected shifts in time",opt,"Each panel has its own numeric Y scale. The common X axis is sample step; it is not elapsed time." if key=="detect" else "No break is detected. The reference at step 00 is the helper's fallback, not a detected event.")],
            ["Metric","First change step","Delay (steps)","Cross-correlation lag","Correlation"], [[m["metric"],m["changepoint_index"],m["lag_steps"],m["optimal_lag"],m["max_cross_corr"]] for m in r["cascade_order"]],
            "A larger penalty can suppress every split. First detected does not mean proven cause.",
            "PELT balances within-segment squared error against a penalty for extra changes. The displayed delay is a difference between first change indices.",
            {"detected_metrics":r["metrics_with_changepoint"],"cascade_order":r["cascade_order"]},"Native line panels. Remove axisPointer.link entries before binding: the current saved-chart validator rejects those keys, including local links."))
    lessons.append(lesson("timeline","Change points","Find when each series changed.","Which metric has the first detected level shift?",
        "PELT divides a series into sections with different means. A penalty limits extra splits. The helper then orders metrics by their first change.","Python helper; aligned native lines",
        [["Prepare each series","Sort time values. Fill missing numeric values forward and backward. Standardize each series."],["Find the splits","Minimize segment squared error plus a change penalty. Prune candidates that cannot improve the solution."],["Order and compare","Use the earliest detected split as T=0. Compare later split indices and calculate cross-correlation lags."]],
        "cost = sum of within-segment squared errors + split penalties",["Ordered metric columns","PELT + lag comparison","Multiple line grids","Aligned timeline"],
        ["pipeline_core/statistics/domino_timeline.py","tests/test_domino_timeline.py","pipeline_core/engine.py"],
        "from pipeline_core.statistics import DominoTimeline\nr = DominoTimeline().detect_cascade(\n    df, 'step', ['Load', 'Latency', 'Errors'])\noption = r['echarts_option']\noption.get('axisPointer', {}).pop('link', None)\noption.get('tooltip', {}).get('axisPointer', {}).pop('link', None)\nreturn {'timeline': {'option': option}}",
        ["The code names a field root_cause_metric. It identifies a first detected change; temporal order does not prove cause.","If no change is detected, the helper still returns the first metric and timestamp as a fallback. Check metrics_with_changepoint before describing a finding.","lag_steps comes from change indices. optimal_lag comes from cross-correlation. They measure different things.","Forward/backward fill can affect break locations. Sample-step delays are not clock durations. Ties use jump size and then metric name.","The helper emits axisPointer.link. The current saved-chart validator rejects any link key, including these local axis links. This guide removes them before rendering; the code tab shows the required adapter."],
        "60 synthetic observations per metric. Injected shifts occur at sample indices 20, 27, and 34. Values include deterministic fluctuations.",variants))

    sample=pd.DataFrame({"spend":rng.normal(50,8,160),"price":rng.normal(20,3,160)})
    sample["Revenue"]=500+8*sample.spend-12*sample.price+rng.normal(0,15,len(sample))
    service=WhatIfService()
    model=service.fit_surrogate(sample,"Revenue",["spend","price"])
    variants=[]
    for key,values in [("baseline",model.baseline_values),("adjust",{"spend":55,"price":19}),("outside",{"spend":100,"price":5})]:
        pred=service.predict(model,values)
        assert pred.is_ood if key=="outside" else not pred.is_ood
        bars=pd.DataFrame({"case":["Baseline","Selected"],"predicted_revenue":[model.baseline_prediction,pred.predicted_value]})
        opt,binding=frame_chart(bars,"bar","case",["predicted_revenue"])
        variants.append(variant(key,{"baseline":"Baseline inputs","adjust":"Spend 55 · price 19","outside":"Spend 100 · price 5"}[key],
            [["Predicted revenue",f"{pred.predicted_value:.2f}"],["Joint distance",f"{pred.mahalanobis_dist:.2f} / {pred.mahalanobis_critical:.2f}"],["History check", "Outside (red)" if pred.is_ood else pred.zone.capitalize()]],
            [chart("A fitted estimate changes with the input settings",opt,"Bars show model estimates, not observed outcomes. The history check is separate from the estimate.")],
            ["Input","Selected value","Fitted weight","Range zone"], [[f,values[f],model.coefficients[i],pred.lever_zones[f]] for i,f in enumerate(model.feature_names)],
            "The linear model returns a number even outside the observed input range. The range check marks that extrapolation.",
            f"ŷ = {model.intercept:.3f} + ({model.coefficients[0]:.3f} × spend) + ({model.coefficients[1]:.3f} × price). Joint distance² = (x − mean)ᵀ × inverse covariance × (x − mean). This accounts for input scale and how inputs vary together.",
            {"prediction":pred.model_dump(),"coefficients":model.coefficients,"intercept":model.intercept,"r_squared":model.r_squared},binding))
    lessons.append(lesson("scenario","Ridge what-if","Change an input. Check the estimate.","What does the fitted model estimate for a new input combination?",
        "Ridge regression fits one weight per numeric input. A penalty limits large weights. Mahalanobis distance checks how far a combination is from the training inputs.","Registered session API; no current frontend caller",
        [["Choose the inputs","The service suggests varying numeric columns as levers. Review that choice; a numeric column is not automatically controllable."],["Fit the approximation","Centre X and y. Solve the ridge equation. Restore the intercept and retain residual spread."],["Predict and check range","Calculate the weighted sum. Check each input's percentile zone and its joint distance from the training mean."]],
        "weights = (XᵀX + αI)⁻¹Xᵀy; prediction = intercept + Σ(weight × input)",
        ["Complete numeric training rows","Ridge + covariance","Prediction + OOD fields","Estimate + range status"],
        ["backend/services/whatif_service.py","backend/routers/scenario.py","backend/app.py","backend/models/whatif.py"],
        "model = service.fit_surrogate(df, 'Revenue', ['spend', 'price'])\nresult = service.predict(model, {'spend': 55, 'price': 19})\n# Session API: POST /api/sessions/{id}/scenario/predict\n# The current builder frontend does not call this API.",
        ["The ridge equation above uses centred inputs. The intercept is not penalized. The service defaults alpha to 1.","The fit R² is calculated on training data. It is not a held-out accuracy result.","The joint check uses a 99% chi-square threshold. A value outside its 1st/99th percentile also produces a red result. This is a rule, not proof of safety.","This estimate is an association fitted to observed rows. Changing a lever in the model does not establish a causal business effect.","The session API is registered. A dedicated control in the active project frontend is not implemented; this guide demonstrates the backend output."],
        "160 synthetic rows with two numeric inputs and seeded residual noise. The guide calls the actual fit and prediction methods.",variants))

    variants=[]
    for key,multiplier in [("reachable",1.10),("unreachable",4)]:
        goal=model.baseline_prediction*multiplier
        recipes=service.solve_recipes(model,goal,model.baseline_values)
        balanced=recipes[1]
        dist=service.simulate_weather_distribution(model,balanced.slider_values,target_goal=goal,n_sims=1000)
        opt={"xAxis":{"type":"category","data":[r.title for r in recipes]},"yAxis":{"type":"value","name":"Predicted revenue"},"series":[{"type":"bar","data":[r.predicted_target for r in recipes],"markLine":{"symbol":"none","data":[{"yAxis":goal,"label":{"formatter":"Goal"}}]}}]}
        pct=[dist.p10,dist.p25,dist.p50,dist.p75,dist.p90]
        assert pct==sorted(pct)
        variants.append(variant(key,"Goal +10%" if key=="reachable" else "Goal ×4 · beyond bounds",
            [["Target",f"{goal:.2f}"],["Balanced estimate",f"{balanced.predicted_target:.2f}"],["Simulated goal fraction",f"{dist.goal_probability_pct:.1f}%"]],
            [chart("Compare the proposed input recipes",opt,"The dashed line is the target. A recipe can be returned even if its prediction does not reach the target."),chart("Simulated outcomes for the Balanced recipe",dist.echarts_whisker_option,"Whiskers are the simulated 10th and 90th percentiles. The box is the 25th to 75th percentile. This is not a time-series forecast.")],
            ["Recipe","Spend","Price","Predicted revenue","Reaches goal?"], [[r.title,r.slider_values["spend"],r.slider_values["price"],r.predicted_target,r.predicted_target>=goal-.02] for r in recipes],
            "An optimizer proposes settings within observed bounds. The simulation adds fitted residual noise to a chosen estimate.",
            "Balanced minimizes Σ((new input − current input) / input standard deviation)² under a target constraint. Then draw estimate + Normal(0, residual spread).",
            {"goal":goal,"recipes":[r.model_dump() for r in recipes],"simulation":dist.model_dump(exclude={"echarts_whisker_option"})},"Backend emits echarts_whisker_option. A chart widget can use {'option': that_option}; the session response does not create a project widget automatically."))
        variants[-1]["extra_tables"] = [{"title":"Simulated outcome percentiles", "columns":["Percentile", "Outcome"],
            "rows":[["10th", dist.p10], ["25th", dist.p25], ["Median", dist.p50], ["75th", dist.p75], ["90th", dist.p90]]}]
    lessons.append(lesson("recipes","Goals and simulation","Seek a target, then show the spread.","Which input settings approach the goal, and how variable is the fitted outcome?",
        "The service solves for input changes, then samples possible outcomes around the fitted estimate. These are two different calculations.","Registered session API; backend-generated options",
        [["Search inside bounds","The single-lever path tries one input. The Balanced path uses constrained SLSQP optimization over multiple inputs."],["Check the achieved value","A returned recipe may miss an unreachable goal. Compare its predicted target with the requested target."],["Sample the outcome","Add seeded normal residual noise to the fitted estimate. Count draws that meet the target and compute percentiles."]],
        "simulated outcome = fitted estimate + Normal(0, residual standard deviation)",
        ["Fitted model + goal","Bounded optimizer + seeded draws","Recipe fields + boxplot option","Recipe bars + outcome range"],
        ["backend/services/whatif_service.py","backend/routers/scenario.py","tests/test_scenario_studio.py"],
        "cards = service.solve_recipes(model, target_goal, current_values)\ndist = service.simulate_weather_distribution(\n    model, cards[1].slider_values, target_goal=target_goal, n_sims=1000)\noption = dist.echarts_whisker_option",
        ["Balanced and Aggressive currently use the same SLSQP objective and constraints. Different labels do not guarantee different settings.","Feasibility scores are hand-built rules. They are not measured probabilities of implementation success.","The simulated goal fraction assumes additive normal noise with fixed fitted spread. It excludes model-parameter uncertainty and changes in real-world behaviour.","The service calls this a weather distribution. It is an outcome simulation, not a meteorological or time-series forecast. A name does not change the underlying calculation."],
        "Same synthetic model as Ridge what-if. Every recipe and percentile comes from the current backend service; Monte Carlo uses its fixed seed 42.",variants))

    for item in lessons:
        for source in item["sources"]:
            assert (ROOT/source).is_file(), source
        for v in item["variants"]:
            for c in v["charts"]:
                validate_chart(c["option"])
    # Avoid changing the generated asset only because the wall clock changed.
    source_paths = sorted({s for item in lessons for s in item["sources"]} | {
        "scripts/build_algorithm_guide.py", "docs/scenarios/data/sales_january.csv",
        "tutorials/data/wine_quality.csv", "tutorials/data/penguins.csv", "tutorials/data/bike_daily.csv"})
    hashes = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths}
    result = safe_json({"lessons":lessons,"source_hashes":hashes})
    payload=json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text("// Generated by scripts/build_algorithm_guide.py. Do not edit.\nwindow.ALGORITHM_GUIDE = " + payload + ";\n")
    print(f"Built {len(lessons)} topics, {sum(len(s['variants']) for s in lessons)} checked examples: {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
