"""Local file-based session persistence manager."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
from typing import List, Optional
import uuid

from backend.exceptions import SessionNotFoundError
from backend.models.chat import ChatMessage
from backend.models.profile import DataProfile
from backend.models.session import SessionMetadata
from config import config

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages session creation, persistence, file storage, and retrieval on local disk."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir: Path = base_dir or config.sessions_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_dir(self, session_id: str) -> Path:
        return self.base_dir / session_id

    def create_session(self, title: Optional[str] = None) -> SessionMetadata:
        """Create a new session with an isolated disk directory and initial metadata."""
        session_id = str(uuid.uuid4())
        session_dir = self._get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        now_iso = datetime.now(timezone.utc).isoformat()
        metadata = SessionMetadata(
            session_id=session_id,
            title=title or f"Analysis Session {datetime.now().strftime('%b %d, %H:%M')}",
            created_at=now_iso,
            updated_at=now_iso,
        )

        metadata_file = session_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=2))

        # Initialize empty messages list
        messages_file = session_dir / "messages.json"
        with open(messages_file, "w", encoding="utf-8") as f:
            json.dump([], f)

        logger.info("Created session %s at %s", session_id, session_dir)
        return metadata

    def get_session(self, session_id: str) -> SessionMetadata:
        """Retrieve metadata for a specific session ID or raise SessionNotFoundError."""
        metadata_file = self._get_session_dir(session_id) / "metadata.json"
        if not metadata_file.exists():
            raise SessionNotFoundError(session_id)

        with open(metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SessionMetadata.model_validate(data)

    def list_sessions(self) -> List[SessionMetadata]:
        """List all persisted sessions ordered by last update descending."""
        sessions: List[SessionMetadata] = []
        if not self.base_dir.exists():
            return sessions

        for path in self.base_dir.iterdir():
            if path.is_dir():
                meta_file = path / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            sessions.append(SessionMetadata.model_validate(json.load(f)))
                    except Exception as e:
                        logger.warning("Could not load session metadata at %s: %s", meta_file, e)

        # Sort newest first
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def update_session(self, metadata: SessionMetadata) -> None:
        """Update and overwrite session metadata."""
        session_dir = self._get_session_dir(metadata.session_id)
        if not session_dir.exists():
            raise SessionNotFoundError(metadata.session_id)

        metadata.updated_at = datetime.now(timezone.utc).isoformat()
        metadata_file = session_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=2))

    def save_dataset(
        self,
        session_id: str,
        csv_bytes: bytes,
        csv_filename: str,
        desc_text: str,
        desc_filename: str,
        row_count: int,
        column_count: int,
    ) -> SessionMetadata:
        """Store uploaded CSV and description files into the session directory."""
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            raise SessionNotFoundError(session_id)

        # Save CSV file
        csv_path = session_dir / "data.csv"
        with open(csv_path, "wb") as f:
            f.write(csv_bytes)

        # Save description file
        desc_path = session_dir / "description.txt"
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(desc_text)

        metadata = self.get_session(session_id)
        metadata.csv_filename = csv_filename
        metadata.desc_filename = desc_filename
        metadata.row_count = row_count
        metadata.column_count = column_count
        metadata.dataset_description = desc_text
        metadata.updated_at = datetime.now(timezone.utc).isoformat()
        if metadata.title.startswith("Analysis Session"):
            metadata.title = f"Analysis: {csv_filename}"

        self.update_session(metadata)
        return metadata

    def get_csv_path(self, session_id: str) -> Path:
        """Get the absolute path to the stored CSV for a session."""
        csv_path = self._get_session_dir(session_id) / "data.csv"
        if not csv_path.exists():
            raise SessionNotFoundError(session_id)
        return csv_path

    def get_description(self, session_id: str) -> str:
        """Get the stored dataset description text."""
        desc_path = self._get_session_dir(session_id) / "description.txt"
        if not desc_path.exists():
            return ""
        with open(desc_path, "r", encoding="utf-8") as f:
            return f.read()

    def save_profile(self, session_id: str, profile: DataProfile) -> None:
        """Save computed data profile to session disk."""
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            raise SessionNotFoundError(session_id)

        profile_file = session_dir / "profile.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))

    def get_profile(self, session_id: str) -> Optional[DataProfile]:
        """Load stored data profile if present."""
        profile_file = self._get_session_dir(session_id) / "profile.json"
        if not profile_file.exists():
            return None
        with open(profile_file, "r", encoding="utf-8") as f:
            return DataProfile.model_validate(json.load(f))

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        """Append a new chat message to session history."""
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            raise SessionNotFoundError(session_id)

        messages = self.get_messages(session_id)
        messages.append(message)

        messages_file = session_dir / "messages.json"
        with open(messages_file, "w", encoding="utf-8") as f:
            json.dump([m.model_dump() for m in messages], f, indent=2)

        meta = self.get_session(session_id)
        meta.updated_at = datetime.now(timezone.utc).isoformat()
        self.update_session(meta)

    def get_messages(self, session_id: str) -> List[ChatMessage]:
        """Load all chat messages for a session."""
        messages_file = self._get_session_dir(session_id) / "messages.json"
        if not messages_file.exists():
            return []
        try:
            with open(messages_file, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            return [ChatMessage.model_validate(m) for m in raw_list]
        except Exception as e:
            logger.warning("Error loading messages for %s: %s", session_id, e)
            return []

    def delete_session(self, session_id: str) -> None:
        """Permanently delete a session and all its stored files."""
        session_dir = self._get_session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
            logger.info("Deleted session directory %s", session_dir)
