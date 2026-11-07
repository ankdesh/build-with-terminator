# Scenario 3: Find a demand trend

**Question:** How can we see the demand pattern when daily rental counts move up and down?

**Useful for:** An operations analyst who reviews demand before a planning meeting.

**Time:** About 15–20 minutes. **Model access:** Required for authoring and the final chat question. Start with the [shared setup](README.md#prepare-once). This scenario is independent of the sales report.

## 1. Load the daily observations

1. Create a new project named `Daily rental demand`.
2. In **Data input**, upload [bike_daily.csv](../../tutorials/data/bike_daily.csv). In the file chooser, its path from the repository root is `tutorials/data/bike_daily.csv`.
3. Check that the profile has `731` rows. Each row is one day. The file covers 2011 and 2012.
4. Save this **Business context**:

   ```text
   Historical daily bike rental data. dteday is the date. cnt is the total rental count for that day, equal to casual + registered. One row represents one day. Use the supplied observations to describe historical demand. A moving average summarizes observed values; it is not a forecast.
   ```

## 2. Create four views

Set chat context to **Project** and paste:

```text
Create a small daily rental demand dashboard.

Use one Data cleaning stage returning cleaned. Parse dteday as datetime, read cnt as integer, sort by dteday ascending, and add calendar_year from the parsed date. Retain all rows and source columns. Do not fill values or deduplicate.

Add a root select parameter calendar_year, label Calendar year, default All/null, choices 2011 and 2012 as numbers. It filters calendar_year in cleaned before Analysis. It is a control, not a widget.

Use one Analysis stage taking cleaned. After filtering and date sorting, calculate rolling_mean_7 = cnt.rolling(7, min_periods=1).mean(). This is a trailing average using the current day and up to six preceding days. Return exactly four outputs: days (row count), total_rentals (sum cnt), average_daily_rentals (mean cnt), and daily_demand (DataFrame with date formatted YYYY-MM-DD, cnt, and rolling_mean_7). Declare parameters_used on the stages.

Create exactly four widgets: Days (metric), Total rentals (metric), Average daily rentals (metric, two decimals), and Daily demand (standard line chart bound to daily_demand; date on X and cnt plus rolling_mean_7 on Y). Label rental units and distinguish the two series. Do not add forecasting, extra controls, or extra widgets.

Keep the original CSV unchanged. Save the stages for review; I will select Run.
```

1. Check the proposal for one cleaning stage, one analysis stage, one control, and four widgets.
2. Select **Apply**, then **Run**. Wait for success.
3. Open **Visualization**. Confirm that the chart dates run from `2011-01-01` to `2012-12-31`.

## 3. Check the result

| Calendar year | Days | Total rentals | Average daily rentals |
| --- | ---: | ---: | ---: |
| All | 731 | 3,292,679 | 4,504.35 |
| 2011 | 365 | 1,243,103 | 3,405.76 |
| 2012 | 366 | 2,049,576 | 5,599.93 |

1. Select **Open dashboard**. Set **Calendar year** to `2011` under **Filters and scenarios**, then select **Apply controls**.
2. Compare the metrics with the table.
3. Inspect the first week in the chart. On `2011-01-01`, both values are `985`. On `2011-01-07`, daily rentals are `1,510` and the seven-day average is about `1,344.71`.
4. Select `2012` and apply. Confirm `366` days. The first day's moving average should equal that day's count because the average is calculated after the year filter.
5. Reset the year to **All** and apply.

The moving average reduces short daily swings. It uses past and current observations. It does not estimate future rentals or explain the causes of demand.

## 4. Ask a question about saved evidence

Return to the builder, which still has its default All-years run. Set chat context to **Project** and send:

```text
Explain how Daily demand calculates its trailing 7-day average. Why is the first value equal to the first day's count? Use the saved calculation and run evidence. Answer only; do not edit the report or run new calculations.
```

Check that the answer describes `min_periods=1` and a window containing the current day. It must not call the moving average a forecast. Dashboard-only filter changes do not change the builder's saved results.

## Demonstrate it in three minutes

1. Show daily rentals and the moving average on the same chart.
2. Filter to one year and point to the matching metrics.
3. Explain the first-week check to show how you verified the formula.
4. Show the chat explanation of the saved calculation.

**Done when:** Both yearly checks match and you can explain the moving average without treating it as a prediction.

Next: [Reuse and hand over a report](04-reuse-and-handoff.md).
