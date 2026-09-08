"""
Centralized configuration for WPS-AI data analysis application.

Hoists all configuration values, environment variable lookups,
and default application constants.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


# --- Constants & Defaults ---
DEFAULT_SERVER_HOST: str = "127.0.0.1"
DEFAULT_SERVER_PORT: int = 8080
DEFAULT_MODEL_NAME: str = "gpt-4o-mini"
MAX_UPLOAD_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB
MAX_EXECUTION_RETRIES: int = 3
CODE_EXECUTION_TIMEOUT_SECONDS: int = 30
SAMPLE_DATA_PREVIEW_ROWS: int = 5
MAX_TABLE_PREVIEW_ROWS: int = 500

# Base directory paths
ROOT_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = ROOT_DIR / "data"
SESSIONS_DIR: Path = DATA_DIR / "sessions"
STATIC_DIR: Path = ROOT_DIR / "backend" / "static"


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration loaded from environment or defaults."""
    
    openai_api_base: Optional[str]
    openai_api_key: str
    openai_model_name: str
    server_host: str
    server_port: int
    sessions_dir: Path
    static_dir: Path
    max_retries: int
    exec_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables with fallback defaults."""
        api_base = os.getenv("OPENAI_API_BASE")
        api_key = os.getenv("OPENAI_API_KEY", "EMPTY")
        model_name = os.getenv("OPENAI_MODEL_NAME", DEFAULT_MODEL_NAME)
        
        host = os.getenv("HOST", DEFAULT_SERVER_HOST)
        port_raw = os.getenv("PORT")
        port = int(port_raw) if port_raw and port_raw.isdigit() else DEFAULT_SERVER_PORT
        
        sessions_path = Path(os.getenv("SESSIONS_DIR", str(SESSIONS_DIR)))
        sessions_path.mkdir(parents=True, exist_ok=True)
        
        return cls(
            openai_api_base=api_base.rstrip("/") if api_base else None,
            openai_api_key=api_key,
            openai_model_name=model_name,
            server_host=host,
            server_port=port,
            sessions_dir=sessions_path,
            static_dir=STATIC_DIR,
            max_retries=MAX_EXECUTION_RETRIES,
            exec_timeout_seconds=CODE_EXECUTION_TIMEOUT_SECONDS,
        )


# Global config instance singleton
config: AppConfig = AppConfig.from_env()
