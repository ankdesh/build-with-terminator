import os
import io
import zipfile
import pandas as pd
from PIL import Image
from pathlib import Path
from typing import Optional, Union

# Docling core type definitions
from docling_core.types.doc import (
    DoclingDocument, 
    TextItem, 
    TableItem, 
    PictureItem, 
    GroupItem,
    NodeItem
)
from docling_core.types.doc.labels import DocItemLabel, GroupLabel

# Ingestion & converter pipeline configurations
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat


class CustomDocumentWriter:
    """
    An extensible writer class that compiles a parsed DoclingDocument into
    a custom proprietary structure (e.g., zipped XMLs, nested trees, or custom JSON formats).
    
    Exposes explicit stubs to parse, isolate, and write texts, tables, and images.
    """
    def __init__(self):
        # State tracking for your proprietary format
        self.doc_name: str = "custom_document"
        self.output_manifest = {
            "sections": [],
            "tables": {},
            "images": {}
        }
        self.current_section = None
        self._image_counter = 0
        self._table_counter = 0

    # =========================================================================
    # STUB 1: SECTION / STRUCTURAL GROUP START
    # =========================================================================
    def start_group(self, group: GroupItem, level: int):
        """
        STUB: Triggered when entering a structural grouping (e.g., Chapter, List, Section).
        Use this to open nested sections in your custom XML or ODT-like document structure.
        """
        group_label = group.label  # e.g., GroupLabel.SECTION, GroupLabel.LIST
        group_name = getattr(group, "name", "Unnamed Group")
        
        # Example logic for nesting sections:
        section_entry = {
            "type": "group_start",
            "label": str(group_label),
            "name": group_name,
            "level": level,
            "items": []
        }
        self.output_manifest["sections"].append(section_entry)
        self.current_section = section_entry
        
        print(f"{'  ' * level}[GROUP START] {group_label} : {group_name}")

    # =========================================================================
    # STUB 2: SECTION / STRUCTURAL GROUP END
    # =========================================================================
    def end_group(self, level: int):
        """
        STUB: Triggered when layout leaves a nested group.
        Use this to emit closing tags (e.g., </section> or </ul>) in your proprietary writer.
        """
        self.output_manifest["sections"].append({
            "type": "group_end",
            "level": level
        })
        print(f"{'  ' * level}[GROUP END]")

    # =========================================================================
    # STUB 3: TEXT ITEM HANDLING (Headings, Paragraphs, Code, Formulas)
    # =========================================================================
    def handle_text_item(self, text_item: TextItem, level: int):
        """
        STUB: Triggered for textual elements in reading order.
        Inspect text_item.label to format differently (e.g., headings, code blocks, lists).
        """
        text = text_item.text
        label = text_item.label  # e.g., DocItemLabel.PARAGRAPH, DocItemLabel.TITLE
        
        # Determine specific textual semantics # [citegc: 8]:
        if label == DocItemLabel.TITLE:
            custom_block = {"element": "h1", "text": text}
        elif label == DocItemLabel.SECTION_HEADER:
            custom_block = {"element": "h2", "text": text}
        elif label == DocItemLabel.CODE:
            custom_block = {"element": "code", "text": text, "language": getattr(text_item, "formatting", None)}
        elif label == DocItemLabel.FORMULA:
            # Mathematical notation automatically rendered as standardized LaTeX # [citegc: 8]
            custom_block = {"element": "math_formula", "latex": text}
        else:
            custom_block = {"element": "p", "text": text}
            
        custom_block["level"] = level
        
        if self.current_section:
            self.current_section["items"].append(custom_block)
        else:
            self.output_manifest["sections"].append(custom_block)
            
        print(f"{'  ' * level}[TEXT] ({label}): {text[:60]}...")

    # =========================================================================
    # STUB 4: TABULAR DATA HANDLING
    # =========================================================================
    def handle_table_item(self, table_item: TableItem, doc: DoclingDocument, level: int):
        """
        STUB: Triggered when a table is encountered.
        Extracts structural grids, row/column metadata, headers, or Pandas DataFrames.
        """
        self._table_counter += 1
        table_id = f"table_{self._table_counter}"
        
        # Method A: Direct export to a standard Pandas DataFrame # [citegc: 9, 10]
        df: pd.DataFrame = table_item.export_to_dataframe(doc=doc)
        
        # Method B: Fine-grained topological traversal of table headers and spans # [citegc: 7, 8]
        table_cells_custom = []
        for cell in table_item.data.table_cells:
            table_cells_custom.append({
                "text": cell.text,
                "row_start": cell.start_row_offset_idx,
                "row_end": cell.end_row_offset_idx,
                "col_start": cell.start_col_offset_idx,
                "col_end": cell.end_col_offset_idx,
                "is_header": cell.column_header or cell.row_header ## [citegc: 7]
            })

        self.output_manifest["tables"][table_id] = {
            "columns": list(df.columns),
            "raw_data": df.values.tolist(),
            "cells_structure": table_cells_custom,
            "level": level
        }
        
        # Referencing the extracted table in the main layout stream
        ref_block = {"element": "table_reference", "id": table_id, "level": level}
        if self.current_section:
            self.current_section["items"].append(ref_block)
        else:
            self.output_manifest["sections"].append(ref_block)
            
        print(f"{'  ' * level}[TABLE] ({table_id}) : {df.shape[0]} rows x {df.shape[1]} columns")

    # =========================================================================
    # STUB 5: PICTURE / IMAGE HANDLING
    # =========================================================================
    def handle_picture_item(self, picture_item: PictureItem, doc: DoclingDocument, level: int):
        """
        STUB: Triggered when an image is encountered.
        Crops, processes, and embeds or references high-resolution images.
        """
        self._image_counter += 1
        image_id = f"image_{self._image_counter}"
        
        # Safely extract the PIL Image representation from memory cache
        pil_image: Optional[Image.Image] = picture_item.get_image(doc)
        
        if pil_image:
            # Stub for custom graphics manipulation (rescaling, compressing, vectorization, etc.)
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()
            
            # Store the graphic metadata and binaries separately
            self.output_manifest["images"][image_id] = {
                "bytes": img_bytes,
                "format": "PNG",
                "width": pil_image.width,
                "height": pil_image.height,
                "level": level
            }
            
            # Record picture captions if available # [citegc: 8]
            caption = picture_item.caption_text(doc=doc) if hasattr(picture_item, "caption_text") else ""
            
            ref_block = {
                "element": "image_reference", 
                "id": image_id, 
                "caption": caption,
                "level": level
            }
            if self.current_section:
                self.current_section["items"].append(ref_block)
            else:
                self.output_manifest["sections"].append(ref_block)
                
            print(f"{'  ' * level}[IMAGE] ({image_id}) : Captured {pil_image.width}x{pil_image.height} PIL Image")
        else:
            print(f"{'  ' * level}[IMAGE] ({image_id}) : Image missing/uncropped. Check pipeline options.")

    # =========================================================================
    # STUB 6: CUSTOM PACKAGING AND SAVING
    # =========================================================================
    def save_as_custom_format(self, output_file_path: Path):
        """
        STUB: Re-packages the separated structural data (text, tables, images) 
        into your proprietary custom format (e.g., standard zip archive containing 
        content XMLs and image binaries, similar to ODF/docx).
        """
        print(f"\nConstructing proprietary Custom Archive: '{output_file_path.name}'")
        
        # Establish a compressed ODF-style package
        with zipfile.ZipFile(output_file_path, "w", zipfile.ZIP_DEFLATED) as custom_zip:
            # 1. Package the structural content mapping (like content.xml in ODT)
            # Remove raw byte elements before converting mapping manifest to text/JSON
            serialized_manifest = {
                "sections": self.output_manifest["sections"],
                "tables": self.output_manifest["tables"],
                "images_meta": {
                    k: {"width": v["width"], "height": v["height"]} 
                    for k, v in self.output_manifest["images"].items()
                }
            }
            
            # Format and save structural content XML or JSON
            import json
            custom_zip.writestr("content.json", json.dumps(serialized_manifest, indent=2))
            
            # 2. Package graphic assets inside a separated subdirectory
            for img_id, img_data in self.output_manifest["images"].items():
                custom_zip.writestr(f"Pictures/{img_id}.png", img_data["bytes"])
                
            # 3. Package layout metadata
            meta_payload = f"Generated by Docling Custom Parser. Version: 1.0"
            custom_zip.writestr("meta.txt", meta_payload)
            
        print("Successfully compiled and saved.")


# =============================================================================
# EXECUTABLE PIPELINE ORCHESTRATION
# =============================================================================
def convert_document_to_custom(input_file: Path, output_archive: Path):
    """
    Orchestrates the ingestion, tree traversal, and conversion logic.
    """
    # 1. Setup layout parsing options (enable image rendering & structural extraction)
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.generate_picture_images = True  # MANDATORY for PIL crop retrieval # [citegc: 5, 11]
    pipeline_options.images_scale = 2.0             # Up-scale canvas sampling resolution # [citegc: 5, 12]
    
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    
    print("Initiating layout parsing...")
    conversion_result = converter.convert(input_file)
    doc: DoclingDocument = conversion_result.document
    
    # 2. Walk the Tree Node-by-Node in layout-aware Reading Order
    custom_writer = CustomDocumentWriter()
    
    # Track nesting transitions using a tracker stack
    active_group_stack = []
    
    # Traverse depth-first walk using iterate_items
    # yield items along with their structural nesting levels
    for item, level in doc.iterate_items(with_groups=True, traverse_pictures=False): ## [citegc: 3]
        # Resolve group nesting scope shifts
        while len(active_group_stack) > level:
            active_group_stack.pop()
            custom_writer.end_group(level=len(active_group_stack))
            
        # Case A: Element is a Structural Group (Section boundaries, Lists, Chapters, etc.)
        if isinstance(item, GroupItem): # [citegc: 2, 7]
            custom_writer.start_group(item, level=level)
            active_group_stack.append(item)
            
        # Case B: Element is an individual Text Block
        elif isinstance(item, TextItem): # [citegc: 2, 7]
            custom_writer.handle_text_item(item, level=level)
            
        # Case C: Element is a Table
        elif isinstance(item, TableItem): # [citegc: 2, 7]
            custom_writer.handle_table_item(item, doc=doc, level=level)
            
        # Case D: Element is a Graphical Picture or Figure
        elif isinstance(item, PictureItem): # [citegc: 2, 7]
            custom_writer.handle_picture_item(item, doc=doc, level=level)

    # Resolve any remaining hanging groups on exit
    while len(active_group_stack) > 0:
        active_group_stack.pop()
        custom_writer.end_group(level=len(active_group_stack))

    # 3. Export to your packaged binary format
    custom_writer.save_as_custom_format(output_archive)


if __name__ == "__main__":
    # Configure input and output workspace
    input_pdf_path = Path("sample_document.pdf")
    output_custom_file = Path("output_document.custom")  # Your zipped, ODT-like package
    
    if not input_pdf_path.exists():
        print(f"Please provide a document file at: '{input_pdf_path.absolute()}' to test conversion.")
    else:
        convert_document_to_custom(input_pdf_path, output_custom_file)
