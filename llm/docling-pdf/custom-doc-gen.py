import os
import io
import argparse
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
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, PaginatedPipelineOptions
from docling.datamodel.base_models import InputFormat


class CustomDocumentWriter:
    """
    An extensible writer class that compiles a parsed DoclingDocument into
    a custom proprietary structure (e.g., zipped XMLs, nested trees, or custom JSON formats).
    
    Exposes explicit stubs to parse, isolate, and write texts, tables, and images.
    """
    def __init__(self):
        # State tracking for your proprietary format
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
        group_label = group.label  # e.g., GroupLabel.SECTION, GroupLabel.LIST # [citegc: 8]
        group_name = getattr(group, "name", "Unnamed Group")
        
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
        label = text_item.label  # e.g., DocItemLabel.PARAGRAPH, DocItemLabel.TITLE # [citegc: 8]
        
        if label == DocItemLabel.TITLE:
            custom_block = {"element": "h1", "text": text}
        elif label == DocItemLabel.SECTION_HEADER:
            custom_block = {"element": "h2", "text": text}
        elif label == DocItemLabel.CODE:
            custom_block = {"element": "code", "text": text, "language": getattr(text_item, "formatting", None)}
        elif label == DocItemLabel.FORMULA:
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
        
        # Direct export to a standard Pandas DataFrame # [citegc: 9]
        df: pd.DataFrame = table_item.export_to_dataframe(doc=doc)
        
        # Fine-grained topological traversal of table headers and spans # [citegc: 8]
        table_cells_custom = []
        for cell in table_item.data.table_cells:
            table_cells_custom.append({
                "text": cell.text,
                "row_start": cell.start_row_offset_idx,
                "row_end": cell.end_row_offset_idx,
                "col_start": cell.start_col_offset_idx,
                "col_end": cell.end_col_offset_idx,
                "is_header": cell.column_header or cell.row_header # [citegc: 8]
            })

        self.output_manifest["tables"][table_id] = {
            "columns": list(df.columns),
            "raw_data": df.values.tolist(),
            "cells_structure": table_cells_custom,
            "level": level
        }
        
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
            img_buffer = io.BytesIO()
            pil_image.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()
            
            self.output_manifest["images"][image_id] = {
                "bytes": img_bytes,
                "format": "PNG",
                "width": pil_image.width,
                "height": pil_image.height,
                "level": level
            }
            
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
            print(f"{'  ' * level}[IMAGE] ({image_id}) : Graphic missing or format does not support visual cropping.")

    # =========================================================================
    # STUB 6: CUSTOM PACKAGING AND SAVING
    # =========================================================================
    def save_as_custom_format(self, output_file_path: Path):
        """
        STUB: Re-packages structural content mapping and separated image buffers 
        into your proprietary custom zip archive (similar to ODF/ODT containers).
        """
        print(f"\nConstructing proprietary Custom Archive: '{output_file_path.name}'")
        
        with zipfile.ZipFile(output_file_path, "w", zipfile.ZIP_DEFLATED) as custom_zip:
            # Prepare serialization manifest (excluding raw byte arrays)
            serialized_manifest = {
                "sections": self.output_manifest["sections"],
                "tables": self.output_manifest["tables"],
                "images_meta": {
                    k: {"width": v["width"], "height": v["height"]} 
                    for k, v in self.output_manifest["images"].items()
                }
            }
            
            import json
            custom_zip.writestr("content.json", json.dumps(serialized_manifest, indent=2))
            
            # Save the raw image bytes in a subdirectory inside the zip
            for img_id, img_data in self.output_manifest["images"].items():
                custom_zip.writestr(f"Pictures/{img_id}.png", img_data["bytes"])
                
            custom_zip.writestr("meta.txt", "Generated dynamically by Docling Custom Multi-Format Engine.")
            
        print(f"Successfully compiled custom archive at: {output_file_path}")


# =============================================================================
# EXECUTABLE PIPELINE ORCHESTRATION
# =============================================================================
def convert_document_to_custom(input_file: Path, output_archive: Path):
    """
    Handles dynamic document configuration, conversion, and structural tree traversal.
    """
    # Configure high-resolution rendering and table OCR settings for PDFs
    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = True
    pdf_options.do_table_structure = True
    pdf_options.generate_picture_images = True
    pdf_options.images_scale = 2.0
    
    # Configure picture extraction settings for paginated DOCX/PPTX files
    word_options = PaginatedPipelineOptions()
    word_options.generate_picture_images = True
    word_options.images_scale = 2.0

    # Initialize DocumentConverter with custom overrides for paginated file types # [citegc: 6]
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            InputFormat.DOCX: WordFormatOption(pipeline_options=word_options)
        }
    )
    
    print(f"Processing input file: '{input_file.name}'")
    conversion_result = converter.convert(input_file)
    doc: DoclingDocument = conversion_result.document
    
    custom_writer = CustomDocumentWriter()
    active_group_stack = []
    
    # Traverse depth-first tree in programmatic reading order # [citegc: 10]
    for item, level in doc.iterate_items(with_groups=True, traverse_pictures=False):
        # Handle group nesting scope shifts
        while len(active_group_stack) > level:
            active_group_stack.pop()
            custom_writer.end_group(level=len(active_group_stack))
            
        if isinstance(item, GroupItem):
            custom_writer.start_group(item, level=level)
            active_group_stack.append(item)
            
        elif isinstance(item, TextItem):
            custom_writer.handle_text_item(item, level=level)
            
        elif isinstance(item, TableItem):
            custom_writer.handle_table_item(item, doc=doc, level=level)
            
        elif isinstance(item, PictureItem):
            custom_writer.handle_picture_item(item, doc=doc, level=level)

    # Clean up any trailing unclosed groupings
    while len(active_group_stack) > 0:
        active_group_stack.pop()
        custom_writer.end_group(level=len(active_group_stack))

    # Compile the final customized ODT-style container
    custom_writer.save_as_custom_format(output_archive)


if __name__ == "__main__":
    # Command Line Interface (CLI) configuration using standard argparse
    parser = argparse.ArgumentParser(
        description="Convert any Docling-supported document format (PDF, DOCX, ODT, HTML, PNG, etc.) into a custom XML/JSON zip format."
    )
    parser.add_argument(
        "input_file", 
        type=str, 
        help="Path to the source document you want to convert."
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default=None,
        help="Optional destination path for the custom output package. Defaults to replacing extension with '.custom'."
    )
    
    args = parser.parse_args()
    input_path = Path(args.input_file)
    
    if not input_path.exists():
        print(f"Error: Target file not found at: '{input_path.absolute()}'")
        exit(1)
        
    # Resolve the destination file path
    output_path = Path(args.output) if args.output else input_path.with_suffix(".custom")
    
    convert_document_to_custom(input_path, output_path)
