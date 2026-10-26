"""Small reference pipelines whose expected results are independently known."""

from pathlib import Path
import pytest
from pipeline_core.models import ProjectRevision


@pytest.fixture
def input_csv(tmp_path: Path) -> Path:
    path = tmp_path / "source.csv"
    path.write_text("zone,value\nA,10\nA,10\nB,20\nC,\n")
    return path


@pytest.fixture
def simple_revision() -> ProjectRevision:
    return ProjectRevision.model_validate({
        "title": "Reference dashboard", "summary": "Clean exact duplicates and missing values, then calculate totals.",
        "input_contract": {"columns": [{"name": "zone", "dtype": "string"}, {"name": "value", "dtype": "number"}]},
        "parameters": [
            {"id": "zone", "label": "Zone", "kind": "select", "default": None, "filter_column": "zone"},
            {"id": "multiplier", "label": "Multiplier", "kind": "number", "default": 1, "minimum": 0, "maximum": 100},
        ],
        "steps": [
            {"id": "cleanup", "title": "Remove duplicates and missing readings", "stage": "cleanup", "function": "clean",
             "inputs": ["data"], "outputs": ["cleaned"], "changes_meaning": True,
             "code": "def clean(inputs, parameters, context):\n    return {'cleaned': inputs['data'].drop_duplicates().dropna(subset=['value']).copy()}\n"},
            {"id": "totals", "title": "Totals", "stage": "analysis", "function": "calculate",
             "inputs": ["cleaned"], "outputs": ["total", "records", "finding"],
             "code": "def calculate(inputs, parameters, context):\n    df = inputs['cleaned']\n    total = float(df['value'].sum()) * parameters['multiplier']\n    return {'total': total, 'records': df, 'finding': f'Total {total:.1f} from {len(df)} rows'}\n"},
        ],
        "dashboard": {"title": "Reference", "widgets": [
            {"id": "total", "kind": "metric", "title": "Total", "output": "total"},
            {"id": "table", "kind": "table", "title": "Records", "output": "records"},
            {"id": "finding", "kind": "text", "title": "Computed finding", "output": "finding"},
        ]},
    })
