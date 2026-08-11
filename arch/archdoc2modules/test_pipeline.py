"""Integration test suite for archdoc2modules pipeline.

Generates a test architectural specification PDF, runs Stage 1 (Docling parsing)
and Stage 2 (Decomposition), and asserts the validity of output structures and localized assets.
"""

import json
import shutil
import sys
import unittest
from pathlib import Path

from create_sample_spec_pdf import generate_sample_architecture_pdf
from stage1_parser import Stage1DoclingParser
from stage2_decomposer import Stage2Decomposer


class TestArchDoc2ModulesPipeline(unittest.TestCase):
    """Test suite for PDF to Modular Architecture Pipeline."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment and generate test PDF."""
        cls.test_dir = Path("./test_workspace")
        cls.test_dir.mkdir(exist_ok=True)

        cls.pdf_path = cls.test_dir / "sample_arch_spec.pdf"
        generate_sample_architecture_pdf(str(cls.pdf_path))

        cls.stage1_output = cls.test_dir / "parsed_stage1"
        cls.stage2_output = cls.test_dir / "decomposed_stage2"

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test artifacts."""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_stage1_parsing(self) -> None:
        """Test Stage 1 PDF parsing and asset externalization."""
        parser = Stage1DoclingParser(output_dir=self.stage1_output)
        section_files = parser.parse_pdf(self.pdf_path)

        self.assertTrue(len(section_files) > 0, "Stage 1 generated 0 section markdown files.")

        manifest_path = self.stage1_output / "parsing_manifest.json"
        self.assertTrue(manifest_path.exists(), "Stage 1 parsing manifest is missing.")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("specification_name", manifest)
        self.assertEqual(manifest["specification_name"], "sample_arch_spec")

        sections_dir = self.stage1_output / "sections"
        tables_dir = self.stage1_output / "assets" / "tables"

        self.assertTrue(sections_dir.exists(), "Stage 1 sections directory missing.")
        self.assertTrue(tables_dir.exists(), "Stage 1 tables directory missing.")

    def test_02_stage2_decomposition(self) -> None:
        """Test Stage 2 architectural decomposition into top_level and module directories."""
        decomposer = Stage2Decomposer(
            stage1_dir=self.stage1_output,
            output_dir=self.stage2_output,
        )
        summary = decomposer.decompose()

        self.assertIn("total_modules", summary)
        self.assertTrue(summary["total_modules"] > 0, "Stage 2 generated 0 modules.")

        top_level_readme = self.stage2_output / "top_level" / "README.md"
        self.assertTrue(top_level_readme.exists(), "Top level README.md is missing.")

        modules_dir = self.stage2_output / "modules"
        self.assertTrue(modules_dir.exists(), "Modules directory is missing.")

        submodules = [d for d in modules_dir.iterdir() if d.is_dir()]
        self.assertTrue(len(submodules) > 0, "No module folders created in output/modules/")

        for mod_dir in submodules:
            mod_readme = mod_dir / "README.md"
            self.assertTrue(mod_readme.exists(), f"Module README.md missing in {mod_dir.name}")

            mod_assets = mod_dir / "assets"
            self.assertTrue(mod_assets.exists(), f"Local assets folder missing in {mod_dir.name}")


if __name__ == "__main__":
    unittest.main()
