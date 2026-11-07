# Scenario 1: Compare energy costs

**Question:** What happens to the estimated electricity cost if the unit price changes?

**Useful for:** A facilities analyst who wants to compare a tariff assumption for the same measured usage.

**Time:** About 10 minutes. **Model access:** Not required. Start with the [shared setup](README.md#prepare-once).

## 1. Load and run the example

1. In the builder, select **Load energy example** in the left sidebar. This creates a separate project with saved stages. Do not upload `sample_data/electric_usage.csv` over this project: the loader has already selected and renamed the three columns that the example requires.
2. Select **Pipeline**. Follow Data input → Data cleaning → Analysis → Visualization.
3. Open **Data cleaning**. Read the rule that removes exact duplicates and readings with missing kWh. This file has neither, so the rule should remove zero rows.
4. Select **Run**. Wait for the run to succeed.
5. Open **Visualization** and check the result. This example also has forecast widgets; use the usage, cost, and zone widgets for this exercise.

## 2. Check the starting result

With all zones selected and **Price per kWh** at `0.15`:

| Check | Expected result |
| --- | ---: |
| Input and cleaned readings | 360 → 360 |
| Total kWh | 19,511.36 |
| Estimated cost, rounded to two decimals | 2,926.70 |
| Zone-A usage | 5,132.22 kWh |
| Zone-B usage | 11,837.78 kWh |
| Zone-C usage | 2,541.36 kWh |

The formula is `estimated cost = total kWh × price per kWh`. The example does not specify a currency. Use a consistent currency for your unit price and cost.

## 3. Change one assumption

1. Select **Open dashboard** in the builder sidebar.
2. In the dashboard, open **Filters and scenarios**.
3. Set **Price per kWh** to `0.20`. Select **Apply controls**.
4. Check that **Total kWh** stays at `19,511.36` and **Estimated cost** becomes `3,902.27`.
5. Open the controls again. Select `Zone-A` in **Zone**, keep the price at `0.20`, and select **Apply controls**.
6. Check that usage is `5,132.22` kWh and estimated cost is `1,026.44`.

The zone selection changes which readings enter the analysis. The price changes only the cost calculation. A price change does not predict a change in consumption.

## 4. Reset for another demonstration

1. Open **Filters and scenarios**.
2. Set **Zone** to **All** and **Price per kWh** to `0.15`.
3. Select **Apply controls**. Check the starting values again.

## Demonstrate it in two minutes

1. Show the pipeline and say: “The report has a saved data rule and a saved cost formula.”
2. Show all-zone usage and cost at `0.15`.
3. Change the price to `0.20`. Say: “We can compare a price assumption against the same readings.”
4. Select `Zone-A`. Show that the same report works for one zone.

**Done when:** You can explain why price affects cost, why the zone filter affects usage, and why this exercise needs no model call.

Next: [Build a small sales report](02-sales-report.md).
