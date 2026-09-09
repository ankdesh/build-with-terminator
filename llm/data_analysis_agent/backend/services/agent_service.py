"""Agent orchestration service managing LLM prompts, execution, retries, and SSE streaming."""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import pandas as pd
from openai import AsyncOpenAI

from backend.exceptions import CodeExecutionError, LLMConfigurationError, LLMServiceError
from backend.models.chat import ChatMessage, ExecutionResult
from backend.models.profile import DataProfile
from backend.services.code_executor import CodeExecutor
from config import config

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are WPS-AI, an expert data analysis assistant operating in an air-gapped environment.
You analyze tabular data by generating plans, writing clean Python pandas/numpy code, and explaining insights in simple, clear English with minimal math jargon.

The user's dataset is already loaded into variable `df` as a pandas DataFrame.
The columns and their business context are provided in the system context.

You must respond with valid JSON matching this exact structure:
{
  "plan": "Simple English description of the analytical steps you plan to take (e.g., '1. Filter records where temperature > 75. 2. Group by hour and calculate average kilowatt usage. 3. Identify the peak usage period.')",
  "code": "Python code using df, pd, np. Output variables:\\n1. `chart_spec`: (optional) dict with {'title': '...', 'description': '...', 'option': {...}} containing an Apache ECharts option tree when a plot/chart is requested.\\n2. `result`: (optional) pandas DataFrame or Series. IMPORTANT: When creating a chart, do NOT assign `result` unless the user explicitly requested data or a table alongside the plot.\\n3. `explanation`: A clear explanation in simple English explaining how it was calculated and what the key takeaways are.",
  "explanation": "Clear, friendly explanation of the answer, findings, and calculation steps in simple English."
}

Rules for code generation:
1. Do NOT load the CSV again; `df` is already available in scope.
2. Only use `pandas` (`pd`), `numpy` (`np`), `math`, `datetime`, `re`, and standard built-in Python libraries.
3. Do NOT import `sklearn` / `scikit-learn` or `scipy`. They are NOT installed in this air-gapped environment.
   - For normalization or min-max scaling: use standard pandas `(df[col] - df[col].min()) / (df[col].max() - df[col].min())`.
   - For standardization / z-score: use `(df[col] - df[col].mean()) / df[col].std()`.
   - For linear regression or trendlines: use `np.polyfit(x, y, deg=1)` or pure numpy/pandas.
4. Do NOT import `matplotlib`, `seaborn`, or `plotly`. All visualizations are rendered client-side from `chart_spec['option']` via Apache ECharts.
5. Ensure column names match the dataset exactly.
6. In `chart_spec['option']`, convert all series data and axis categories into native Python lists (e.g., `df['col'].tolist()`).
7. Do NOT output `result` or print a data table when plotting a chart unless the user explicitly asked to see the data or table in their request (e.g., 'show table and plot' or 'include data'). If the user only asked for a chart/plot, omit `result` so only the chart is displayed.

Visualization Guidelines (Keep charts simple, clear, and informative):
- Simplicity & Clarity: Do not clutter charts. Keep layouts clean with readable fonts and intuitive axis scaling.
- Units & Labels: Always specify clear axis names with units (e.g., name='Energy Usage (kWh)', name='Temperature (°F)').
- Choosing the right chart type:
  - Trends over time -> `type: 'line'` or `'area'` with `xAxis: {'type': 'category', 'data': [...]}`.
  - Discrete category comparisons -> `type: 'bar'` (use horizontal bars if category names are long).
  - Comparing two metrics with different units/scales -> Dual Y-axis:
    `yAxis: [{'type': 'value', 'name': 'kWh', 'position': 'left'}, {'type': 'value', 'name': 'Temp (°F)', 'position': 'right'}]`,
    and assign the second series `yAxisIndex: 1`.
  - Correlation between two numeric variables -> `type: 'scatter'`.
  - Statistical distributions & outliers -> `type: 'boxplot'`.
  - Matrix / time-of-day heatmaps -> `type: 'heatmap'` with `visualMap`.
  - Proportions of a whole (only for <= 6 categories) -> `type: 'pie'` (or donut).
- Highlighting & Markers:
  - When the user asks to highlight, mark, or call out specific points (e.g., top 25%, outliers, or peaks):
    In `series.data`, supply data items with custom styling:
    `{'value': val, 'symbol': 'circle', 'symbolSize': 10, 'itemStyle': {'color': '#ef4444'}}` for highlighted points, while normal points remain standard or `symbolSize: 0`.
  - Use `markLine` for key reference thresholds or averages (e.g. `markLine: {'data': [{'type': 'average', 'name': 'Mean'}]}`).
"""


class AgentService:
    """Orchestrates LLM query decomposition, code execution, self-correction retries, and SSE events."""

    def __init__(
        self,
        code_executor: Optional[CodeExecutor] = None,
        openai_client: Optional[AsyncOpenAI] = None
    ) -> None:
        self.code_executor = code_executor or CodeExecutor()
        self._client = openai_client

    def _get_client(self) -> AsyncOpenAI:
        """Lazily initialize and return the AsyncOpenAI client."""
        if self._client is not None:
            return self._client

        base_url = config.openai_api_base
        if not base_url:
            raise LLMConfigurationError(
                "OPENAI_API_BASE environment variable is not configured. "
                "Point it to your local or internal OpenAI-compatible endpoint."
            )

        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=config.openai_api_key or "EMPTY",
        )
        return self._client

    async def run_analysis_stream(
        self,
        session_id: str,
        user_query: str,
        df: pd.DataFrame,
        profile: DataProfile,
        chat_history: List[ChatMessage],
        dataset_description: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time SSE events for plan, execution, retries, visuals, and final explanation."""
        # Yield initial status
        yield {"event": "status", "data": "Analyzing question and dataset context..."}

        # Build prompt context
        messages = self._build_prompt_messages(
            user_query=user_query,
            profile=profile,
            chat_history=chat_history,
            dataset_description=dataset_description,
        )

        retries = 0
        max_retries = config.max_retries
        last_error = ""
        last_code = ""

        while retries <= max_retries:
            try:
                if retries > 0:
                    yield {
                        "event": "status",
                        "data": f"Self-correcting analysis code (attempt {retries}/{max_retries})..."
                    }
                    # Add error correction prompt
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Your previous Python code failed with this traceback:\n"
                            f"```\n{last_error}\n```\n"
                            f"Previous code was:\n```python\n{last_code}\n```\n"
                            f"Please correct the error, review the DataFrame column names and types, "
                            f"and provide the corrected JSON response."
                        )
                    })

                # Call LLM
                response_json = await self._call_llm(messages)
                plan = response_json.get("plan", "Generating data analysis plan...")
                code = response_json.get("code", "")
                initial_explanation = response_json.get("explanation", "")

                # Stream plan to client
                yield {"event": "plan", "data": plan}
                yield {"event": "status", "data": "Executing Python analysis code..."}

                last_code = code

                # Execute Python code against dataframe
                exec_result = self.code_executor.execute_code(
                    code=code,
                    df=df,
                    plan=plan,
                    explanation=initial_explanation,
                    retries_attempted=retries,
                    user_query=user_query,
                )

                # Stream execution artifacts
                yield {
                    "event": "execution_result",
                    "data": exec_result.model_dump()
                }

                # Stream tokens of explanation
                explanation_text = exec_result.explanation or initial_explanation
                chunk_size = 25
                for i in range(0, len(explanation_text), chunk_size):
                    chunk = explanation_text[i:i + chunk_size]
                    yield {"event": "token", "data": chunk}

                yield {"event": "done", "data": {"success": True}}
                return

            except CodeExecutionError as ce:
                last_error = ce.traceback_str
                retries += 1
                logger.warning("Execution error on attempt %s: %s", retries, ce.traceback_str)
                if retries > max_retries:
                    yield {
                        "event": "error",
                        "data": (
                            f"Could not complete calculation after {max_retries} attempts.\n"
                            f"Error details:\n{ce.traceback_str}"
                        )
                    }
                    return
            except Exception as e:
                logger.error("Agent error during analysis stream: %s", e)
                yield {"event": "error", "data": str(e)}
                return

    async def _call_llm(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send chat request to OpenAI-compatible endpoint with JSON format enforcement."""
        from typing import cast
        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=config.openai_model_name,
                messages=cast(Any, messages),
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
            parsed: Dict[str, Any] = json.loads(raw_content)
            return parsed
        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            raise LLMServiceError(status_code=500, response_text=str(e))

    def _build_prompt_messages(
        self,
        user_query: str,
        profile: DataProfile,
        chat_history: List[ChatMessage],
        dataset_description: str
    ) -> List[Dict[str, str]]:
        """Construct prompt context including column schemas, types, preview, and quality assumptions."""
        # Summarize columns for prompt
        col_lines: List[str] = []
        for c in profile.columns:
            line = f"- `{c.name}` ({c.data_type}): {c.column_description}"
            if c.sample_values:
                line += f" | Sample: {c.sample_values[:3]}"
            if c.mean_value is not None:
                line += f" | Mean: {c.mean_value}, Min: {c.min_value}, Max: {c.max_value}"
            col_lines.append(line)

        # Assumptions / quality flags
        assumptions_lines: List[str] = []
        for flag in profile.quality_report.flags:
            assumptions_lines.append(f"- [{flag.severity.upper()}] {flag.message}")

        context_msg = (
            f"Dataset Name: {profile.dataset_name}\n"
            f"Total Rows: {profile.row_count}, Total Columns: {profile.column_count}\n\n"
            f"General Context / Description:\n{dataset_description or 'No explicit description provided.'}\n\n"
            f"Columns Information:\n" + "\n".join(col_lines) + "\n\n"
        )
        if assumptions_lines:
            context_msg += "Known Data Quality Issues & Assumptions:\n" + "\n".join(assumptions_lines) + "\n"

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"DATASET CONTEXT:\n{context_msg}"},
        ]

        # Append recent user/assistant turns for context
        for msg in chat_history[-6:]:
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})

        # Append current user query
        messages.append({"role": "user", "content": user_query})
        return messages
