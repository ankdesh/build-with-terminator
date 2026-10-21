"""Execution engine for running KLayout DRC scripts in batch mode.

Provides a robust runner that executes KLayout in headless batch mode,
validates return status, and verifies that the report database is materialized.
"""

import logging
import subprocess
from pathlib import Path

from .config import DRCJobConfig, DRCExecutionError

logger = logging.getLogger(__name__)


class DRCRunner:
    """Executes KLayout DRC runs against GDS layouts using specified runsets."""

    def __init__(self, config: DRCJobConfig) -> None:
        """Initialize with validated job configuration.
        
        Args:
            config: DRC job configuration specifying paths and timeout.
        """
        config.validate()
        self.config = config

    def run(self) -> Path:
        """Execute KLayout batch DRC and return the generated LYRDB path.
        
        Raises:
            DRCExecutionError: If KLayout fails or if the expected report database is not created.
            
        Returns:
            Path: Absolute path to the generated .lyrdb report database.
        """
        output_lyrdb = self.config.output_lyrdb.resolve()
        
        # Remove pre-existing report file to prevent stale results
        if output_lyrdb.exists():
            output_lyrdb.unlink()

        cmd = [
            self.config.klayout_bin,
            "-b",
            "-r", str(self.config.drc_script.resolve()),
            "-rd", f"{self.config.param_in_gds}={self.config.input_gds.resolve()}",
            "-rd", f"{self.config.param_report}={output_lyrdb}",
        ]
        for key, val in self.config.extra_params.items():
            cmd.extend(["-rd", f"{key}={val}"])

        logger.info("Executing KLayout command: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise DRCExecutionError(
                f"KLayout DRC run timed out after {self.config.timeout_seconds} seconds."
            ) from exc
        except FileNotFoundError as exc:
            raise DRCExecutionError(
                f"KLayout executable '{self.config.klayout_bin}' not found on PATH."
            ) from exc

        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else "Unknown error"
            raise DRCExecutionError(
                f"KLayout DRC execution failed with code {result.returncode}: {stderr_msg}"
            )

        if not output_lyrdb.exists():
            raise DRCExecutionError(
                f"KLayout finished with code 0 but report database '{output_lyrdb}' was not generated.\n"
                f"Stderr: {result.stderr}\nStdout: {result.stdout}"
            )

        return output_lyrdb
