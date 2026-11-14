"""Local file-based session persistence manager."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import shutil
import threading
from typing import Any, ClassVar, Dict, List, Optional
import uuid

from backend.exceptions import SessionNotFoundError
from backend.models.chat import ChatMessage
from backend.models.profile import DataProfile
from backend.models.session import SessionMetadata
from config import config

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages session creation, persistence, file storage, and retrieval on local disk."""

    # Shared in-memory surrogate model cache across all SessionStore instances (Milestone 3)
    _surrogate_cache: ClassVar[Dict[str, Any]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir: Path = base_dir or config.sessions_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Note: _surrogate_cache is a shared ClassVar, not initialized per instance.

    def __setattr__(self, name: str, value: Any) -> None:
        """Route instance assignments to _surrogate_cache into the shared class dictionary."""
        if name == "_surrogate_cache":
            with SessionStore._cache_lock:
                SessionStore._surrogate_cache.clear()
                if isinstance(value, dict):
                    SessionStore._surrogate_cache.update(value)
            return
        super().__setattr__(name, value)

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

        # Invalidate cached surrogate model since underlying dataset changed
        self.invalidate_surrogate_cache(session_id)

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

    def get_surrogate(self, session_id: str, target_col: Optional[str] = None) -> Optional[Any]:
        """Retrieve cached in-memory surrogate model for a session and target metric.

        Strict target matching:
        - If target_col is provided (not None): checks f"{session_id}:{target_col}".
          If found, returns it. If NOT found, returns None (never falls back to an unrelated metric).
        - If target_col is None: checks f"{session_id}:default". If found, returns it.
          If not found, falls back to returning the first cached model matching f"{session_id}:" or key == session_id.
        - Returns None on cache miss. Thread-safe class-level cache lookup.
        """
        with SessionStore._cache_lock:
            if target_col is not None:
                return SessionStore._surrogate_cache.get(f"{session_id}:{target_col}")

            default_key = f"{session_id}:default"
            if default_key in SessionStore._surrogate_cache:
                return SessionStore._surrogate_cache[default_key]

            prefix = f"{session_id}:"
            for key, model in list(SessionStore._surrogate_cache.items()):
                if key.startswith(prefix) or key == session_id:
                    return model
            return None

    def save_surrogate(
        self,
        session_id: str,
        target_col_or_surrogate: Any,
        surrogate_or_none: Optional[Any] = None,
    ) -> None:
        """Store trained surrogate model into fast in-memory cache for sub-millisecond evaluation.

        Supports both (session_id, target_col, surrogate) and (session_id, surrogate, target_col) signatures.
        """
        if isinstance(target_col_or_surrogate, str):
            target = target_col_or_surrogate
            model = surrogate_or_none
        else:
            model = target_col_or_surrogate
            target = surrogate_or_none or getattr(model, "target_col", None) or "default"

        cache_key = f"{session_id}:{target}"
        with SessionStore._cache_lock:
            SessionStore._surrogate_cache[cache_key] = model
        logger.info("Cached surrogate model in memory for session %s (key: %s)", session_id, cache_key)

    # Alias for save_surrogate
    set_surrogate = save_surrogate

    def invalidate_surrogate_cache(self, session_id: str) -> None:
        """Evict all cached surrogate models for a session across all store instances."""
        prefix = f"{session_id}:"
        with SessionStore._cache_lock:
            keys_to_delete = [
                k for k in list(SessionStore._surrogate_cache.keys())
                if k.startswith(prefix) or k == session_id
            ]
            for k in keys_to_delete:
                SessionStore._surrogate_cache.pop(k, None)
        if keys_to_delete:
            logger.info("Evicted %d surrogate cache entries for session %s", len(keys_to_delete), session_id)

    # Alias for invalidate_surrogate_cache
    clear_surrogate = invalidate_surrogate_cache

    @classmethod
    def clear_all_surrogates(cls) -> None:
        """Evict all cached surrogate models across all sessions (primarily for testing and resets)."""
        with cls._cache_lock:
            cls._surrogate_cache.clear()

    def delete_session(self, session_id: str) -> None:
        """Permanently delete a session and all its stored files."""
        self.invalidate_surrogate_cache(session_id)
        session_dir = self._get_session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
            logger.info("Deleted session directory %s", session_dir)
