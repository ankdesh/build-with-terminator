"""Unit tests for DataProfiler service."""

from pathlib import Path
import pytest
from backend.exceptions import DataProfilingError
from backend.services.data_profiler import DataProfiler


def test_profiler_with_sample_electric_data() -> None:
    profiler = DataProfiler()
    csv_path = Path(__file__).resolve().parent.parent / "sample_data" / "electric_usage.csv"
    desc_path = Path(__file__).resolve().parent.parent / "sample_data" / "electric_usage_desc.txt"

    with open(csv_path, "rb") as f:
        csv_bytes = f.read()

    with open(desc_path, "r", encoding="utf-8") as f:
        desc_text = f.read()

    profile = profiler.profile_csv(
        session_id="test-session-1",
        csv_bytes=csv_bytes,
        dataset_name="electric_usage.csv",
        column_descriptions_text=desc_text,
    )

    assert profile.row_count == 360
    assert profile.column_count == 7
    assert len(profile.columns) == 7

    # Validate column schema and descriptions parsed
    col_dict = {c.name: c for c in profile.columns}
    assert "kwh_consumed" in col_dict
    assert col_dict["kwh_consumed"].mean_value is not None
    assert col_dict["kwh_consumed"].null_count == 0
    assert "kilowatt-hours" in col_dict["kwh_consumed"].column_description

    # Validate preview rows
    assert len(profile.preview_rows) == 5
    assert "timestamp" in profile.preview_rows[0]

    # Validate quality report
    assert profile.quality_report.duplicate_rows_count == 0


def test_profiler_with_empty_data() -> None:
    profiler = DataProfiler()
    with pytest.raises(DataProfilingError):
        profiler.profile_csv(
            session_id="test-session-empty",
            csv_bytes=b"col1,col2\n",
            dataset_name="empty.csv",
        )
