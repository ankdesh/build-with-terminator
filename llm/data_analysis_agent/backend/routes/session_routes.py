"""API routes for session lifecycle management and file uploads."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.exceptions import DataProfilingError, SessionNotFoundError
from backend.models.profile import DataProfile
from backend.models.session import SessionMetadata
from backend.services.data_profiler import DataProfiler
from backend.services.session_store import SessionStore
from config import MAX_UPLOAD_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])
session_store = SessionStore()
data_profiler = DataProfiler()


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SessionDetailResponse(BaseModel):
    metadata: SessionMetadata
    profile: Optional[DataProfile] = None
    message_count: int = 0


@router.post("", response_model=SessionMetadata, status_code=status.HTTP_201_CREATED)
async def create_session(payload: Optional[CreateSessionRequest] = None) -> SessionMetadata:
    """Create a new isolated session."""
    title = payload.title if payload else None
    return session_store.create_session(title=title)


@router.get("", response_model=List[SessionMetadata])
async def list_sessions() -> List[SessionMetadata]:
    """List all available persisted sessions."""
    return session_store.list_sessions()


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str) -> SessionDetailResponse:
    """Get metadata, profile, and message statistics for a session."""
    try:
        metadata = session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    profile = session_store.get_profile(session_id)
    messages = session_store.get_messages(session_id)

    return SessionDetailResponse(
        metadata=metadata,
        profile=profile,
        message_count=len(messages),
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> None:
    """Delete a session and all its persistent data."""
    try:
        session_store.delete_session(session_id)
    except Exception as e:
        logger.warning("Error deleting session %s: %s", session_id, e)


@router.post("/{session_id}/upload", response_model=SessionDetailResponse)
async def upload_dataset(
    session_id: str,
    csv_file: UploadFile = File(..., description="The CSV dataset file"),
    desc_file: Optional[UploadFile] = File(None, description="Optional column descriptions text file"),
    description_text: Optional[str] = Form(None, description="Optional raw text descriptions")
) -> SessionDetailResponse:
    """Upload CSV dataset and description file, triggering automated profiling and persistence."""
    try:
        session_store.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )

    # Read CSV bytes
    csv_bytes = await csv_file.read()
    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded CSV file is empty."
        )
    if len(csv_bytes) > MAX_UPLOAD_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_FILE_SIZE_BYTES / (1024 * 1024)} MB."
        )

    # Read column description text
    desc_content = ""
    desc_filename = ""
    if desc_file is not None and desc_file.filename:
        raw_desc = await desc_file.read()
        desc_content = raw_desc.decode("utf-8", errors="replace")
        desc_filename = desc_file.filename
    elif description_text:
        desc_content = description_text
        desc_filename = "manual_description.txt"

    # Profile the CSV
    try:
        profile = data_profiler.profile_csv(
            session_id=session_id,
            csv_bytes=csv_bytes,
            dataset_name=csv_file.filename or "data.csv",
            column_descriptions_text=desc_content,
        )
    except DataProfilingError as dpe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to profile CSV data: {dpe.details}"
        )

    # Persist dataset and profile
    updated_meta = session_store.save_dataset(
        session_id=session_id,
        csv_bytes=csv_bytes,
        csv_filename=csv_file.filename or "data.csv",
        desc_text=desc_content,
        desc_filename=desc_filename,
        row_count=profile.row_count,
        column_count=profile.column_count,
    )
    session_store.save_profile(session_id, profile)

    return SessionDetailResponse(
        metadata=updated_meta,
        profile=profile,
        message_count=len(session_store.get_messages(session_id)),
    )
