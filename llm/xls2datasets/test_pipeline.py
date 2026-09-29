"""Integration test suite for xls2datasets pipeline.

Generates a test XLSX file, runs Stage 1 (Docling extraction) and
Stage 2 (Schema analysis), and validates output structure and content.
"""

import json
import shutil
import unittest
from pathlib import Path

import pandas as pd

from create_sample_xls import generate_sample_xlsx
from stage1_extractor import Stage1XlsExtractor
from stage2_schema_analyzer import Stage2SchemaAnalyzer


class TestXls2DatasetsPipeline(unittest.TestCase):
    """Test suite for XLS to Datasets pipeline."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment and generate test XLSX."""
        cls.test_dir = Path("./test_workspace")
        cls.test_dir.mkdir(exist_ok=True)

        cls.xlsx_path = cls.test_dir / "sample_data.xlsx"
        generate_sample_xlsx(str(cls.xlsx_path))

        cls.stage1_output = cls.test_dir / "extracted_tables"
        cls.stage2_output = cls.test_dir / "analyzed_datasets"

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test artifacts."""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_stage1_extraction(self) -> None:
        """Test Stage 1 XLSX table extraction and CSV generation."""
        extractor = Stage1XlsExtractor(output_dir=self.stage1_output)
        csv_files = extractor.extract(self.xlsx_path)

        # Should extract at least one table
        self.assertTrue(len(csv_files) > 0, "Stage 1 extracted 0 tables.")

        # Manifest should exist
        manifest_path = self.stage1_output / "extraction_manifest.json"
        self.assertTrue(manifest_path.exists(), "Extraction manifest is missing.")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("source_file", manifest)
        self.assertEqual(manifest["source_file"], "sample_data")
        self.assertTrue(manifest["total_tables"] > 0)

        # Tables directory should exist with CSV files
        tables_dir = self.stage1_output / "tables"
        self.assertTrue(tables_dir.exists(), "Tables directory missing.")

        csv_count = len(list(tables_dir.glob("*.csv")))
        self.assertTrue(csv_count > 0, "No CSV files generated in tables directory.")

        # Each CSV should be loadable by pandas
        for csv_file in tables_dir.glob("*.csv"):
            df = pd.read_csv(csv_file)
            self.assertTrue(len(df) > 0, f"CSV {csv_file.name} is empty.")
            self.assertTrue(len(df.columns) > 0, f"CSV {csv_file.name} has no columns.")

    def test_02_stage2_schema_analysis(self) -> None:
        """Test Stage 2 schema analysis (heuristic mode, no LLM key required)."""
        analyzer = Stage2SchemaAnalyzer(
            stage1_dir=self.stage1_output,
            output_dir=self.stage2_output,
        )
        result = analyzer.analyze()

        self.assertIn("total_tables", result)
        self.assertTrue(result["total_tables"] > 0, "Stage 2 analyzed 0 tables.")

        # Schemas directory should exist
        schemas_dir = self.stage2_output / "schemas"
        self.assertTrue(schemas_dir.exists(), "Schemas directory missing.")

        # Each table should have a schema JSON
        schema_count = len(list(schemas_dir.glob("*_schema.json")))
        self.assertTrue(schema_count > 0, "No schema files generated.")

        # Data dictionary should exist
        dict_path = self.stage2_output / "data_dictionary.json"
        self.assertTrue(dict_path.exists(), "Data dictionary is missing.")

        with open(dict_path, "r", encoding="utf-8") as f:
            data_dict = json.load(f)

        self.assertIn("tables", data_dict)
        for table in data_dict["tables"]:
            self.assertIn("table_name", table)
            self.assertIn("columns", table)
            self.assertTrue(len(table["columns"]) > 0, f"No columns in {table['table_name']}")

            for col in table["columns"]:
                self.assertIn("column_name", col)
                self.assertIn("data_type", col)
                self.assertIn("description", col)


if __name__ == "__main__":
    unittest.main()
