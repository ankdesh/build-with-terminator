"""Data profiling and quality inspection models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnSummary(BaseModel):
    """Statistical and structural summary of an individual dataset column."""

    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="Inferred pandas data type (e.g., int64, float64, object, datetime64)")
    null_count: int = Field(default=0, description="Count of missing or null values")
    null_percentage: float = Field(default=0.0, description="Percentage of missing values (0-100)")
    unique_count: int = Field(default=0, description="Count of distinct values")
    sample_values: List[Any] = Field(default_factory=list, description="Sample values from the column")
    min_value: Optional[Any] = Field(default=None, description="Minimum value if numeric or timestamp")
    max_value: Optional[Any] = Field(default=None, description="Maximum value if numeric or timestamp")
    mean_value: Optional[float] = Field(default=None, description="Arithmetic mean if numeric")
    median_value: Optional[float] = Field(default=None, description="Median if numeric")
    column_description: str = Field(default="", description="User-provided description from text file")


class QualityFlag(BaseModel):
    """An explicit finding or assumption identified during automated dataset profiling."""

    category: str = Field(..., description="Category: e.g., 'missing_values', 'duplicates', 'constant_column', 'type_anomaly'")
    severity: str = Field(default="warning", description="Severity level: 'info', 'warning', 'critical'")
    column: Optional[str] = Field(default=None, description="Specific column impacted, or null if dataset-wide")
    message: str = Field(..., description="Plain English description of the issue or assumption made")


class DataQualityReport(BaseModel):
    """Collection of quality flags, data integrity checks, and modeling assumptions."""

    duplicate_rows_count: int = Field(default=0, description="Count of exact duplicate rows in the dataset")
    total_missing_cells: int = Field(default=0, description="Sum of all null entries across all cells")
    missing_cells_percentage: float = Field(default=0.0, description="Overall missing cell percentage")
    flags: List[QualityFlag] = Field(default_factory=list, description="List of specific identified issues/assumptions")


class DataProfile(BaseModel):
    """Primary data profile representation for an uploaded dataset."""

    session_id: str = Field(..., description="Associated session identifier")
    dataset_name: str = Field(..., description="Uploaded CSV filename")
    row_count: int = Field(..., description="Total row count")
    column_count: int = Field(..., description="Total column count")
    columns: List[ColumnSummary] = Field(default_factory=list, description="Column-by-column breakdown")
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list, description="First N preview rows (dict format)")
    quality_report: DataQualityReport = Field(default_factory=lambda: DataQualityReport(), description="Data quality findings and assumptions")
