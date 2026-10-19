"""Central configuration and constants for the KLayout DRC pipeline.

All hardcoded values, tool execution defaults, rule thresholds, and
custom exceptions are hoisted here to avoid magic constants across the codebase.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final


# Project Root Directory
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent

# Default Tool Execution Settings
DEFAULT_KLAYOUT_BIN: Final[str] = "klayout"
DEFAULT_TIMEOUT_SECONDS: Final[int] = 120

# Standard Paths
DEFAULT_DATA_DIR: Final[Path] = PROJECT_ROOT / "test_data"
DEFAULT_LAYOUTS_DIR: Final[Path] = DEFAULT_DATA_DIR / "layouts"
DEFAULT_RULES_DIR: Final[Path] = DEFAULT_DATA_DIR / "rules"
DEFAULT_REPORTS_DIR: Final[Path] = PROJECT_ROOT / "reports"

DEFAULT_GDS_PATH: Final[Path] = DEFAULT_LAYOUTS_DIR / "asap7_test.gds"
DEFAULT_DRC_SCRIPT_PATH: Final[Path] = DEFAULT_RULES_DIR / "asap7_mini.drc"
DEFAULT_REPORT_DB_PATH: Final[Path] = DEFAULT_REPORTS_DIR / "drc_violations.lyrdb"
DEFAULT_TEXT_REPORT_PATH: Final[Path] = DEFAULT_REPORTS_DIR / "drc_report.txt"
DEFAULT_KNOWLEDGE_DIR: Final[Path] = PROJECT_ROOT / "knowledge"
DEFAULT_FIX_SCRIPT_PATH: Final[Path] = DEFAULT_REPORTS_DIR / "fix_layout.py"

# Layout Context Extraction Settings
DEFAULT_WINDOW_HALO_UM: Final[float] = 0.100  # 100 nm window margin around violation markers
ASAP7_DBU_UM: Final[float] = 0.00025          # 0.25 nm database unit

# ASAP7 PDK Layer Definitions (Layer, Datatype)
LAYER_M1: Final[tuple[int, int]] = (18, 0)
LAYER_V1: Final[tuple[int, int]] = (19, 0)

# ASAP7 Geometric Rule Thresholds (in micrometers)
ASAP7_M1_MIN_WIDTH_UM: Final[float] = 0.018
ASAP7_M1_MIN_SPACING_UM: Final[float] = 0.018
ASAP7_V1_M1_MIN_ENCLOSURE_UM: Final[float] = 0.009


class DRCError(Exception):
    """Base exception for all DRC operations."""
    pass


class DRCConfigurationError(DRCError):
    """Raised when configuration, input files, or options are invalid."""
    pass


class DRCExecutionError(DRCError):
    """Raised when the KLayout engine execution fails."""
    pass


class DRCParserError(DRCError):
    """Raised when parsing report database or layout shapes fails."""
    pass


@dataclass(frozen=True)
class DRCJobConfig:
    """Configuration for a single DRC run."""
    input_gds: Path
    drc_script: Path
    output_lyrdb: Path
    klayout_bin: str = DEFAULT_KLAYOUT_BIN
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def validate(self) -> None:
        """Validate that input files exist and paths are well-formed."""
        if not self.input_gds.exists():
            raise DRCConfigurationError(f"Input GDS file does not exist: {self.input_gds}")
        if not self.drc_script.exists():
            raise DRCConfigurationError(f"DRC script file does not exist: {self.drc_script}")
        if not self.output_lyrdb.parent.exists():
            self.output_lyrdb.parent.mkdir(parents=True, exist_ok=True)
