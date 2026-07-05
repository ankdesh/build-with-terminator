import os
import logging
import io
from typing import List, Dict, Optional
from fpdf import FPDF
from PIL import Image

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Compiles captured slides and their corresponding notes/transcripts into a PDF."""

    def _sanitize_text(self, text: str) -> str:
        """Sanitizes unicode characters to prevent encoding errors in PDF generation."""
        replacements = {
            "\u2022": "-",    # Bullet point
            "\u2013": "-",    # En dash
            "\u2014": "-",    # Em dash
            "\u201c": '"',    # Left double quote
            "\u201d": '"',    # Right double quote
            "\u2018": "'",    # Left single quote
            "\u2019": "'",    # Right single quote
            "\u2026": "...",  # Ellipsis
            "\u00a0": " ",    # Non-breaking space
        }
        for uni_char, ascii_char in replacements.items():
            text = text.replace(uni_char, ascii_char)
            
        # Encode to latin-1, ignoring any characters that cannot be represented
        return text.encode("latin-1", errors="ignore").decode("latin-1")

    def generate_pdf(self, slides: List[Dict[str, str]], output_pdf_path: str, image_quality: Optional[int] = None) -> None:
        """Generates a PDF where each page contains a slide image and its corresponding notes.

        Args:
            slides: A list of dictionaries, each containing:
                    - 'image_path': Path to the slide image.
                    - 'notes': The text notes/transcript for the slide.
            output_pdf_path: Path where the output PDF will be saved.
            image_quality: Optional JPEG compression quality (1-100). If None, embeds original images.
        """
        logger.info(f"Generating PDF: {output_pdf_path} (image quality: {image_quality})...")
        
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_margins(left=10, top=10, right=10)
        pdf.set_auto_page_break(auto=True, margin=15)

        for i, slide in enumerate(slides, start=1):
            image_path = slide["image_path"]
            notes_text = slide["notes"]

            # Add a new page for each slide
            pdf.add_page()
            
            # 1. Slide Title
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(w=0, h=10, text=f"Slide {i}", new_x="LMARGIN", new_y="NEXT", align="L")
            pdf.ln(2)

            # 2. Slide Image
            if os.path.exists(image_path):
                # Page width is 210mm. Margins are 10mm left/right. Printable width is 190mm.
                # Place image at x=10, y=22, width=190. Height will be auto-calculated to maintain aspect ratio.
                try:
                    if image_quality is not None:
                        # Open, convert to RGB, and compress as JPEG in memory
                        with Image.open(image_path) as img:
                            if img.mode != "RGB":
                                img = img.convert("RGB")
                            img_buffer = io.BytesIO()
                            img.save(img_buffer, format="JPEG", quality=image_quality, optimize=True)
                            img_buffer.seek(0)
                            pdf.image(img_buffer, x=10, y=22, w=190)
                    else:
                        pdf.image(image_path, x=10, y=22, w=190)
                    # A 16:9 image of width 190mm has a height of ~107mm.
                    # We add some spacing below the image.
                    pdf.ln(112)
                except Exception as e:
                    logger.error(f"Failed to insert image {image_path} into PDF: {e}")
                    pdf.set_font("Helvetica", "I", 10)
                    pdf.cell(w=0, h=10, text="[Error loading slide image]", new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(5)
            else:
                logger.warning(f"Slide image not found: {image_path}")
                pdf.set_font("Helvetica", "I", 10)
                pdf.cell(w=0, h=10, text="[Slide image not found]", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(5)

            # 3. Notes Heading
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(w=0, h=8, text="Notes:", new_x="LMARGIN", new_y="NEXT", align="L")
            pdf.ln(1)

            # 4. Notes Content
            pdf.set_font("Helvetica", "", 10)
            
            sanitized_notes = self._sanitize_text(notes_text)
            if not sanitized_notes.strip():
                sanitized_notes = "No notes or transcript available for this slide."

            # Write the notes using multi_cell for automatic word-wrapping
            pdf.multi_cell(w=0, h=5, text=sanitized_notes)

        try:
            pdf.output(output_pdf_path)
            logger.info(f"Successfully generated PDF at {output_pdf_path}")
        except Exception as e:
            logger.error(f"Failed to write PDF to {output_pdf_path}: {e}")
            raise RuntimeError(f"Failed to generate PDF: {e}") from e
