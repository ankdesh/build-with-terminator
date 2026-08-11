"""Centralized configuration module for archdoc2modules.

Hoists system constants, default file paths, image scaling factors,
and OpenAI model configurations.
"""

import os
from pathlib import Path
from typing import Final

# Pipeline default paths
DEFAULT_STAGE1_OUTPUT_DIR: Final[Path] = Path("./parsed_stage1")
DEFAULT_STAGE2_OUTPUT_DIR: Final[Path] = Path("./decomposed_stage2")

# Stage 1 (Docling) parameters
DEFAULT_IMAGE_DPI_SCALE: Final[float] = 2.0
DEFAULT_MIN_SURFACE_RATIO: Final[float] = 0.0  # Extract all pictures regardless of size
FIGURES_SUBDIR_NAME: Final[str] = "figures"
TABLES_SUBDIR_NAME: Final[str] = "tables"
SECTIONS_SUBDIR_NAME: Final[str] = "sections"
MANIFEST_FILENAME: Final[str] = "parsing_manifest.json"

# Stage 2 (OpenAI LLM) parameters
DEFAULT_OPENAI_MODEL: Final[str] = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_LLM_TOKENS: Final[int] = 4096
LLM_TEMPERATURE: Final[float] = 0.2

# Top-level vs Module folder names
TOP_LEVEL_DIR_NAME: Final[str] = "top_level"
MODULES_DIR_NAME: Final[str] = "modules"
ASSETS_DIR_NAME: Final[str] = "assets"
