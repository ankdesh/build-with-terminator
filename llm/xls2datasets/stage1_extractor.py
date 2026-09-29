"""Stage 1: XLS/XLSX Table Extraction Module.

Uses IBM Docling's DocumentConverter to parse XLS/XLSX files,
detect table boundaries across sheets/tabs, and export each table
as an individual CSV file with an extraction manifest.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types.doc import (
    DoclingDocument,
    TableItem,
)

from config import (
    CSV_ENCODING,
    CSV_INDEX,
    DEFAULT_STAGE1_OUTPUT_DIR,
    EXTRACTION_MANIFEST_FILENAME,
    TABLES_SUBDIR_NAME,
)

logger = logging.getLogger(__name__)


class Stage1XlsExtractor:
    """Extracts tables from XLS/XLSX files into individual CSV files."""

    def __init__(self, output_dir: str | Path = DEFAULT_STAGE1_OUTPUT_DIR) -> None:
        """Initialize the extractor and create output directory structure.

        Args:
            output_dir: Target directory for extracted CSVs and manifest.
        """
        self.output_dir = Path(output_dir)
        self.tables_dir = self.output_dir / TABLES_SUBDIR_NAME
        self._create_directories()
        self.converter = self._init_converter()

    def _create_directories(self) -> None:
        """Create output directory hierarchy."""
        self.tables_dir.mkdir(parents=True, exist_ok=True)

    def _init_converter(self) -> DocumentConverter:
        """Configure Docling DocumentConverter for XLSX input format."""
        return DocumentConverter(
            allowed_formats=[InputFormat.XLSX]
        )

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize sheet/tab names to filesystem-safe identifiers."""
        clean = re.sub(r"[^\w\s-]", "", name).strip()
        return re.sub(r"[-\s]+", "_", clean)

    def extract(self, xls_path: str | Path) -> List[Path]:
        """Execute table extraction pipeline on target XLS/XLSX file.

        Args:
            xls_path: Path to the input XLS/XLSX file.

        Returns:
            List of generated CSV file paths.

        Raises:
            FileNotFoundError: If xls_path does not exist.
        """
        xls_file = Path(xls_path)
        if not xls_file.exists():
            raise FileNotFoundError(f"Input XLS file not found: {xls_path}")

        logger.info(f"Starting Stage 1 extraction for: {xls_file.name}")
        conversion_result = self.converter.convert(xls_file)
        doc: DoclingDocument = conversion_result.document

        return self._process_document(doc, xls_file.stem)

    def _process_document(
        self, doc: DoclingDocument, doc_stem: str
    ) -> List[Path]:
        """Traverse Docling document AST and extract all tables.

        Args:
            doc: Parsed DoclingDocument AST object.
            doc_stem: Base filename stem of the source XLS file.

        Returns:
            List of output CSV file paths.
        """
        csv_files: List[Path] = []
        table_metadata: List[Dict[str, Any]] = []

        # Track table counts per sheet for naming
        sheet_table_counts: Dict[str, int] = {}
        table_counter = 0

        for item, level in doc.iterate_items():
            if not isinstance(item, TableItem):
                continue

            table_counter += 1

            # Determine which sheet this table came from
            # Docling may expose sheet info via parent hierarchy or item metadata
            sheet_name = self._get_sheet_name(item, doc, table_counter)
            safe_sheet = self._sanitize_name(sheet_name)

            # Increment per-sheet counter
            sheet_table_counts[safe_sheet] = sheet_table_counts.get(safe_sheet, 0) + 1
            table_idx = sheet_table_counts[safe_sheet]

            csv_filename = f"{safe_sheet}_table_{table_idx:02d}.csv"
            csv_path = self.tables_dir / csv_filename

            # Export table to DataFrame then to CSV
            row_count = 0
            col_count = 0
            try:
                df = item.export_to_dataframe(doc=doc)
                df.to_csv(csv_path, index=CSV_INDEX, encoding=CSV_ENCODING)
                row_count = len(df)
                col_count = len(df.columns)
                logger.info(f"Exported table -> {csv_filename} ({row_count} rows, {col_count} cols)")
            except Exception as e:
                logger.warning(f"DataFrame export failed for table {table_counter}: {e}")
                # Fallback: export markdown representation to a text file
                try:
                    table_md = item.export_to_markdown(doc=doc)
                    csv_path = csv_path.with_suffix(".md")
                    csv_path.write_text(table_md, encoding=CSV_ENCODING)
                    logger.info(f"Exported table as markdown fallback -> {csv_path.name}")
                except Exception as e2:
                    logger.error(f"Markdown fallback also failed for table {table_counter}: {e2}")
                    continue

            csv_files.append(csv_path)

            table_metadata.append({
                "table_id": table_counter,
                "source_sheet": sheet_name,
                "filename": csv_path.name,
                "row_count": row_count,
                "col_count": col_count,
            })

        self._generate_manifest(doc_stem, table_metadata)
        return csv_files

    def _get_sheet_name(
        self, item: TableItem, doc: DoclingDocument, fallback_idx: int
    ) -> str:
        """Attempt to determine the source sheet name for a table item.

        Docling's XLSX parser may encode sheet info in the document hierarchy.
        Falls back to a generic name if not detectable.

        Args:
            item: The TableItem from the document.
            doc: The parent DoclingDocument.
            fallback_idx: Fallback index for naming.

        Returns:
            Sheet name string.
        """
        # Try to get sheet name from the item's parent hierarchy
        # Docling organizes XLSX content with section headers per sheet
        try:
            prov = item.prov
            if prov and len(prov) > 0:
                # Provenance may contain page number which maps to sheet index
                page_no = prov[0].page_no
                if page_no is not None:
                    return f"Sheet{page_no}"
        except (AttributeError, IndexError):
            pass

        # Try to walk parents to find a SectionHeaderItem
        try:
            parent = item.parent
            while parent is not None:
                if hasattr(parent, "text") and parent.text:
                    return parent.text
                parent = getattr(parent, "parent", None)
        except AttributeError:
            pass

        return f"Sheet_{fallback_idx}"

    def _generate_manifest(
        self, doc_stem: str, tables: List[Dict[str, Any]]
    ) -> Path:
        """Generate extraction manifest JSON.

        Args:
            doc_stem: Base filename stem of the source file.
            tables: List of table metadata dictionaries.

        Returns:
            Path to the manifest file.
        """
        manifest = {
            "source_file": doc_stem,
            "total_tables": len(tables),
            "tables": tables,
            "output_directory": str(self.tables_dir.resolve()),
        }

        manifest_path = self.output_dir / EXTRACTION_MANIFEST_FILENAME
        with open(manifest_path, "w", encoding=CSV_ENCODING) as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Stage 1 Manifest written -> {manifest_path}")
        return manifest_path
