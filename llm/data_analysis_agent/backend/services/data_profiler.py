"""Automated data profiling, descriptive statistics, and data quality analysis."""

import io
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.exceptions import DataProfilingError
from backend.models.profile import ColumnSummary, DataProfile, DataQualityReport, QualityFlag
from config import SAMPLE_DATA_PREVIEW_ROWS

logger = logging.getLogger(__name__)


class DataProfiler:
    """Inspects uploaded CSV files to generate statistics, previews, and quality flags."""

    def __init__(self, sample_preview_rows: int = SAMPLE_DATA_PREVIEW_ROWS) -> None:
        self.sample_preview_rows = sample_preview_rows

    def profile_csv(
        self,
        session_id: str,
        csv_bytes: bytes,
        dataset_name: str,
        column_descriptions_text: str = ""
    ) -> DataProfile:
        """Parse raw CSV bytes, compute column-level metrics, and flag quality issues."""
        try:
            # Attempt parsing with standard UTF-8, then fallback to latin1 if needed
            try:
                df = pd.read_csv(io.BytesIO(csv_bytes))
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(csv_bytes), encoding="latin1")
        except Exception as e:
            raise DataProfilingError(filename=dataset_name, reason=str(e))

        if df.empty:
            raise DataProfilingError(
                filename=dataset_name,
                reason="The uploaded CSV file contains no data rows."
            )

        col_desc_map = self._parse_column_descriptions(column_descriptions_text)

        columns_summary: List[ColumnSummary] = []
        for col_name in df.columns:
            col_series = df[col_name]
            summary = self._summarize_column(
                col_name=str(col_name),
                series=col_series,
                description=col_desc_map.get(str(col_name), "")
            )
            columns_summary.append(summary)

        # Generate sample preview rows (clean NaN/Inf for JSON compliance)
        preview_df = df.head(self.sample_preview_rows).copy()
        preview_rows = self._clean_dict_records(preview_df.to_dict(orient="records"))

        # Run quality inspections
        quality_report = self._inspect_data_quality(df)

        return DataProfile(
            session_id=session_id,
            dataset_name=dataset_name,
            row_count=int(len(df)),
            column_count=int(len(df.columns)),
            columns=columns_summary,
            preview_rows=preview_rows,
            quality_report=quality_report,
        )

    def _summarize_column(self, col_name: str, series: pd.Series, description: str) -> ColumnSummary:
        """Calculate descriptive metrics for a single pandas Series."""
        null_count = int(series.isna().sum())
        total_count = len(series)
        null_pct = round((null_count / total_count) * 100.0, 2) if total_count > 0 else 0.0
        unique_cnt = int(series.nunique(dropna=True))

        # Distinct non-null sample values
        non_null = series.dropna()
        sample_vals = [self._sanitize_value(v) for v in non_null.head(5).tolist()]

        min_val: Optional[Any] = None
        max_val: Optional[Any] = None
        mean_val: Optional[float] = None
        median_val: Optional[float] = None

        if pd.api.types.is_numeric_dtype(series):
            if not non_null.empty:
                min_val = self._sanitize_value(non_null.min())
                max_val = self._sanitize_value(non_null.max())
                mean_val = round(float(non_null.mean()), 3)
                median_val = round(float(non_null.median()), 3)
        elif pd.api.types.is_datetime64_any_dtype(series):
            if not non_null.empty:
                min_val = str(non_null.min())
                max_val = str(non_null.max())

        return ColumnSummary(
            name=col_name,
            data_type=str(series.dtype),
            null_count=null_count,
            null_percentage=null_pct,
            unique_count=unique_cnt,
            sample_values=sample_vals,
            min_value=min_val,
            max_value=max_val,
            mean_value=mean_val,
            median_value=median_val,
            column_description=description,
        )

    def _inspect_data_quality(self, df: pd.DataFrame) -> DataQualityReport:
        """Identify duplicate rows, constant columns, heavy nulls, and format anomalies."""
        flags: List[QualityFlag] = []

        # 1. Duplicate rows
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            flags.append(
                QualityFlag(
                    category="duplicates",
                    severity="warning",
                    column=None,
                    message=f"Dataset contains {dup_count} exact duplicate rows. Analysis may need deduplication."
                )
            )

        # 2. Total missing cells
        total_cells = df.size
        total_missing = int(df.isna().sum().sum())
        missing_pct = round((total_missing / total_cells) * 100.0, 2) if total_cells > 0 else 0.0

        # 3. Column-specific checks
        for col in df.columns:
            series = df[col]
            nulls = int(series.isna().sum())
            null_ratio = nulls / len(df) if len(df) > 0 else 0.0

            if null_ratio == 1.0:
                flags.append(
                    QualityFlag(
                        category="missing_values",
                        severity="critical",
                        column=str(col),
                        message=f"Column '{col}' is completely empty (100% null)."
                    )
                )
            elif null_ratio > 0.4:
                flags.append(
                    QualityFlag(
                        category="missing_values",
                        severity="warning",
                        column=str(col),
                        message=f"Column '{col}' has {round(null_ratio * 100, 1)}% missing values."
                    )
                )

            # Constant column
            if series.nunique(dropna=True) <= 1 and len(df) > 1:
                flags.append(
                    QualityFlag(
                        category="constant_column",
                        severity="info",
                        column=str(col),
                        message=f"Column '{col}' has only one unique value across all rows."
                    )
                )

            # Detect potential numeric columns masked as objects (e.g. '$12.50' or '1,200')
            if series.dtype == "object":
                non_null_samples = series.dropna().astype(str).head(20)
                if not non_null_samples.empty:
                    numeric_like = non_null_samples.str.replace(r"[\$,€£% ]", "", regex=True)
                    numeric_like = numeric_like.str.replace(",", "", regex=False)
                    all_numeric = pd.to_numeric(numeric_like, errors="coerce").notna().all()
                    if all_numeric:
                        flags.append(
                            QualityFlag(
                                category="type_anomaly",
                                severity="info",
                                column=str(col),
                                message=f"Column '{col}' is stored as text but appears to contain numeric values or currency symbols."
                            )
                        )

        # 4. Outlier detection on numeric columns
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) > 10:
                std = series.std()
                if std > 0:
                    mean = series.mean()
                    z_scores = np.abs((series - mean) / std)
                    outliers_count = int((z_scores > 3.5).sum())
                    if outliers_count > 0:
                        flags.append(
                            QualityFlag(
                                category="outliers",
                                severity="info",
                                column=str(col),
                                message=f"Column '{col}' contains {outliers_count} potential extreme outliers (> 3.5 standard deviations)."
                            )
                        )

        return DataQualityReport(
            duplicate_rows_count=dup_count,
            total_missing_cells=total_missing,
            missing_cells_percentage=missing_pct,
            flags=flags,
        )

    def _parse_column_descriptions(self, text: str) -> Dict[str, str]:
        """Parse user-provided description file into a mapping of {column_name: description}."""
        col_desc: Dict[str, str] = {}
        if not text:
            return col_desc

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check for delimiters: ':' or '-' or '='
            for delim in [":", " - ", "\t", "="]:
                if delim in line:
                    parts = line.split(delim, 1)
                    key = parts[0].strip().strip("`*\"'")
                    val = parts[1].strip()
                    if key:
                        col_desc[key] = val
                    break
        return col_desc

    def _clean_dict_records(self, records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
        """Clean records for JSON serialization by replacing NaN and Inf with None."""
        cleaned: List[Dict[str, Any]] = []
        for row in records:
            clean_row: Dict[str, Any] = {}
            for k, v in row.items():
                clean_row[str(k)] = self._sanitize_value(v)
            cleaned.append(clean_row)
        return cleaned

    def _sanitize_value(self, val: Any) -> Any:
        """Sanitize individual value for JSON serialization."""
        if val is None or pd.isna(val):
            return None
        if isinstance(val, (np.integer, int)):
            return int(val)
        if isinstance(val, (np.floating, float)):
            if np.isneginf(val) or np.isposinf(val) or np.isnan(val):
                return None
            return round(float(val), 4)
        if isinstance(val, (pd.Timestamp, np.datetime64)):
            return str(val)
        return str(val)
