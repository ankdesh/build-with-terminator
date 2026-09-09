"""
Centralized configuration for WPS-AI data analysis application.

Loads application settings from config.json, while keeping the API key
strictly in the environment variable (OPENAI_API_KEY) for security.
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("wps-ai.config")

# --- Constants & Defaults ---
DEFAULT_OPENAI_API_BASE: str = "https://api.openai.com/v1"
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
CONFIG_FILE_PATH: Path = ROOT_DIR / "config.json"
DATA_DIR: Path = ROOT_DIR / "data"
SESSIONS_DIR: Path = DATA_DIR / "sessions"
STATIC_DIR: Path = ROOT_DIR / "backend" / "static"


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration loaded from config.json and environment."""

    openai_api_base: str
    openai_api_key: str
    openai_model_name: str
    server_host: str
    server_port: int
    sessions_dir: Path
    static_dir: Path
    max_retries: int
    exec_timeout_seconds: int
    max_upload_size_bytes: int

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AppConfig":
        """Load configuration from config.json, taking OPENAI_API_KEY from environment."""
        target_path = config_path or CONFIG_FILE_PATH
        file_settings: Dict[str, Any] = {}

        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    file_settings = json.load(f)
                logger.info("Loaded configuration from %s", target_path)
            except Exception as e:
                logger.error("Failed to parse %s: %s. Using default values.", target_path, e)
        else:
            logger.info("Config file %s not found. Generating default config.json...", target_path)
            file_settings = {
                "openai_api_base": DEFAULT_OPENAI_API_BASE,
                "openai_model_name": DEFAULT_MODEL_NAME,
                "server_host": DEFAULT_SERVER_HOST,
                "server_port": DEFAULT_SERVER_PORT,
                "max_retries": MAX_EXECUTION_RETRIES,
                "exec_timeout_seconds": CODE_EXECUTION_TIMEOUT_SECONDS,
                "max_upload_size_bytes": MAX_UPLOAD_FILE_SIZE_BYTES,
            }
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(file_settings, f, indent=2)
            except Exception as e:
                logger.warning("Could not create default %s: %s", target_path, e)

        # Retrieve values with defaults
        api_base = str(file_settings.get("openai_api_base") or DEFAULT_OPENAI_API_BASE).rstrip("/")
        model_name = str(file_settings.get("openai_model_name") or DEFAULT_MODEL_NAME)
        host = str(file_settings.get("server_host") or DEFAULT_SERVER_HOST)
        port = int(file_settings.get("server_port") or DEFAULT_SERVER_PORT)
        retries = int(file_settings.get("max_retries") or MAX_EXECUTION_RETRIES)
        timeout = int(file_settings.get("exec_timeout_seconds") or CODE_EXECUTION_TIMEOUT_SECONDS)
        upload_limit = int(file_settings.get("max_upload_size_bytes") or MAX_UPLOAD_FILE_SIZE_BYTES)

        # API Key is strictly sourced from environment variable for secret isolation
        api_key = os.getenv("OPENAI_API_KEY", "EMPTY")

        sessions_path = SESSIONS_DIR
        sessions_path.mkdir(parents=True, exist_ok=True)

        return cls(
            openai_api_base=api_base,
            openai_api_key=api_key,
            openai_model_name=model_name,
            server_host=host,
            server_port=port,
            sessions_dir=sessions_path,
            static_dir=STATIC_DIR,
            max_retries=retries,
            exec_timeout_seconds=timeout,
            max_upload_size_bytes=upload_limit,
        )


# Global config singleton
config: AppConfig = AppConfig.load()
