"""Centralized configuration module for xls2datasets.

Hoists system constants, default file paths, and directory naming conventions.
"""

from pathlib import Path
from typing import Final

# Default output directories
DEFAULT_STAGE1_OUTPUT_DIR: Final[Path] = Path("./extracted_tables")
DEFAULT_STAGE2_OUTPUT_DIR: Final[Path] = Path("./analyzed_datasets")

# Subdirectory names
TABLES_SUBDIR_NAME: Final[str] = "tables"
SCHEMAS_SUBDIR_NAME: Final[str] = "schemas"

# Manifest filenames
EXTRACTION_MANIFEST_FILENAME: Final[str] = "extraction_manifest.json"
DATA_DICTIONARY_FILENAME: Final[str] = "data_dictionary.json"

# LLM configuration
DEFAULT_LLM_CONFIG_PATH: Final[Path] = Path("llm_config.yaml")
LLM_API_KEY_ENV_VAR: Final[str] = "OPENAI_API_KEY"

# CSV export settings
CSV_ENCODING: Final[str] = "utf-8"
CSV_INDEX: Final[bool] = False

# Schema analysis settings
SCHEMA_SAMPLE_ROWS: Final[int] = 20  # Number of rows to send to LLM for analysis
