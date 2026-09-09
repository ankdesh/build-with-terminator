"""Chat API routes with Server-Sent Events (SSE) streaming for real-time analysis."""

import io
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid
import pandas as pd
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.exceptions import SessionNotFoundError
from backend.models.chat import ChatMessage, ExecutionResult
from backend.services.agent_service import AgentService
from backend.services.session_store import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["Chat"])
session_store = SessionStore()
agent_service = AgentService()


class ChatQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language question or request")


class ExportCsvRequest(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    filename: Optional[str] = "wps_ai_export.csv"


@router.get("/messages", response_model=List[ChatMessage])
async def get_messages(session_id: str) -> List[ChatMessage]:
    """Get all past messages for the given session."""
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )
    return session_store.get_messages(session_id)


@router.post("/chat")
async def chat_stream(session_id: str, payload: ChatQueryRequest) -> EventSourceResponse:
    """Initiate streaming analysis. Emits plan, status, execution results, and explanation tokens."""
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    # Check if dataset has been uploaded
    try:
        csv_path = session_store.get_csv_path(session_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dataset uploaded for this session. Please upload a CSV first."
        )

    profile = session_store.get_profile(session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset profile not found. Please re-upload the CSV."
        )

    # Load dataset into memory
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error("Failed to read dataset from %s: %s", csv_path, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dataset: {e}"
        )

    # Record user message
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        role="user",
        content=payload.query
    )
    session_store.add_message(session_id, user_msg)

    # Retrieve chat history for context
    history = session_store.get_messages(session_id)
    dataset_desc = session_store.get_description(session_id)

    async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
        accumulated_plan: str = ""
        accumulated_explanation: str = ""
        captured_exec_result: Optional[ExecutionResult] = None

        try:
            async for chunk in agent_service.run_analysis_stream(
                session_id=session_id,
                user_query=payload.query,
                df=df,
                profile=profile,
                chat_history=history,
                dataset_description=dataset_desc,
            ):
                event_type = chunk.get("event", "message")
                event_data = chunk.get("data", "")

                if event_type == "plan" and isinstance(event_data, str):
                    accumulated_plan = event_data
                elif event_type == "token" and isinstance(event_data, str):
                    accumulated_explanation += event_data
                elif event_type == "execution_result" and isinstance(event_data, dict):
                    try:
                        captured_exec_result = ExecutionResult.model_validate(event_data)
                    except Exception as ex:
                        logger.warning("Could not parse ExecutionResult: %s", ex)

                # Format as SSE event (safely JSON-encode complex or multi-line event payloads)
                if event_type in ("execution_result", "done", "log", "code"):
                    data_str = json.dumps(event_data)
                elif isinstance(event_data, str):
                    data_str = event_data
                else:
                    data_str = json.dumps(event_data)

                yield {
                    "event": event_type,
                    "data": data_str
                }

            # Save assistant message to disk
            assistant_msg = ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=accumulated_explanation or (captured_exec_result.explanation if captured_exec_result else "Analysis completed."),
                plan=accumulated_plan,
                execution_result=captured_exec_result,
            )
            session_store.add_message(session_id, assistant_msg)

        except Exception as err:
            logger.error("Error in SSE event generator: %s", err)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(err)})
            }

    return EventSourceResponse(event_generator())


@router.post("/export-csv")
async def export_table_csv(payload: ExportCsvRequest) -> Response:
    """Export tabular result rows to a downloadable CSV file."""
    if not payload.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export.")

    df_export = pd.DataFrame(payload.rows)
    if payload.columns:
        valid_cols = [c for c in payload.columns if c in df_export.columns]
        if valid_cols:
            df_export = df_export[valid_cols]

    output = io.StringIO()
    df_export.to_csv(output, index=False)
    csv_text = output.getvalue()

    filename = payload.filename or "export.csv"
    if not filename.endswith(".csv"):
        filename += ".csv"

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
