"""Stage 2: LLM-Powered Schema Analysis Module.

Reads extracted CSV tables from Stage 1, sends sample data to a
configurable OpenAI-compatible LLM, and generates structured data
dictionaries (column types, units, descriptions) per table.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml
from pydantic import BaseModel, Field

from config import (
    CSV_ENCODING,
    DATA_DICTIONARY_FILENAME,
    DEFAULT_LLM_CONFIG_PATH,
    DEFAULT_STAGE2_OUTPUT_DIR,
    EXTRACTION_MANIFEST_FILENAME,
    LLM_API_KEY_ENV_VAR,
    SCHEMA_SAMPLE_ROWS,
    SCHEMAS_SUBDIR_NAME,
    TABLES_SUBDIR_NAME,
)

logger = logging.getLogger(__name__)


# --- Pydantic models for structured LLM output ---

class ColumnSchema(BaseModel):
    """Schema definition for a single column."""

    column_name: str = Field(description="Name of the column as it appears in the CSV header")
    data_type: str = Field(description="Inferred data type: int, float, string, date, boolean, or categorical")
    unit: Optional[str] = Field(default=None, description="Measurement unit if detectable (e.g., °C, kg, m/s)")
    description: str = Field(description="Brief description of what this column represents")


class TableSchema(BaseModel):
    """Schema definition for an entire table."""

    table_name: str = Field(description="Identifier for the table (from CSV filename)")
    table_description: str = Field(description="Brief summary of what data this table contains")
    columns: List[ColumnSchema] = Field(default_factory=list, description="Schema for each column")
    suggested_index_columns: List[str] = Field(
        default_factory=list,
        description="Column names suggested as DataFrame index for analysis",
    )


class LLMConfig(BaseModel):
    """Configuration for the LLM connection."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 4096


class Stage2SchemaAnalyzer:
    """Analyzes extracted CSV tables using an LLM to generate data dictionaries."""

    def __init__(
        self,
        stage1_dir: str | Path,
        output_dir: str | Path = DEFAULT_STAGE2_OUTPUT_DIR,
        config_path: str | Path = DEFAULT_LLM_CONFIG_PATH,
    ) -> None:
        """Initialize the schema analyzer.

        Args:
            stage1_dir: Path to Stage 1 output directory containing CSVs and manifest.
            output_dir: Path for Stage 2 outputs (schemas, data dictionary).
            config_path: Path to LLM configuration YAML file.
        """
        self.stage1_dir = Path(stage1_dir)
        self.output_dir = Path(output_dir)
        self.tables_dir = self.stage1_dir / TABLES_SUBDIR_NAME
        self.schemas_dir = self.output_dir / SCHEMAS_SUBDIR_NAME
        self.manifest_path = self.stage1_dir / EXTRACTION_MANIFEST_FILENAME

        self.llm_config = self._load_llm_config(Path(config_path))
        self.api_key = os.getenv(LLM_API_KEY_ENV_VAR)

        self._create_directories()

    def _create_directories(self) -> None:
        """Create output directory hierarchy."""
        self.schemas_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_llm_config(config_path: Path) -> LLMConfig:
        """Load LLM configuration from YAML file.

        Args:
            config_path: Path to the YAML config file.

        Returns:
            Parsed LLMConfig object.
        """
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)
            if raw_config:
                return LLMConfig(**raw_config)

        logger.warning(f"LLM config not found at {config_path}, using defaults.")
        return LLMConfig()

    def analyze(self) -> Dict[str, Any]:
        """Execute Stage 2 schema analysis pipeline.

        Returns:
            Data dictionary summary.

        Raises:
            FileNotFoundError: If Stage 1 manifest is missing.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Stage 1 manifest not found at {self.manifest_path}. Run Stage 1 first."
            )

        with open(self.manifest_path, "r", encoding=CSV_ENCODING) as f:
            manifest = json.load(f)

        logger.info(f"Loaded Stage 1 manifest for '{manifest.get('source_file')}'")

        table_schemas: List[Dict[str, Any]] = []

        for table_info in manifest.get("tables", []):
            csv_filename = table_info["filename"]
            csv_path = self.tables_dir / csv_filename

            if not csv_path.exists():
                logger.warning(f"CSV file not found: {csv_path}, skipping.")
                continue

            schema = self._analyze_table(csv_path, table_info)
            if schema:
                table_schemas.append(schema)

        # Generate overall data dictionary
        data_dictionary = {
            "source_file": manifest.get("source_file"),
            "total_tables": len(table_schemas),
            "tables": table_schemas,
        }

        dict_path = self.output_dir / DATA_DICTIONARY_FILENAME
        with open(dict_path, "w", encoding=CSV_ENCODING) as f:
            json.dump(data_dictionary, f, indent=2)

        logger.info(
            f"Stage 2 complete. Generated schemas for {len(table_schemas)} tables."
        )
        return data_dictionary

    def _analyze_table(
        self, csv_path: Path, table_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single table CSV using the LLM.

        Args:
            csv_path: Path to the CSV file.
            table_info: Metadata from the extraction manifest.

        Returns:
            Schema dictionary, or None on failure.
        """
        table_name = csv_path.stem

        try:
            df = pd.read_csv(csv_path, encoding=CSV_ENCODING)
        except Exception as e:
            logger.error(f"Failed to read CSV {csv_path.name}: {e}")
            return None

        # Prepare sample data for LLM
        sample_rows = min(SCHEMA_SAMPLE_ROWS, len(df))
        sample_csv = df.head(sample_rows).to_csv(index=False)

        if self.api_key:
            schema = self._llm_analyze(table_name, sample_csv, table_info)
        else:
            logger.warning(
                f"{LLM_API_KEY_ENV_VAR} not set. Using heuristic schema for {table_name}."
            )
            schema = self._heuristic_analyze(table_name, df, table_info)

        if schema:
            # Write per-table schema JSON
            schema_path = self.schemas_dir / f"{table_name}_schema.json"
            with open(schema_path, "w", encoding=CSV_ENCODING) as f:
                json.dump(schema, f, indent=2)
            logger.info(f"Schema written -> {schema_path.name}")

        return schema

    def _llm_analyze(
        self,
        table_name: str,
        sample_csv: str,
        table_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI-compatible LLM for structured schema analysis.

        Args:
            table_name: Identifier for the table.
            sample_csv: CSV string of sample rows.
            table_info: Metadata from extraction manifest.

        Returns:
            Schema dictionary or None on failure.
        """
        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.llm_config.base_url,
        )

        prompt = (
            f"You are analyzing a data table extracted from an Excel spreadsheet.\n\n"
            f"Table name: {table_name}\n"
            f"Source sheet: {table_info.get('source_sheet', 'unknown')}\n"
            f"Total rows: {table_info.get('row_count', 'unknown')}\n"
            f"Total columns: {table_info.get('col_count', 'unknown')}\n\n"
            f"Here is a sample of the data (first {SCHEMA_SAMPLE_ROWS} rows as CSV):\n\n"
            f"```csv\n{sample_csv}```\n\n"
            f"Analyze this table and provide:\n"
            f"1. A brief description of what data this table contains.\n"
            f"2. For each column: the column name, inferred data type "
            f"(int, float, string, date, boolean, or categorical), "
            f"measurement unit if applicable, and a brief description.\n"
            f"3. Which columns would make good DataFrame index columns for analysis.\n"
        )

        try:
            response = client.beta.chat.completions.parse(
                model=self.llm_config.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data analyst expert. Analyze tabular data "
                            "and produce structured schema metadata."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format=TableSchema,
                temperature=self.llm_config.temperature,
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                return parsed.model_dump()
        except Exception as e:
            logger.error(f"LLM analysis failed for {table_name}: {e}")

        # Fallback to heuristic
        logger.warning(f"Falling back to heuristic analysis for {table_name}.")
        try:
            df = pd.read_csv(
                self.tables_dir / f"{table_name}.csv", encoding=CSV_ENCODING
            )
        except Exception:
            return None
        return self._heuristic_analyze(table_name, df, table_info)

    def _heuristic_analyze(
        self,
        table_name: str,
        df: pd.DataFrame,
        table_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate schema using pandas dtype heuristics when LLM is unavailable.

        Args:
            table_name: Identifier for the table.
            df: Loaded DataFrame.
            table_info: Metadata from extraction manifest.

        Returns:
            Schema dictionary.
        """
        columns = []
        for col in df.columns:
            dtype = str(df[col].dtype)

            if "int" in dtype:
                inferred_type = "int"
            elif "float" in dtype:
                inferred_type = "float"
            elif "bool" in dtype:
                inferred_type = "boolean"
            elif "datetime" in dtype:
                inferred_type = "date"
            else:
                inferred_type = "string"

            columns.append({
                "column_name": str(col),
                "data_type": inferred_type,
                "unit": None,
                "description": f"Column '{col}' with pandas dtype {dtype}",
            })

        return {
            "table_name": table_name,
            "table_description": (
                f"Table from sheet '{table_info.get('source_sheet', 'unknown')}' "
                f"with {len(df)} rows and {len(df.columns)} columns."
            ),
            "columns": columns,
            "suggested_index_columns": [],
        }
