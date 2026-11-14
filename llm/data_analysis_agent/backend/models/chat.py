"""Chat interaction, code execution, and visualization specification models."""

from datetime import datetime, timezone
import re
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


class ConfidenceBadge(BaseModel):
    """Plain-English confidence or risk badge representing underlying statistical health."""

    level: Literal["high", "moderate", "warning", "uncharted", "low"] = Field(
        ...,
        description="Semantic confidence tier: high (green), moderate/warning (yellow), uncharted/low (red)",
    )
    icon: Literal["🟢", "🟡", "🔴"] = Field(
        ...,
        description="Visual traffic-light status emoji (🟢 = trustworthy, 🟡 = caution/low sample, 🔴 = uncharted/risk)",
    )
    title: str = Field(
        ...,
        description="Human-readable confidence headline (e.g. 'High Confidence Finding', 'Low Sample Warning')",
    )
    subtitle: str = Field(
        default="",
        description="Contextual plain-English explanation or caveat without raw formulas",
    )
    metric_source: str = Field(
        default="general",
        description="Statistical test or metric source (e.g. 'p_value', 'r_squared', 'mahalanobis', 'sample_size')",
    )
    raw_value: float = Field(
        default=0.0,
        description="Raw numerical value of the underlying statistic for auditing/debugging",
    )
    badge: Optional[str] = Field(
        default=None,
        description="Combined badge string for fast display (e.g. '🟢 High Confidence Finding')",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize level aliases
            if data.get("level") == "uncharted_territory":
                data["level"] = "uncharted"

            # Auto-populate icon and title if only combined badge string was passed
            if "badge" in data and data["badge"]:
                b_str = str(data["badge"])
                if "icon" not in data or not data["icon"]:
                    for ic in ["🟢", "🟡", "🔴"]:
                        if ic in b_str:
                            data["icon"] = ic
                            break
                    if "icon" not in data or not data["icon"]:
                        data["icon"] = "🟢" if data.get("level") == "high" else ("🔴" if data.get("level") in ["uncharted", "low"] else "🟡")
                if "title" not in data or not data["title"]:
                    clean_title = re.sub(r"[🟢🟡🔴]", "", b_str).strip()
                    data["title"] = clean_title or "Statistical Confidence"
            elif "icon" in data and "title" in data and ("badge" not in data or not data["badge"]):
                data["badge"] = f"{data['icon']} {data['title']}"

            # Fallback icon if missing
            if "icon" not in data or not data["icon"]:
                data["icon"] = "🟢" if data.get("level") == "high" else ("🔴" if data.get("level") in ["uncharted", "low"] else "🟡")

            # Fallback raw_value if None
            if "raw_value" in data and data["raw_value"] is None:
                data["raw_value"] = 0.0
        return data

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class FollowUpChip(BaseModel):
    """Interactive next-step action chip prompting contextual follow-up workflows."""

    id: str = Field(
        ...,
        description="Unique identifier for action routing (e.g. 'drilldown_warehouse', 'simulate_recovery')",
    )
    label: str = Field(
        ...,
        description="User-facing chip button text with emoji icon (e.g. '🔍 Show me which customer group caused this')",
    )
    prompt: str = Field(
        ...,
        description="Pre-formulated chat query submitted when the user clicks the chip",
    )
    action_type: Literal["drilldown", "simulate", "recipes", "compare"] = Field(
        ...,
        description="Action category for UI routing: 'drilldown', 'simulate', 'recipes', 'compare'",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


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
    step_logs: List[str] = Field(default_factory=list, description="Step-by-step diagnostic and execution log entries")
    confidence_badges: List[ConfidenceBadge] = Field(
        default_factory=list,
        description="List of plain-English confidence and data quality badges",
    )
    follow_up_chips: List[FollowUpChip] = Field(
        default_factory=list,
        description="Interactive next-step action chips displayed below the response",
    )
    diagnostic_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured diagnostic metadata from anomaly, waterfall, or domino engines",
    )


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
