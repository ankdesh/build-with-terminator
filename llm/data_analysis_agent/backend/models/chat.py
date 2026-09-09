"""Chat interaction, code execution, and visualization specification models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ChartSpec(BaseModel):
    """Native Apache ECharts visualization specification."""

    title: str = Field(default="Analysis Chart", description="Chart title")
    description: Optional[str] = Field(default=None, description="Short caption explaining the visual takeaway")
    option: Dict[str, Any] = Field(default_factory=dict, description="Native Apache ECharts option tree")

    @model_validator(mode="before")
    @classmethod
    def normalize_spec(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # If already has non-empty option, return as-is
        if "option" in data and isinstance(data["option"], dict) and data["option"]:
            return data

        # Check if it's the legacy schema: data + x_key (or series)
        if "data" in data and isinstance(data["data"], list) and data["data"]:
            records = data.get("data", [])
            chart_type = str(data.get("chart_type", "bar")).lower()
            x_key = str(data.get("x_key", list(records[0].keys())[0] if records else "x"))
            raw_series = data.get("series", [])
            categories = [str(r.get(x_key, "")) for r in records]

            echarts_series = []
            if raw_series and isinstance(raw_series, list):
                for s in raw_series:
                    k = str(s.get("key", "")) if isinstance(s, dict) else str(s)
                    nm = str(s.get("name", k)) if isinstance(s, dict) else str(s)
                    c_key = s.get("color_key") if isinstance(s, dict) else None
                    stype = "line" if chart_type in ["line", "area"] else "bar"
                    sdata = []
                    for r in records:
                        val = r.get(k, 0)
                        col = r.get(c_key) if c_key else r.get("color")
                        if col:
                            sdata.append({
                                "value": val,
                                "itemStyle": {"color": col},
                                "symbolSize": 10,
                                "symbol": "circle",
                            })
                        else:
                            sdata.append(val)
                    echarts_series.append({
                        "name": nm or "Value",
                        "type": stype,
                        "data": sdata,
                        "smooth": True if chart_type in ["line", "area"] else False,
                    })
            else:
                # Default series from first numeric column
                cols = [c for c in records[0].keys() if c != x_key] if records else []
                k = cols[0] if cols else "value"
                echarts_series.append({
                    "name": k,
                    "type": "line" if chart_type in ["line", "area"] else "bar",
                    "data": [r.get(k, 0) for r in records],
                })

            return {
                "title": data.get("title", "Analysis Chart"),
                "description": data.get("description"),
                "option": {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": categories},
                    "yAxis": {"type": "value"},
                    "series": echarts_series,
                },
            }

        # If data itself is an ECharts option (contains series)
        if "series" in data:
            title_val = data.get("title")
            title_str = (
                title_val.get("text", "Analysis Chart")
                if isinstance(title_val, dict)
                else (str(title_val) if title_val else "Analysis Chart")
            )
            return {
                "title": title_str,
                "description": data.get("description"),
                "option": data,
            }

        return data


class TableData(BaseModel):
    """Tabular data representation for inline display, pagination, and CSV export."""

    columns: List[str] = Field(default_factory=list, description="Column names in display order")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Row objects (column_name: cell_value)")
    total_rows: int = Field(default=0, description="Total number of rows in the complete result")


class ExecutionResult(BaseModel):
    """Output generated from running data analysis code against the session DataFrame."""

    success: bool = Field(..., description="True if code executed without errors")
    plan: str = Field(default="", description="Plain-English preliminary plan of steps")
    explanation: str = Field(default="", description="Plain-English explanation of calculations and findings")
    code: str = Field(default="", description="Python code that was executed")
    stdout: str = Field(default="", description="Standard output captured during execution")
    chart: Optional[ChartSpec] = Field(default=None, description="Optional interactive chart specification")
    table: Optional[TableData] = Field(default=None, description="Optional tabular output")
    error_traceback: Optional[str] = Field(default=None, description="Error traceback if execution failed")
    execution_time_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    retries_attempted: int = Field(default=0, description="Count of retry attempts required to succeed")


class ChatMessage(BaseModel):
    """An individual message in a session's conversation history."""

    id: str = Field(..., description="Unique message ID")
    role: Literal["user", "assistant", "system"] = Field(..., description="Sender role")
    content: str = Field(..., description="Main text content / plain-English answer")
    plan: Optional[str] = Field(default=None, description="Preliminary plan if assistant response")
    execution_result: Optional[ExecutionResult] = Field(default=None, description="Execution metadata and visuals")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp"
    )
