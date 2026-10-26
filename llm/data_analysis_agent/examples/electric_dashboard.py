"""A reference project for reproducibility tests and the Windows release smoke test."""

from pipeline_core.models import ProjectRevision


def revision() -> ProjectRevision:
    return ProjectRevision.model_validate({
        "title": "Energy usage dashboard", "summary": "Clean duplicates and missing readings; compare zones and forecast hourly usage.",
        "input_contract": {"columns": [
            {"name": "timestamp", "dtype": "datetime"},
            {"name": "zone", "dtype": "string"},
            {"name": "kwh", "dtype": "number"},
        ]},
        "parameters": [
            {"id": "zone", "label": "Zone", "kind": "select", "filter_column": "zone", "default": None},
            {"id": "price", "label": "Price per kWh", "kind": "number", "default": 0.15, "minimum": 0, "maximum": 100},
            {"id": "horizon", "label": "Forecast hours", "kind": "integer", "default": 4, "minimum": 1, "maximum": 24},
        ],
        "steps": [
            {"id": "cleanup", "title": "Remove duplicate and missing readings", "stage": "cleanup", "function": "clean",
             "inputs": ["data"], "outputs": ["cleaned"], "changes_meaning": True,
             "rationale": "Discard exact duplicate records and records without kWh; preserve the original file.",
             "code": "def clean(inputs, parameters, context):\n    return {'cleaned': inputs['data'].drop_duplicates().dropna(subset=['kwh']).copy()}\n"},
            {"id": "summary", "title": "Calculate totals and zone comparisons", "stage": "analysis", "function": "summarize",
             "inputs": ["cleaned"], "outputs": ["total", "cost", "zones", "trend", "finding"],
             "code": """def summarize(inputs, parameters, context):
    df = inputs['cleaned']
    zones = df.groupby('zone', observed=True)['kwh'].sum().reset_index()
    total = float(df['kwh'].sum())
    trend = {'option': {'xAxis': {'type': 'category', 'data': zones['zone'].tolist()},
        'yAxis': {'type': 'value', 'name': 'kWh'}, 'series': [{'type': 'bar', 'data': zones['kwh'].tolist()}]}}
    return {'total': total, 'cost': total * parameters['price'], 'zones': zones, 'trend': trend,
        'finding': f'{len(df)} valid readings total {total:.2f} kWh.'}
"""},
            {"id": "forecast", "title": "Forecast hourly usage", "stage": "analysis", "function": "predict",
             "inputs": ["cleaned"], "outputs": ["projection", "forecast_notes"],
             "code": """from pipeline_core.statistics import forecast
def predict(inputs, parameters, context):
    df = inputs['cleaned']
    hourly = df.groupby('timestamp')['kwh'].sum().sort_index()
    if len(hourly) < 10:
        return {'projection': {'option': {'xAxis': {'data': []}, 'yAxis': {}, 'series': []}},
            'forecast_notes': 'Insufficient data: at least ten ordered hourly readings are required.'}
    output = forecast(hourly, parameters['horizon'])
    return {'projection': {'option': {'xAxis': {'type': 'category', 'data': list(range(1, parameters['horizon'] + 1))},
        'yAxis': {'type': 'value', 'name': 'Predicted kWh'}, 'series': [{'type': 'line', 'data': output['forecast']}]}},
        'forecast_notes': f"Holdout MAE {output['backtest_mae']:.3f}; naive baseline MAE {output['baseline_mae']:.3f}. " + output['assumptions'] + ' ' + output['uncertainty']}
"""},
        ],
        "dependencies": ["pandas", "numpy", "scipy", "statsmodels"],
        "dashboard": {"title": "Energy usage", "subtitle": "Zone comparisons, cost scenarios, and hourly forecasts", "widgets": [
            {"id": "total", "kind": "metric", "title": "Total kWh", "output": "total"},
            {"id": "cost", "kind": "metric", "title": "Estimated cost", "output": "cost", "format": ".2f"},
            {"id": "chart", "kind": "chart", "title": "Usage by zone", "output": "trend"},
            {"id": "forecast", "kind": "chart", "title": "Predicted hourly usage", "output": "projection"},
            {"id": "table", "kind": "table", "title": "Zone totals", "output": "zones", "width": 2},
            {"id": "finding", "kind": "text", "title": "Current input", "output": "finding", "width": 2},
            {"id": "validation", "kind": "text", "title": "Forecast validation and assumptions", "output": "forecast_notes", "width": 2},
        ]},
    })
