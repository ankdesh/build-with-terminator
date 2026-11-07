# Scenario 2: Build a small sales report

**Question:** How much did we sell, which country contributed more, and what would a 10% discount do to the total?

**Useful for:** A sales analyst who prepares the same report each month.

**Time:** About 15–20 minutes. **Model access:** Required to create the report. Start with the [shared setup](README.md#prepare-once).

## 1. Understand the ten input rows

Open [sales_january.csv](data/sales_january.csv). This is synthetic data. All prices use one fictional currency, called CU (currency units). India and UK are category labels; no currency conversion is required.

Use this rule: a valid sale has an invoice number that does not start with `C`, a quantity greater than zero, and a unit price greater than zero. Sales value is `Quantity × UnitPrice` for valid lines only.

| Line type | Count | Treatment |
| --- | ---: | --- |
| Valid sale | 7 | Include in sales value |
| Cancellation (`C1006`) | 1 | Exclude from sales value |
| Zero quantity (`1007`) | 1 | Exclude from sales value |
| Zero price (`1008`) | 1 | Exclude from sales value |

## 2. Create a project

1. Select **New project** in the builder. Rename it `Minimal sales report` using the project name in the top bar.
2. Open **Data input**, select **Upload CSV**, and choose `docs/scenarios/data/sales_january.csv` from this checkout.
3. Check that the profile shows ten rows and five columns.
4. Paste this into **Business context**, then click outside the field to save:

   ```text
   Synthetic invoice-line data. All UnitPrice values use one common currency, CU. Country is a category, not a currency. A C prefix marks a cancelled invoice. A valid sale requires a non-cancelled invoice, Quantity > 0, and UnitPrice > 0. Report positive sales value, not profit or refund-adjusted net revenue. The discount scenario assumes unchanged quantities.
   ```

## 3. Create the report through chat

Set chat context to **Project**. Paste this prompt:

```text
Create a minimal reusable sales dashboard from this CSV.

Read InvoiceNo and Country as text, InvoiceDate as datetime, Quantity as integer, and UnitPrice as number. All five columns are required for replacement files.

Use one Data cleaning stage that returns cleaned. Preserve every row and source column. Add is_valid_sale: InvoiceNo does not start with C (case-insensitive), Quantity > 0, and UnitPrice > 0. Do not deduplicate or fill missing prices with zero.

Add two root parameters: country, a select filter on Country in cleaned, default All/null; and discount_pct, a number with label Discount percent, default 0, minimum 0, maximum 30. Filters are controls, not widgets.

Use one Analysis stage taking cleaned. From the currently filtered rows, calculate valid_sales from is_valid_sale and add sales_value = Quantity * UnitPrice. Return exactly five outputs: sales_value (sum of valid sales), excluded_lines (count of invalid rows in the current country selection), scenario_sales_value (sales_value * (1 - discount_pct / 100)), country_totals (all valid sales grouped by Country, columns Country and sales_value, sorted by value descending), and sales_detail (all valid rows with their source columns and sales_value). Return scalar outputs as separate values. Declare parameters_used on the stages.

Create exactly five widgets: Sales value (metric, CU, two decimals), Excluded lines (metric), Scenario sales value (metric, CU, two decimals), Sales by country (standard bar chart bound to country_totals with Country on X and sales_value on Y), and Sales detail (full table bound to sales_detail). Discount affects only Scenario sales value. Keep the saved table complete.

Keep the original CSV unchanged. Save the stages for review; I will select Run.
```

1. Read the review. Check the sale rule, two controls, and five widgets.
2. Select **Apply**. Select **Run** in the top bar and wait for success.
3. Open **Data cleaning**. Check that all ten rows remain; invalid lines are flagged rather than removed here.
4. Open **Visualization** and check the numbers below.

## 4. Check the result

At **All** countries and a discount of `0`:

| Check | Expected result |
| --- | ---: |
| Sales value | 800.00 CU |
| Excluded lines | 3 |
| Scenario sales value | 800.00 CU |
| India bar | 530.00 CU |
| UK bar | 270.00 CU |
| Sales detail rows | 7 |

You can check the total by hand: `200 + 150 + 120 + 100 + 100 + 80 + 50 = 800`.

## 5. Try a business assumption

1. Select **Open dashboard**. Open **Filters and scenarios**.
2. Keep Country at **All**. Set **Discount percent** to `10` and select **Apply controls**.
3. Check **Scenario sales value** = `720.00` CU. **Sales value** stays at `800.00` CU. The bars and detail table still show original sales.
4. Select Country `India`, keep the discount at `10`, and apply again.
5. Check sales = `530.00`, scenario sales = `477.00`, excluded lines = `1`, and detail rows = `4`.
6. Reset Country to **All** and discount to `0`. Select **Apply controls**.

## Demonstrate it in three minutes

1. Show the ten-row CSV and explain the three excluded lines.
2. Show the saved cleaning rule and the `800.00` result.
3. Apply the `10%` discount. Explain that `720.00` assumes the same quantities.
4. Filter to India. Show that all views use the same country selection.

**Done when:** Your totals match, and you can explain which rows contribute to the result. Keep this project for [scenario 4](04-reuse-and-handoff.md).

Next independent example: [Find a demand trend](03-demand-trend.md).
