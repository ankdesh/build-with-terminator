"""Session domain models for persisting and managing user analysis sessions."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Metadata describing a single analysis session and its associated dataset."""

    session_id: str = Field(..., description="Unique identifier for the session")
    title: str = Field(default="Untitled Session", description="Human-readable session title")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of creation"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of last update"
    )
    csv_filename: Optional[str] = Field(default=None, description="Original uploaded CSV filename")
    desc_filename: Optional[str] = Field(default=None, description="Original uploaded column description filename")
    row_count: int = Field(default=0, description="Number of rows in the loaded dataset")
    column_count: int = Field(default=0, description="Number of columns in the loaded dataset")
    dataset_description: str = Field(default="", description="High-level description of dataset context")
