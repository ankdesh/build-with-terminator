"""Common configuration and path definitions for scenarios automation.

All temporary outputs, reports, and screenshots are captured under temp/TEMP_ folder
in strict adherence to the project constitution.
"""

from pathlib import Path

# Base temporary directories
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMP_BASE_DIR = REPO_ROOT / "temp"
TEMP_REPORTS_DIR = TEMP_BASE_DIR / "TEMP_reports"
SCREENSHOTS_DIR = TEMP_REPORTS_DIR / "screenshots"

def ensure_temp_dirs() -> None:
    """Ensure the temporary report and screenshot directories exist."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
