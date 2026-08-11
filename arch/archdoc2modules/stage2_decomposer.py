"""Stage 2: Architectural Decomposition and Module Structure Generation.

Analyzes Stage 1 extracted Markdown sections and assets, uses OpenAI gpt-4o
(with heuristic fallback for offline testing) to determine system vs module boundaries,
and produces a modular Markdown directory structure with localized assets.
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

from pydantic import BaseModel, Field

from config import (
    ASSETS_DIR_NAME,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_STAGE2_OUTPUT_DIR,
    FIGURES_SUBDIR_NAME,
    LLM_TEMPERATURE,
    MAX_LLM_TOKENS,
    MODULES_DIR_NAME,
    TABLES_SUBDIR_NAME,
    TOP_LEVEL_DIR_NAME,
)

logger = logging.getLogger(__name__)


class ModuleSchema(BaseModel):
    """Pydantic model representing decomposed module metadata."""

    module_name: str = Field(description="Identifier for the module (e.g. dma_controller, interrupt_controller)")
    display_title: str = Field(description="Human readable title for the module")
    summary: str = Field(description="Brief overview of module function and capabilities")
    sections_involved: List[str] = Field(default_factory=list, description="Section filenames relevant to this module")
    figures_involved: List[str] = Field(default_factory=list, description="Figure image filenames associated with this module")
    tables_involved: List[str] = Field(default_factory=list, description="Table CSV filenames associated with this module")


class SystemDecompositionSchema(BaseModel):
    """Pydantic model for complete system decomposition structure."""

    system_name: str = Field(description="Name of the overall system / SoC specification")
    top_level_description: str = Field(description="Overview of top-level system architecture, buses, memory map")
    top_level_sections: List[str] = Field(default_factory=list, description="Section filenames for top-level system")
    modules: List[ModuleSchema] = Field(default_factory=list, description="List of identified architectural modules/IP blocks")


class Stage2Decomposer:
    """Decomposes Stage 1 outputs into top-level and module-level Markdown directories."""

    def __init__(
        self,
        stage1_dir: str | Path,
        output_dir: str | Path = DEFAULT_STAGE2_OUTPUT_DIR,
        openai_model: str = DEFAULT_OPENAI_MODEL,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize Stage 2 decomposer.

        Args:
            stage1_dir: Path to directory containing Stage 1 outputs.
            output_dir: Path to directory where modular outputs will be saved.
            openai_model: OpenAI model name (default gpt-4o).
            api_key: Optional OpenAI API key (defaults to OPENAI_API_KEY env var).
        """
        self.stage1_dir = Path(stage1_dir)
        self.output_dir = Path(output_dir)
        self.openai_model = openai_model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        self.sections_dir = self.stage1_dir / "sections"
        self.figures_dir = self.stage1_dir / "assets" / FIGURES_SUBDIR_NAME
        self.tables_dir = self.stage1_dir / "assets" / TABLES_SUBDIR_NAME
        self.manifest_file = self.stage1_dir / "parsing_manifest.json"

        self.top_level_dir = self.output_dir / TOP_LEVEL_DIR_NAME
        self.modules_dir = self.output_dir / MODULES_DIR_NAME

    def decompose(self) -> Dict[str, Any]:
        """Execute Stage 2 decomposition pipeline.

        Returns:
            Dictionary summary of generated modular structures.

        Raises:
            FileNotFoundError: If Stage 1 manifest or section directory is missing.
        """
        if not self.manifest_file.exists():
            raise FileNotFoundError(
                f"Stage 1 manifest not found at {self.manifest_file}. Run Stage 1 first."
            )

        with open(self.manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        logger.info(f"Loaded Stage 1 manifest for '{manifest.get('specification_name')}'")

        # Load section contents
        sections_map = self._load_sections()

        # Determine system decomposition (via OpenAI API if key available, else Heuristic)
        if self.api_key:
            logger.info(f"Using OpenAI API ({self.openai_model}) for architectural decomposition...")
            decomposition = self._llm_decompose(manifest, sections_map)
        else:
            logger.warning(
                "OPENAI_API_KEY not found. Falling back to rule-based heuristic decomposition."
            )
            decomposition = self._heuristic_decompose(manifest, sections_map)

        # Generate top-level documentation directory
        self._build_top_level(decomposition, sections_map)

        # Generate module documentation directories
        self._build_modules(decomposition, sections_map)

        summary = {
            "system_name": decomposition.system_name,
            "top_level_dir": str(self.top_level_dir.resolve()),
            "total_modules": len(decomposition.modules),
            "modules": [m.module_name for m in decomposition.modules],
        }

        # Save stage2 decomposition manifest
        with open(self.output_dir / "decomposition_manifest.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(
            f"Stage 2 Decomposition completed. Extracted {len(decomposition.modules)} modules."
        )
        return summary

    def _load_sections(self) -> Dict[str, str]:
        """Load all section Markdown contents from Stage 1 output directory."""
        sections_map: Dict[str, str] = {}
        if not self.sections_dir.exists():
            return sections_map

        for file_path in sorted(self.sections_dir.glob("*.md")):
            with open(file_path, "r", encoding="utf-8") as f:
                sections_map[file_path.name] = f.read()

        return sections_map

    def _llm_decompose(
        self, manifest: Dict[str, Any], sections_map: Dict[str, str]
    ) -> SystemDecompositionSchema:
        """Call OpenAI gpt-4o API to analyze section content and decompose architecture."""
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        prompt_sections = []
        for name, content in sections_map.items():
            # Truncate section preview if very long to stay within context
            preview = content[:2000]
            prompt_sections.append(f"--- Section File: {name} ---\n{preview}\n")

        full_prompt = (
            f"Specification Name: {manifest.get('specification_name')}\n"
            f"Total Sections: {len(sections_map)}\n\n"
            "Below are the extracted sections from a hardware architectural specification document:\n\n"
            + "\n".join(prompt_sections)
            + "\n\nTasks:\n"
            "1. Identify top-level system architecture sections (system overview, bus topologies, global memory map).\n"
            "2. Identify distinct hardware modules / functional IP blocks (e.g. DMA controller, Interrupt Controller, GPU, Core, etc.).\n"
            "3. For each module, list the relevant section filenames, figure images referenced (e.g. fig_001.png), and table CSVs referenced (e.g. table_001.csv).\n"
            "Provide the output strictly structured as requested."
        )

        try:
            response = client.beta.chat.completions.parse(
                model=self.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Electronic System-Level (ESL) hardware architect parsing specifications into modular documentation.",
                    },
                    {"role": "user", "content": full_prompt},
                ],
                response_format=SystemDecompositionSchema,
                temperature=LLM_TEMPERATURE,
            )
            parsed_result = response.choices[0].message.parsed
            if parsed_result:
                return parsed_result
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}. Falling back to heuristic decomposition.")

        return self._heuristic_decompose(manifest, sections_map)

    def _heuristic_decompose(
        self, manifest: Dict[str, Any], sections_map: Dict[str, str]
    ) -> SystemDecompositionSchema:
        """Rule-based heuristic decomposition when LLM key is unavailable."""
        system_name = manifest.get("specification_name", "Architecture_Spec")
        top_level_sections: List[str] = []
        modules: List[ModuleSchema] = []

        for sec_name, content in sections_map.items():
            # Find references to figures and tables
            figs = re.findall(r"[\w_-]+\_fig\_\d+\.png", content)
            tbls = re.findall(r"[\w_-]+\_table\_\d+\.csv", content)

            first_line = content.split("\n")[0] if content else ""
            title = re.sub(r"^#+\s*", "", first_line).strip() or sec_name

            # Classify section 0 or overview as top level
            if "00_" in sec_name or "overview" in sec_name.lower() or "introduction" in sec_name.lower():
                top_level_sections.append(sec_name)
            else:
                module_id = self._sanitize_name(title)
                modules.append(
                    ModuleSchema(
                        module_name=module_id,
                        display_title=title,
                        summary=f"Functional specification for module {title}",
                        sections_involved=[sec_name],
                        figures_involved=list(set(figs)),
                        tables_involved=list(set(tbls)),
                    )
                )

        if not top_level_sections and sections_map:
            top_level_sections.append(list(sections_map.keys())[0])

        return SystemDecompositionSchema(
            system_name=system_name,
            top_level_description=f"Top-level architecture specification for {system_name}",
            top_level_sections=top_level_sections,
            modules=modules,
        )

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert module title into clean directory name."""
        clean = re.sub(r"^[0-9\._\s]+", "", name)
        clean = re.sub(r"[^\w\s-]", "", clean).strip().lower()
        clean = re.sub(r"[-\s]+", "_", clean)
        return clean or "module"

    def _build_top_level(
        self, decomposition: SystemDecompositionSchema, sections_map: Dict[str, str]
    ) -> None:
        """Build output/top_level/ directory with README.md and localized assets."""
        self.top_level_dir.mkdir(parents=True, exist_ok=True)
        top_assets_dir = self.top_level_dir / ASSETS_DIR_NAME
        top_figures_dir = top_assets_dir / FIGURES_SUBDIR_NAME
        top_tables_dir = top_assets_dir / TABLES_SUBDIR_NAME

        top_figures_dir.mkdir(parents=True, exist_ok=True)
        top_tables_dir.mkdir(parents=True, exist_ok=True)

        readme_content = [
            f"# System Architecture: {decomposition.system_name}\n",
            f"## Overview\n\n{decomposition.top_level_description}\n",
        ]

        for sec_name in decomposition.top_level_sections:
            if sec_name in sections_map:
                sec_text = sections_map[sec_name]
                updated_text = self._localize_and_copy_assets(
                    sec_text, self.top_level_dir, top_figures_dir, top_tables_dir
                )
                readme_content.append(f"\n---\n\n{updated_text}")

        with open(self.top_level_dir / "README.md", "w", encoding="utf-8") as f:
            f.write("\n".join(readme_content))

    def _build_modules(
        self, decomposition: SystemDecompositionSchema, sections_map: Dict[str, str]
    ) -> None:
        """Build output/modules/<module_name>/ directories with README.md and localized assets."""
        self.modules_dir.mkdir(parents=True, exist_ok=True)

        for mod in decomposition.modules:
            mod_dir = self.modules_dir / mod.module_name
            mod_dir.mkdir(parents=True, exist_ok=True)

            mod_assets_dir = mod_dir / ASSETS_DIR_NAME
            mod_figures_dir = mod_assets_dir / FIGURES_SUBDIR_NAME
            mod_tables_dir = mod_assets_dir / TABLES_SUBDIR_NAME

            mod_figures_dir.mkdir(parents=True, exist_ok=True)
            mod_tables_dir.mkdir(parents=True, exist_ok=True)

            content_blocks = [
                f"# Module: {mod.display_title}\n",
                f"## Executive Summary\n\n{mod.summary}\n",
            ]

            # Copy explicit assets listed in metadata
            for fig in mod.figures_involved:
                src_fig = self.figures_dir / fig
                if src_fig.exists():
                    shutil.copy2(src_fig, mod_figures_dir / fig)

            for tbl in mod.tables_involved:
                src_tbl = self.tables_dir / tbl
                if src_tbl.exists():
                    shutil.copy2(src_tbl, mod_tables_dir / tbl)

            # Include content from involved sections
            for sec_name in mod.sections_involved:
                if sec_name in sections_map:
                    sec_text = sections_map[sec_name]
                    updated_text = self._localize_and_copy_assets(
                        sec_text, mod_dir, mod_figures_dir, mod_tables_dir
                    )
                    content_blocks.append(f"\n---\n\n{updated_text}")

            with open(mod_dir / "README.md", "w", encoding="utf-8") as f:
                f.write("\n".join(content_blocks))

    def _localize_and_copy_assets(
        self,
        text: str,
        base_dir: Path,
        target_fig_dir: Path,
        target_tbl_dir: Path,
    ) -> str:
        """Copy referenced figure and table files into local asset directory and update relative links."""
        # Find all figures referenced in markdown
        fig_matches = re.findall(r"!\s*\[([^\]]*)\]\(([^)]+)\)", text)
        for alt, link in fig_matches:
            fig_name = Path(link).name
            src_fig = self.figures_dir / fig_name
            if src_fig.exists():
                shutil.copy2(src_fig, target_fig_dir / fig_name)

                # New relative path from base_dir to target_fig_dir
                new_rel_path = os.path.relpath(target_fig_dir / fig_name, base_dir)
                text = text.replace(link, new_rel_path)

        # Find all table CSV links referenced in comments or text
        tbl_matches = re.findall(r"<!--\s*External Data:\s*\[([^\]]+)\]\(([^)]+)\)\s*-->", text)
        for tbl_label, link in tbl_matches:
            tbl_name = Path(link).name
            src_tbl = self.tables_dir / tbl_name
            if src_tbl.exists():
                shutil.copy2(src_tbl, target_tbl_dir / tbl_name)

                new_rel_path = os.path.relpath(target_tbl_dir / tbl_name, base_dir)
                text = text.replace(link, new_rel_path)

        return text
