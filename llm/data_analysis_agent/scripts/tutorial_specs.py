"""The exact learner prompts and independent numerical checks for each lesson."""

from typing import Any
import numpy as np
import pandas as pd

COMMON = """Build a desktop dashboard with separate Data cleaning and Analysis stages and the requested Visualization widgets. Give widgets the exact titles listed below so I can check them. Use readable English labels and correct units. Keep the original CSV unchanged. Preserve repeated observations unless I explicitly ask otherwise. Use standard column bindings for ordinary bar, pie, line and scatter charts so I can edit their bindings in Properties. For advanced charts return JSON-only ECharts options from the analysis. Use no external chart resources or JavaScript callbacks. Declare parameters_used for each step. Add a full table export where requested; do not truncate the underlying table. Save the stages; I will select Run."""

LESSONS = [
    {"key": "penguins", "number": "01", "title": "Explore and compare", "subject": "Palmer Penguins", "file": "penguins.csv", "accent": "#245bd7",
     "question": "How do species differ, and how do flipper length and body mass relate?",
     "skills": ["Cleaning missing values", "Grouped averages", "Bar and pie charts", "Scatter plots", "Card properties"],
     "context": "Each row is one historical penguin observation. Species and island are categories. Bill and flipper measurements are in millimetres; body mass is in grams. Missing sex is not a reason to remove an otherwise valid measurement. Year is an observation label, not an equally spaced time series. Do not infer causes from correlations.",
     "prompts": [COMMON + """
Use every source column. In cleanup, remove only rows missing any of bill_length_mm, bill_depth_mm, flipper_length_mm or body_mass_g; replace missing sex with 'Unknown'. Do not remove duplicate-looking observations.
Add a species select filter on the cleaned data, default All (null).
Create metrics 'Records used' (row count) and 'Mean body mass' (mean body_mass_g, grams, two decimals).
Create 'Species counts' as a bar chart of counts by species, 'Species share' as a pie chart of those same counts, and 'Mass and flipper length' as a scatter plot with flipper_length_mm on X and body_mass_g on Y, one point per cleaned observation.
Create the full table 'Species summary' with species, count, mean_body_mass_g and mean_flipper_length_mm. Charts and tables must use the current filtered data. Keep all three standard charts editable through column bindings.
""", """Add one computed text widget titled 'Reading the scatter'. Calculate Pearson correlation between flipper_length_mm and body_mass_g from the current filtered cleaned data. Include the observation count and correlation rounded to three decimals, and explain that association does not establish cause. If fewer than two observations or a constant column prevents correlation, say that it is unavailable. Preserve all existing stages, widget titles, bindings, and controls. I will select Run."""],
     "filter": {"species": "Adelie"}, "filter_label": "Adelie only", "practice_label": "Gentoo observations only",
     "charts": ["Species counts", "Species share", "Mass and flipper length"],
     "caveats": ["Rows with missing measurements are excluded from this complete-case comparison. Counts describe this sample, not the Antarctic population.", "Species counts and Species share use the same denominator. Changing a chart does not change its calculation.", "Unknown sex is retained. Similar measurements are not proof of duplicate birds."],
     "exercises": ["Select Species counts. In Properties → Chart binding, change bar to pie. Compare it with Species share, then select Undo.", "Select Mass and flipper length. Swap its numeric X and Y bindings, inspect the axes, then Undo.", "Change the metric format and unit display in Properties. Formatting does not convert grams to kilograms.", "Select the added Reading the scatter card in Pipeline, review Delete stage, delete it, then Undo. The original CSV is unchanged."],
    },
    {"key": "retail", "number": "02", "title": "Build a sales dashboard", "subject": "Online Retail · Q1 2011", "file": "retail_q1_2011.csv", "accent": "#097e70",
     "question": "Where does invoice sales value come from, and what changes under a discount scenario?",
     "skills": ["Metric definitions", "Ranked comparisons", "Daily trends", "Stacked bars", "What-if controls"],
     "context": "This is a historical UK retailer extract for January–March 2011. UnitPrice is GBP per unit. A C prefix in InvoiceNo marks cancellation. Positive invoice-line sales value is Quantity × UnitPrice on non-cancelled lines with Quantity > 0 and UnitPrice > 0. This is not profit or refund-adjusted net revenue. Missing CustomerID must not remove valid sales. Keep potential duplicate lines because the source has no invoice-line identifier.",
     "prompts": [COMMON + """
Read InvoiceNo, StockCode and CustomerID as nullable text and InvoiceDate as datetime. Cleanup must keep all source rows, normalize dates, fill missing Description and CustomerID with 'Unknown', and add is_valid_sale for non-cancelled InvoiceNo (case-insensitive C prefix), Quantity > 0 and UnitPrice > 0. Do not deduplicate.
Add a Country select filter on cleaned data with All (null), and a numeric discount_pct scenario default 0, minimum 0, maximum 30. Discount only scales sales value; it does not predict a change in quantity. Put the Country control in the root parameters array: {"id":"country","label":"Country","kind":"select","default":null,"minimum":null,"maximum":null,"choices":[],"filter_column":"Country","filter_artifact":"cleaned","filter_operator":"eq"}. It is not a visualization widget.
Analysis uses only valid sale rows for sales metrics and charts, while 'Excluded lines' counts invalid lines in the currently filtered data. Metrics: 'Sales value' (sum Quantity × UnitPrice, GBP, two decimals), 'Invoice lines' (valid line count), 'Invoices' (distinct valid InvoiceNo count), 'Excluded lines', 'Scenario sales value' (Sales value × (1 - discount_pct/100)).
Charts: 'Sales by country' (top ten countries ranked by sales value, bar), 'Daily sales' (sum by observed calendar date, line), and 'Top invoice items' (top ten Description values ranked by sales value, horizontal bar). Labels must not claim that all item codes represent physical products.
Create full table 'Invoice detail' with every valid invoice line, original columns and sales_value. Never use head() for its exported result. Do not add a pie chart with dozens of countries.
Keep the graph small: one cleanup step returns cleaned; one analysis step takes cleaned and returns all nine named outputs: sales_value, invoice_lines, invoices, excluded_lines, scenario_sales_value, country_totals, daily_sales, top_items, invoice_detail. Declare these exact names in that analysis step's outputs list and return each of them from its function. First assign valid_sales=valid_sales.assign(sales_value=valid_sales.Quantity*valid_sales.UnitPrice). Compute country_totals=valid_sales.groupby('Country',as_index=False)['sales_value'].sum().nlargest(10,'sales_value'); compute daily_sales=valid_sales.assign(date=valid_sales.InvoiceDate.dt.strftime('%Y-%m-%d')).groupby('date',as_index=False)['sales_value'].sum(). Never aggregate Quantity and label it sales value. country_totals is a DataFrame with Country and sales_value, daily_sales a DataFrame with date and sales_value; bind the country bar and daily line directly to those DataFrames. Build item_totals=valid_sales.assign(sales_value=valid_sales.Quantity*valid_sales.UnitPrice).groupby('Description',as_index=False)['sales_value'].sum().nlargest(10,'sales_value'); top_items={'option':{'xAxis':{'type':'value','name':'GBP'},'yAxis':{'type':'category','data':item_totals.Description.tolist()},'series':[{'type':'bar','data':item_totals.sales_value.tolist()}]}}. Its widget chart_binding must be null. invoice_detail is the full valid-line DataFrame. Metric widgets bind the five separate scalar outputs, not a metrics dictionary. Do not create chart widgets that refer to undeclared or differently named outputs.
""", """Add one chart titled 'Monthly country mix'. Use the current valid sale lines to sum sales_value by calendar month and Country. First set valid_sales=inputs['cleaned'].loc[inputs['cleaned']['is_valid_sale']].copy(); this exclusion is essential. Add valid_sales['sales_value']=valid_sales.Quantity*valid_sales.UnitPrice and valid_sales['month']=valid_sales.InvoiceDate.dt.strftime('%Y-%m'). All grouping below uses valid_sales, never the unfiltered cleaned artifact. Show stacked bars for the five countries with the largest total sales value in the current selection, plus an Other series for the remaining countries. Group by the explicit month and country columns, pivot to countries, then reindex its row index to ['2011-01', '2011-02', '2011-03'] with zero for missing cells. Read chart X labels directly from that index; do not reset an unnamed index and assume it is named Month. Return a JSON chart dictionary, never a pivot DataFrame: pivot=valid_sales.pivot_table(index='month',columns='Country',values='sales_value',aggfunc='sum',fill_value=0).reindex(['2011-01','2011-02','2011-03'],fill_value=0); top=pivot.sum().nlargest(5).index.tolist(); series=[{'name':str(c),'type':'bar','stack':'sales','data':pivot[c].tolist()} for c in top]; remaining=[c for c in pivot.columns if c not in top]; series.append({'name':'Other','type':'bar','stack':'sales','data':pivot[remaining].sum(axis=1).tolist()}); monthly_country_mix={'option':{'legend':{},'xAxis':{'type':'category','data':pivot.index.tolist()},'yAxis':{'type':'value','name':'GBP'},'series':series}}. Declare monthly_country_mix as this step's only output and return {'monthly_country_mix':monthly_country_mix}; point the widget output at monthly_country_mix. Use chart_binding=null on this new widget. Include a legend and GBP axis. The sum of all stack values must equal Sales value. Preserve the existing metrics, charts, full detail table, Country filter and discount scenario. I will select Run."""],
     "filter": {"country": "Germany"}, "filter_column": "Country", "filter_label": "Germany only", "practice_label": "March 2011 invoice lines only",
     "scenario": {"discount_pct": 10}, "scenario_label": "10% discount, unchanged quantities",
     "charts": ["Sales by country", "Daily sales", "Top invoice items", "Monthly country mix"],
     "caveats": ["The supplied CSV includes every source row in the quarter; it is not a random sample. The workbook-to-CSV conversion is recorded in the manifest.", "Excluded cancellations and non-positive lines are reported, not silently treated as completed sales. Missing customers remain in the totals.", "The discount result is arithmetic under fixed quantities. It is not a demand forecast, profit estimate, or current market claim."],
     "exercises": ["Select Daily sales and switch its standard binding from line to bar, then Undo.", "In the target, change discount_pct to 10 and select Apply controls. Sales value stays the same; Scenario sales value becomes 90% of it.", "Edit a dashboard title in Dashboard settings and watch the target update without Run. Change a calculation default, observe Changes pending, then select Run.", "Download Invoice detail CSV. Compare its complete row count with Invoice lines; the on-screen preview may show fewer rows."],
    },
    {"key": "wine", "number": "03", "title": "Inspect distributions and relationships", "subject": "Wine Quality", "file": "wine_quality.csv", "accent": "#8250a3",
     "question": "How do distributions differ, and which measurements move together?",
     "skills": ["Histograms", "Box plots", "Spearman correlation", "Heatmaps", "Threshold controls"],
     "context": "Each row is a measured red or white Vinho Verde wine sample from the UCI source. wine_type identifies the source file. Quality is an ordered sensory score from 0 to 10, not a percentage. Alcohol is percent by volume. Repeated measurements may be distinct samples: preserve all rows. Comparisons and correlations are descriptive; they do not establish cause or support health claims.",
     "prompts": [COMMON + """
Cleanup must preserve every row and every source measurement, including repeated rows. Add a wine_type select filter on cleaned data with All (null), and quality_threshold integer default 7, minimum 0, maximum 10. The threshold is a scenario parameter, not a row-removing filter.
Metrics: 'Samples' (row count), 'Mean quality' (mean quality, three decimals), 'At or above threshold' (count quality >= quality_threshold).
Create 'Alcohol distribution' as a histogram using fixed edges 8.0, 8.5, ..., 15.0 percent alcohol. Bins are left-inclusive/right-exclusive except the last includes its right edge. Show count on Y and alcohol ranges on X.
Create 'Alcohol by wine type' as a native ECharts boxplot of alcohol grouped by wine_type. Use minimum, 25th percentile, median, 75th percentile and maximum, with linear quantile interpolation. Label that the whiskers are min/max, not Tukey outliers. Do not silently drop rows.
Create full table 'Quality summary' with wine_type, sample_count, mean_quality, median_alcohol and count_at_threshold for the current selection.
Use exactly one cleanup stage returning cleaned and one initial analysis stage returning these six separately declared outputs: samples (scalar count), mean_quality (scalar), threshold_count (scalar), alcohol_distribution (DataFrame with bin_label and count columns), alcohol_by_type (dictionary with an option key containing native ECharts boxplot options), quality_summary (DataFrame). Bind the three metric widgets to the three separate scalar outputs; never bind a metric to a dictionary of metrics. Use numpy.histogram with bins=np.arange(8.0,15.5,0.5) for the stated bin semantics. The boxplot widget must have chart_binding=null, and its ECharts series data must contain one five-number array per wine type, not a pandas describe table. Keep all table column names unique strings.
For the boxplot use this exact structure with computed data: groups=sorted(df['wine_type'].unique().tolist()); five_numbers=[np.quantile(df.loc[df['wine_type']==group,'alcohol'],[0,.25,.5,.75,1]).tolist() for group in groups]; alcohol_by_type={'option':{'xAxis':{'type':'category','data':groups},'yAxis':{'type':'value','name':'Alcohol (% ABV)'},'series':[{'type':'boxplot','data':five_numbers}]}}. Do not return describe().to_dict(), which is a statistics dictionary rather than an ECharts chart.
""", """Add a native ECharts heatmap titled 'Measurement correlations' using the current filtered samples. Use Spearman correlations, with rows and columns in this order: alcohol, density, residual sugar, volatile acidity, sulphates, quality. Show a diverging colour scale fixed from -1 to +1 with zero in the centre. Include all 36 cells and label the axes. Compute labels=['alcohol','density','residual sugar','volatile acidity','sulphates','quality']; matrix=df[labels].corr(method='spearman'); cells=[[x,y,float(matrix.iloc[y,x])] for y in range(6) for x in range(6)]. Return {'option':{'xAxis':{'type':'category','data':labels},'yAxis':{'type':'category','data':labels},'visualMap':{'min':-1,'max':1,'inRange':{'color':['#245bd7','#ffffff','#bd3945']}},'series':[{'type':'heatmap','data':cells}]}} as the chart artifact and set chart_binding=null. Do not flatten the matrix to bare numbers: each cell needs its x index, y index and value. Python booleans are True/False. Add computed text 'Correlation notes' explaining that quality is ordinal, that Spearman measures ranked association, and that correlation does not establish cause. Preserve all existing calculations and controls. I will select Run."""],
     "filter": {"wine_type": "red"}, "filter_label": "Red wine only", "practice_label": "Red-wine source observations only",
     "scenario": {"quality_threshold": 6}, "scenario_label": "Quality threshold lowered to 6",
     "charts": ["Alcohol distribution", "Alcohol by wine type", "Measurement correlations"],
     "caveats": ["Fixed histogram bins support comparison. All bundled observations fall within the displayed range; check ranges when using a different CSV.", "Box-plot whiskers here show the observed minimum and maximum. They do not identify Tukey outliers.", "The quality scale is ordered and unbalanced. A correlation is not a causal effect or a complete prediction model."],
     "exercises": ["Select the analysis card that uses quality_threshold. Properties should show only controls declared by that stage, not every dashboard field.", "Change quality_threshold to 6 in the target and Apply. Samples and Mean quality remain unchanged; the threshold count increases or stays equal.", "Select a heatmap or box-plot card. These advanced options are produced by analysis; their structure is changed through chat rather than the standard binding dropdown.", "Read the chart tooltip, compare red and white using the filter, then Reset and Apply to return to the reference defaults."],
    },
    {"key": "bike", "number": "04", "title": "Understand trends and forecasts", "subject": "Bike Sharing · daily observations", "file": "bike_daily.csv", "accent": "#c77818",
     "question": "How does demand change over time, and how uncertain is a short forecast?",
     "skills": ["Rolling averages", "Stacked area charts", "Calendar heatmaps", "Chronological backtests", "Forecast intervals"],
     "context": "This is UCI Bike Sharing day.csv: one row per date in 2011–2012. cnt equals casual + registered. Weather variables such as temp and windspeed are normalized values, not degrees Celsius or raw speed. Keep all daily observations. The forecast requires an ordered, unique, equally spaced daily series. Year filtering is contiguous; do not filter weekdays out of the forecasting input.",
     "prompts": [COMMON + """
Read dteday as datetime. Cleanup preserves all observations, sorts by dteday, and adds calendar_year from the date. Add a calendar_year select filter on cleaned data (All/null, 2011, 2012). Preserve all dates in a selected year. Add this control to the root parameters list, not the widgets list: {"id":"calendar_year","label":"Calendar year","kind":"select","default":null,"minimum":null,"maximum":null,"choices":[2011,2012],"filter_column":"calendar_year","filter_artifact":"cleaned","filter_operator":"eq"}. Controls are ParameterSpec objects, not visualization widgets.
Metrics: 'Days' (number of days), 'Total rentals' (sum cnt), 'Average daily rentals' (mean cnt, two decimals).
Create 'Daily demand' with two line series: cnt and a trailing 7-day rolling mean with min_periods=1, dates in ascending order.
Create 'Rider mix' as a stacked area chart of casual and registered rentals for each date. The two series must sum to cnt. Both native line series need stack='riders' and areaStyle={} so this is a stacked area chart rather than two ordinary lines.
Create 'Calendar pattern' as an ECharts heatmap with month (1–12) on X and weekday (Sunday 0 through Saturday 6) on Y. Each cell is MEAN daily cnt for that month/weekday, not a total. Use null or omit a cell if no observations exist.
Create the full table 'Daily detail' containing dteday, cnt, casual, registered and rolling_mean_7.
Keep the initial graph to one cleanup stage returning cleaned and one analysis stage returning these seven separately declared outputs: days (scalar), total_rentals (scalar), average_daily_rentals (scalar), daily_demand (DataFrame), rider_mix (dictionary with an option key), calendar_pattern (dictionary with an option key), daily_detail (DataFrame). Compute rolling_mean_7 on a copy using assign, never concatenate another column named cnt. daily_demand must have unique string columns dteday, cnt, rolling_mean_7 and a standard line chart binding with both numeric Y columns. The area and heatmap widgets use chart_binding=null and complete native ECharts options inside an option key. Return the heatmap as axis labels and [month_index,weekday_index,mean] triples, not a pivot DataFrame with integer column names. Set xAxis.data=list(range(1,13)), yAxis.data=list(range(7)); its cell coordinates MUST be zero-based: cells=[[int(month)-1,int(day),float(value)] for (month,day),value in df.groupby(['mnth','weekday'])['cnt'].mean().items()]. Do not put month 1..12 directly into zero-based category coordinates. Add visualMap={'min':0,'max':float(df.cnt.max()),'inRange':{'color':['#eff6ff','#245bd7']}} and series=[{'type':'heatmap','data':cells}]. Return every declared output and make each widget output match its artifact name exactly.
""", """Add a forecasting analysis stage using pipeline_core.statistics.forecast on the current filtered cnt Series indexed by dteday, sorted by date. Use method='arima' (the helper uses ARIMA(1,1,0)), and add horizon integer default 14, minimum 1, maximum 30. Add horizon to the root parameters list with id=horizon, label='Forecast days', kind=integer, default=14, minimum=1, maximum=30, choices=[], filter_column=null, filter_artifact=cleaned, filter_operator=eq. Declare horizon in the forecast step parameters_used. Do not change the helper, use a random split, or fit on future rows. In your patch use numeric JSON Pointer array indices, or /steps/- and /dashboard/widgets/- to append. Stage IDs such as forecast_analysis are not valid array path indices. Add the forecast step only once; on repair replace its existing code at its numeric index rather than appending duplicate IDs. The helper returns keys forecast, prediction_intervals_95 (list of [lower,upper] pairs), backtest_mae, baseline_mae, training_observations, holdout_observations, method, assumptions and uncertainty. It does not return dates: create them with pd.date_range(df.dteday.max()+pd.Timedelta(days=1),periods=horizon,freq='D').strftime('%Y-%m-%d').tolist(). Set chart_binding=null for the forecast option dictionary.
Add metrics 'Holdout MAE' and 'Baseline MAE' from the helper, both two decimals. Add computed text 'Forecast checks' with training and holdout observation counts, method, assumptions, uncertainty, and whether the model beats the naive baseline. Do not promise an improvement.
Add 'Demand forecast' showing the last 60 observed days, the future daily point forecasts starting the next day, and the helper's 95% model intervals. Use JSON-only ECharts line series. For the interval fill use an invisible lower-bound series and an upper-minus-lower area series stacked together with stackStrategy='all' so negative lower bounds are handled correctly. Do not clip negative bounds or forecasts silently. Keep actuals and predictions visibly distinct. Preserve all existing charts, table and calendar_year filter. I will select Run."""],
     "filter": {"calendar_year": 2012}, "filter_label": "2012 only", "practice_label": "Daily observations for 2012 only",
     "scenario": {"horizon": 7}, "scenario_label": "Seven future days",
     "charts": ["Daily demand", "Rider mix", "Calendar pattern", "Demand forecast"],
     "caveats": ["No observations after 2012 are included. The forecast is a worked historical exercise, not a current demand estimate.", "Temperature and wind fields are normalized. The guide does not convert them using unverified daily-scale constants.", "Intervals are conditional ARIMA model intervals. They do not include all real-world uncertainty. A model may perform worse than its naive baseline."],
     "exercises": ["Change horizon to 7 in the target, then Apply. The number of future points and the holdout size should change; historical totals remain unchanged.", "Upload the labelled 2012 replacement CSV in the target. The builder must keep the original two-year CSV. Then select Use builder data.", "Upload the invalid-schema practice CSV. Check the missing-column error and confirm that the last successful results remain visible.", "Review cleanup, Run defaults, select Accept revision and inspect History. Download requires the compatible Windows runtime archive; without it, verify the explicit export error rather than treating it as a successful application download.", "Open a second tutorial project and compare dashboard URLs. If a run is still active, try Cancel; short runs may finish before you can select it."],
    },
]


# Keep advanced chart construction explicit; the model still creates the saved stages,
# contracts and widgets from these published, data-driven instructions.
LESSONS[3]['prompts'][1] += """
Use one new stage with id=forecast_analysis, inputs=['cleaned'], outputs=['holdout_mae','baseline_mae','forecast_checks','demand_forecast'], parameters_used=['horizon','calendar_year']. Preserve all earlier steps. Use this function body, including the explicit helper import; pd and np are available but pipeline_core and statsmodels module names are not preloaded:

def function(inputs, parameters, context):
    from pipeline_core.statistics import forecast as run_forecast
    df = inputs['cleaned'].sort_values('dteday').copy()
    horizon = int(parameters['horizon'])
    result = run_forecast(df.set_index('dteday')['cnt'], horizon=horizon, method='arima')
    history = df.tail(60)
    future = pd.date_range(df.dteday.max()+pd.Timedelta(days=1), periods=horizon, freq='D').strftime('%Y-%m-%d').tolist()
    dates = history.dteday.dt.strftime('%Y-%m-%d').tolist()+future
    blank_history = [None]*len(history)
    intervals = result['prediction_intervals_95']
    lower = [pair[0] for pair in intervals]
    width = [pair[1]-pair[0] for pair in intervals]
    chart = {'option':{'legend':{},'xAxis':{'type':'category','data':dates},'yAxis':{'type':'value','name':'Rentals'},'series':[
      {'name':'Observed','type':'line','data':history.cnt.tolist()+[None]*horizon},
      {'name':'Forecast','type':'line','data':blank_history+result['forecast']},
      {'name':'Lower bound','type':'line','stack':'interval','stackStrategy':'all','data':blank_history+lower,'lineStyle':{'opacity':0},'symbol':'none'},
      {'name':'95% interval','type':'line','stack':'interval','stackStrategy':'all','data':blank_history+width,'lineStyle':{'opacity':0},'areaStyle':{'opacity':.2},'symbol':'none'}]}}
    note = f"Training observations: {result['training_observations']}; holdout observations: {result['holdout_observations']}; method: {result['method']}. {result['assumptions']} {result['uncertainty']} Model beats naive baseline: {result['backtest_mae'] < result['baseline_mae']}. This is a historical exercise, not a promise."
    return {'holdout_mae':result['backtest_mae'],'baseline_mae':result['baseline_mae'],'forecast_checks':note,'demand_forecast':chart}

Bind the four new widgets to these exact output names. Forecast and baseline metric formats must be .2f. The forecast widget has chart_binding=null. Do not add a second step with the same id during repair; edit its existing numeric array index.
"""


def expected(key: str, source: pd.DataFrame, parameters: dict[str, Any] | None = None) -> dict[str, float | int]:
    p = parameters or {}
    df = source.copy()
    if key == "penguins":
        df = df.dropna(subset=["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"])
        if p.get("species") is not None: df = df.loc[df.species == p["species"]]
        return {"Records used": len(df), "Mean body mass": float(df.body_mass_g.mean())}
    if key == "retail":
        if p.get("country") is not None: df = df.loc[df.Country == p["country"]]
        valid = ~df.InvoiceNo.astype(str).str.upper().str.startswith("C") & df.Quantity.gt(0) & df.UnitPrice.gt(0)
        sales = df.loc[valid]
        value = float(np.dot(sales.Quantity.to_numpy(), sales.UnitPrice.to_numpy()))
        return {"Sales value": value, "Invoice lines": len(sales), "Invoices": sales.InvoiceNo.nunique(),
                "Excluded lines": int((~valid).sum()), "Scenario sales value": value * (1 - p.get("discount_pct", 0) / 100)}
    if key == "wine":
        if p.get("wine_type") is not None: df = df.loc[df.wine_type == p["wine_type"]]
        return {"Samples": len(df), "Mean quality": float(df.quality.mean()), "At or above threshold": int(df.quality.ge(p.get("quality_threshold", 7)).sum())}
    if p.get("calendar_year") is not None: df = df.loc[pd.to_datetime(df.dteday).dt.year == p["calendar_year"]]
    return {"Days": len(df), "Total rentals": int(df.cnt.sum()), "Average daily rentals": float(df.cnt.mean())}


def checks(key: str, frame: pd.DataFrame) -> list[tuple[str, Any]]:
    """Additional data checks independent of generated application source."""
    if key == "penguins":
        from scipy.stats import pearsonr
        clean = frame.dropna(subset=["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"])
        return [("Complete measurement rows", len(clean)), ("Missing measurement rows", len(frame) - len(clean)),
                ("Pearson r: flipper length / body mass", round(float(pearsonr(clean.flipper_length_mm, clean.body_mass_g).statistic), 6))]
    if key == "retail":
        valid = ~frame.InvoiceNo.astype(str).str.upper().str.startswith("C") & frame.Quantity.gt(0) & frame.UnitPrice.gt(0)
        return [("Valid sale rows with missing customer ID", int(frame.loc[valid].CustomerID.isna().sum())),
                ("Repeated-looking source rows retained", int(frame.duplicated().sum()))]
    if key == "wine":
        from scipy.stats import spearmanr
        counts, edges = np.histogram(frame.alcohol, bins=np.arange(8, 15.5, .5))
        return [("Red source samples", int(frame.wine_type.eq("red").sum())), ("White source samples", int(frame.wine_type.eq("white").sum())),
                ("Histogram count total", int(counts.sum())), ("Spearman rho: alcohol / quality", round(float(spearmanr(frame.alcohol, frame.quality).statistic), 6))]
    return [("First date", str(frame.dteday.min())), ("Last date", str(frame.dteday.max())),
            ("Rows where casual + registered differs from cnt", int((frame.casual + frame.registered != frame.cnt).sum()))]
