"""Stage 1: PDF Specification Ingestion and Parsing Module.

Converts an architectural specification PDF into section-bounded Markdown files,
externalized figure images (PNG), tabular data files (CSV), and a manifest using IBM Docling.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import (
    DoclingDocument,
    PictureItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
)

from config import (
    DEFAULT_IMAGE_DPI_SCALE,
    DEFAULT_MIN_SURFACE_RATIO,
    DEFAULT_STAGE1_OUTPUT_DIR,
    FIGURES_SUBDIR_NAME,
    MANIFEST_FILENAME,
    SECTIONS_SUBDIR_NAME,
    TABLES_SUBDIR_NAME,
)

logger = logging.getLogger(__name__)


class Stage1DoclingParser:
    """Parses PDF specifications into modular Markdown sections with externalized assets."""

    def __init__(self, output_dir: str | Path = DEFAULT_STAGE1_OUTPUT_DIR) -> None:
        """Initialize parser and create directory structure.

        Args:
            output_dir: Target directory path for extracted sections and assets.
        """
        self.output_dir = Path(output_dir)
        self.sections_dir = self.output_dir / SECTIONS_SUBDIR_NAME
        self.assets_dir = self.output_dir / "assets"
        self.figures_dir = self.assets_dir / FIGURES_SUBDIR_NAME
        self.tables_dir = self.assets_dir / TABLES_SUBDIR_NAME

        self._create_directories()
        self.converter = self._init_converter()

    def _create_directories(self) -> None:
        """Create output directory hierarchy."""
        self.sections_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def _init_converter(self) -> DocumentConverter:
        """Configure Docling DocumentConverter with high DPI and table structure options."""
        pipeline_options = PdfPipelineOptions()
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = DEFAULT_IMAGE_DPI_SCALE
        pipeline_options.do_table_structure = True
        # Ensure small diagrams/figures are not dropped
        if hasattr(pipeline_options, "min_picture_page_surface_ratio"):
            pipeline_options.min_picture_page_surface_ratio = DEFAULT_MIN_SURFACE_RATIO

        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize heading strings to filesystem-safe identifiers."""
        clean_name = re.sub(r"[^\w\s-]", "", name).strip().lower()
        return re.sub(r"[-\s]+", "_", clean_name)

    def parse_pdf(self, pdf_path: str | Path) -> List[Path]:
        """Execute full extraction pipeline on target PDF specification.

        Args:
            pdf_path: Filepath to the input PDF specification document.

        Returns:
            List of generated section Markdown filepaths.

        Raises:
            FileNotFoundError: If pdf_path does not exist.
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"Input PDF specification not found: {pdf_path}")

        logger.info(f"Starting Stage 1 parsing for specification: {pdf_file.name}")
        conversion_result = self.converter.convert(pdf_file)
        doc: DoclingDocument = conversion_result.document

        return self._process_document_tree(doc, pdf_file.stem)

    def _process_document_tree(
        self, doc: DoclingDocument, doc_stem: str
    ) -> List[Path]:
        """Traverse Docling structural AST and extract section-bounded Markdown files.

        Args:
            doc: Parsed DoclingDocument AST object.
            doc_stem: Base filename stem of the source PDF.

        Returns:
            List of output section markdown file paths.
        """
        section_files: List[Path] = []
        current_section_title = "00_introduction_and_overview"
        current_section_idx = 0
        current_buffer: List[str] = []

        figure_counter = 0
        table_counter = 0

        def flush_section_buffer(
            title: str, index: int, content: List[str]
        ) -> Optional[Path]:
            if not content:
                return None
            safe_title = self._sanitize_filename(title)
            filename = f"section_{index:02d}_{safe_title}.md"
            filepath = self.sections_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Section: {title}\n\n")
                f.write("\n\n".join(content))
                f.write("\n")

            logger.info(f"Exported Section -> {filepath.name}")
            return filepath

        for item, level in doc.iterate_items():
            if isinstance(item, SectionHeaderItem):
                header_level = getattr(item, "level", 1)
                header_text = item.text.strip()

                # Major section headers (level <= 2) trigger a buffer flush
                if header_level <= 2 and current_buffer:
                    saved_path = flush_section_buffer(
                        current_section_title, current_section_idx, current_buffer
                    )
                    if saved_path:
                        section_files.append(saved_path)

                    current_section_idx += 1
                    current_section_title = header_text
                    current_buffer = []

                prefix = "#" * header_level
                current_buffer.append(f"{prefix} {header_text}")

            elif isinstance(item, TextItem):
                text = item.text.strip()
                if text:
                    current_buffer.append(text)

            elif isinstance(item, PictureItem):
                figure_counter += 1
                fig_filename = f"{doc_stem}_fig_{figure_counter:03d}.png"
                fig_path = self.figures_dir / fig_filename

                image_obj = item.get_image(doc)
                if image_obj:
                    image_obj.save(fig_path, format="PNG")

                    rel_fig_path = os.path.relpath(fig_path, self.sections_dir)
                    caption_text = (
                        item.caption_text(doc)
                        if hasattr(item, "caption_text")
                        else ""
                    )
                    alt_text = (
                        caption_text
                        if caption_text
                        else f"Architectural Diagram {figure_counter}"
                    )

                    md_image_ref = f"![{alt_text}]({rel_fig_path})"
                    if caption_text:
                        md_image_ref += f"\n*Figure {figure_counter}: {caption_text}*"

                    current_buffer.append(md_image_ref)

            elif isinstance(item, TableItem):
                table_counter += 1
                tbl_csv_filename = f"{doc_stem}_table_{table_counter:03d}.csv"
                tbl_csv_path = self.tables_dir / tbl_csv_filename

                try:
                    df = item.export_to_dataframe()
                    df.to_csv(tbl_csv_path, index=False)
                except Exception as e:
                    logger.warning(f"Could not export table {table_counter} to DataFrame/CSV: {e}")

                table_md = item.export_to_markdown(doc=doc)
                rel_tbl_path = os.path.relpath(tbl_csv_path, self.sections_dir)

                caption_text = (
                    item.caption_text(doc) if hasattr(item, "caption_text") else ""
                )
                tbl_block = (
                    f"<!-- External Data: [{tbl_csv_filename}]({rel_tbl_path}) -->\n"
                    + table_md
                )
                if caption_text:
                    tbl_block += f"\n*Table {table_counter}: {caption_text}*"

                current_buffer.append(tbl_block)

        if current_buffer:
            saved_path = flush_section_buffer(
                current_section_title, current_section_idx, current_buffer
            )
            if saved_path:
                section_files.append(saved_path)

        self._generate_manifest(doc_stem, section_files, figure_counter, table_counter)
        return section_files

    def _generate_manifest(
        self, doc_stem: str, sections: List[Path], fig_count: int, tbl_count: int
    ) -> Path:
        """Compile document metadata and asset paths into machine-readable JSON manifest.

        Args:
            doc_stem: Base filename stem of specification.
            sections: List of section files generated.
            fig_count: Total extracted figures.
            tbl_count: Total extracted tables.

        Returns:
            Path to manifest file.
        """
        manifest = {
            "specification_name": doc_stem,
            "total_sections": len(sections),
            "total_figures": fig_count,
            "total_tables": tbl_count,
            "sections": [p.name for p in sections],
            "asset_paths": {
                "sections": str(self.sections_dir.resolve()),
                "figures": str(self.figures_dir.resolve()),
                "tables": str(self.tables_dir.resolve()),
            },
        }
        manifest_path = self.output_dir / MANIFEST_FILENAME
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Stage 1 Manifest written -> {manifest_path}")
        return manifest_path
