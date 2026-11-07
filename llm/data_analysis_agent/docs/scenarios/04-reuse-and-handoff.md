# Scenario 4: Reuse and hand over a report

**Question:** Can another user apply the same sales rules to next month's file, and keep a useful result if a file is invalid?

**Useful for:** A team that repeats a report with a new monthly CSV.

**Time:** About 10 minutes for the Linux exercise. **Model access:** Not required. **Prerequisite:** Complete [scenario 2](02-sales-report.md). Windows export is a separate, optional final step.

## 1. Establish the January result

1. Open the `Minimal sales report` project from scenario 2.
2. Confirm that the builder's input is `sales_january.csv`. Keep the builder defaults at Country **All** and Discount percent `0`.
3. Select **Run** if calculations are pending. Check sales = `800.00` CU and excluded lines = `3`.
4. Select **Open dashboard**. Reset its controls to Country **All** and discount `0`, then select **Apply controls** if needed.

## 2. Use February data in the separate dashboard

1. In the dashboard page, select **Upload CSV** and choose [sales_february.csv](data/sales_february.csv), at `docs/scenarios/data/sales_february.csv`.
2. Wait for the saved analysis to finish. Upload runs the calculations with the revision defaults.
3. Check these results:

   | Check | Expected result |
   | --- | ---: |
   | Sales value | 500.00 CU |
   | Excluded lines | 2 |
   | Scenario sales value, discount 0 | 500.00 CU |
   | India bar | 280.00 CU |
   | UK bar | 220.00 CU |
   | Sales detail rows | 4 |

4. Set **Discount percent** to `10` and select **Apply controls**. Check scenario sales = `450.00` CU and original sales = `500.00` CU.
5. Reset discount to `0` and apply.
6. Return to the builder's **Data input** page. Check that its file is still January. Its saved sales result remains `800.00` CU.

You have reused the saved report on a separate input. This did not require a new chat request or a replacement of the development CSV.

## 3. Try an invalid file

1. Return to the dashboard page. Note the current successful result: sales = `500.00` CU.
2. Select **Upload CSV** and choose [sales_missing_price.csv](data/sales_missing_price.csv), at `docs/scenarios/data/sales_missing_price.csv`.
3. Check that an error identifies the missing `UnitPrice` column. Exact error wording can vary.
4. Check that the February dashboard remains visible with sales = `500.00` CU. Do not read this retained result as a successful calculation of the invalid file.
5. Upload `sales_february.csv` again. Wait for success and check `500.00` CU.

The input contract makes the report's data requirements explicit. A failed replacement keeps the last successful result.

## 4. Return to the builder input

1. At the bottom of the live dashboard, expand **Data and revision**.
2. Select **Use builder data**.
3. Wait for the refresh. Check January sales = `800.00` CU, excluded lines = `3`, and scenario sales = `800.00` CU.

This action uses the builder CSV and revision defaults. Reapply temporary control selections if you need them.

## 5. Accept a version

1. In the builder, review the cleaning stage and the successful January results.
2. Select **Accept revision**. If the dialog asks for cleanup confirmation, read the impact summary and select the confirmation checkbox.
3. Confirm **Accept revision**, then open **History**.
4. Check that an accepted revision is listed. Acceptance identifies the saved calculations and accepted input for download. A CSV uploaded only in the separate dashboard is excluded from that accepted input.

You can finish the scenario here. The live dashboard demonstrates reuse while the Linux builder is running.

## 6. Optional: hand over the Windows application

**Prerequisite:** The Linux builder has a compatible, verified Windows runtime ZIP configured through `WPS_WINDOWS_RUNTIME`. Follow the [runtime build and cache instructions](../../README.md#build-and-cache-the-windows-runtime) if it is not available. Without that cache, download reports an error; skip this step until the runtime is ready.

1. In **History**, select **Include the accepted CSV in downloads**.
2. Select **Download Windows app** for the accepted revision. Transfer the ZIP and the small practice CSVs to a Windows 11 x64 workstation.
3. Extract the ZIP. Run `WPSAnalysis.exe` and open the local URL if the browser does not open.
4. Check the initial January result: sales = `800.00` CU. Upload `sales_february.csv` and check `500.00` CU. Apply a `10%` discount and check `450.00` CU.
5. Close the original Linux builder. Confirm that the exported Windows app can still refresh its local report. It uses the saved calculations and needs no model credentials or internet connection.

The Linux live dashboard depends on the builder process. The exported Windows application runs independently. A successful Linux exercise does not verify the Windows package; perform the Windows checks before demonstrating that handoff.

## Demonstrate it in three minutes

1. Start with January sales at `800.00` CU.
2. Upload February and show `500.00` CU using the same rules.
3. Upload the invalid file. Show the missing-column error and the retained February result.
4. Restore builder data and show `800.00` CU.
5. If you verified the Windows package, show the same February report there.

**Done when:** You can repeat the report with a new CSV, explain the retained result after an error, and identify which input belongs to the accepted version.

Return to the [scenario index](README.md).
