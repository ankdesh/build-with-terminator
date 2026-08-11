"""Script to generate a synthetic sample architectural specification PDF for testing.

Creates a multi-section PDF document containing headings, narrative text,
diagrams/figures, and register map tables.
"""

import sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_sample_architecture_pdf(output_pdf_path: str = "sample_arch_spec.pdf") -> Path:
    """Generate a sample architectural PDF specification."""
    pdf_file = Path(output_pdf_path)
    doc = SimpleDocTemplate(
        str(pdf_file),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1A2B4C"),
        spaceAfter=15,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0D47A1"),
        spaceBefore=15,
        spaceAfter=10,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1565C0"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#212121"),
        spaceAfter=8,
    )

    elements = []

    # Title
    elements.append(Paragraph("System-on-Chip (SoC) Architectural Specification", title_style))
    elements.append(Paragraph("Document Version: 1.0.4 | Author: System Architecture Team", body_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A2B4C"), spaceAfter=15))

    # Section 1: Executive Overview
    elements.append(Paragraph("1. Executive System Overview & Bus Interconnect", h1_style))
    elements.append(
        Paragraph(
            "This specification defines the high-level hardware architecture for the multi-core SoC platform. "
            "The system integrates an ARM Cortex processor cluster, high-performance DMA controller, "
            "Vectored Interrupt Controller (VIC), and an AXI-to-APB peripheral bridge over an AXI4 system bus topology.",
            body_style,
        )
    )

    # Bus Diagram Drawing
    d = Drawing(450, 100)
    d.add(Rect(10, 30, 100, 40, fillColor=colors.HexColor("#BBDEFB"), strokeColor=colors.HexColor("#0D47A1")))
    d.add(String(25, 48, "CPU Cluster", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#0D47A1")))

    d.add(Rect(150, 30, 100, 40, fillColor=colors.HexColor("#C8E6C9"), strokeColor=colors.HexColor("#2E7D32")))
    d.add(String(165, 48, "DMA Controller", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#2E7D32")))

    d.add(Rect(290, 30, 100, 40, fillColor=colors.HexColor("#FFE0B2"), strokeColor=colors.HexColor("#E65100")))
    d.add(String(300, 48, "Interrupt Ctrl", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor("#E65100")))

    # Interconnect Bus line
    d.add(Line(10, 15, 390, 15, strokeColor=colors.HexColor("#37474F"), strokeWidth=3))
    d.add(String(160, 2, "AXI4 System Bus Interconnect", fontName="Helvetica-Oblique", fontSize=8, fillColor=colors.HexColor("#37474F")))

    elements.append(d)
    elements.append(Spacer(1, 15))

    # Section 2: DMA Controller
    elements.append(Paragraph("2. Direct Memory Access (DMA) Controller Subsystem", h1_style))
    elements.append(
        Paragraph(
            "The DMA controller manages high-throughput scatter-gather data transfers between system memory "
            "and peripheral devices without CPU intervention. It supports 8 concurrent DMA channels, configurable "
            "burst sizes, and priority arbitration.",
            body_style,
        )
    )

    elements.append(Paragraph("2.1 DMA Controller Register Map", h2_style))

    # DMA Register Table Data
    dma_table_data = [
        ["Register Name", "Offset", "Access", "Reset Value", "Description"],
        ["DMA_CTRL", "0x00", "R/W", "0x0000_0000", "Control Register (Bit 0: Enable, Bit 1: Interrupt Enable)"],
        ["DMA_STATUS", "0x04", "RO", "0x0000_0000", "Channel Status Flags (Transfer Complete, Error)"],
        ["DMA_SRC_ADDR", "0x08", "R/W", "0x0000_0000", "Source Base Memory Address"],
        ["DMA_DST_ADDR", "0x0C", "R/W", "0x0000_0000", "Destination Base Memory Address"],
        ["DMA_XFER_SIZE", "0x10", "R/W", "0x0000_0000", "Transfer Length in Bytes (Max 64KB)"],
    ]

    t_dma = Table(dma_table_data, colWidths=[100, 50, 50, 80, 200])
    t_dma.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565C0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F5F5F5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0BEC5")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    elements.append(t_dma)
    elements.append(Spacer(1, 15))

    # Section 3: Interrupt Controller
    elements.append(Paragraph("3. Vectored Interrupt Controller (VIC)", h1_style))
    elements.append(
        Paragraph(
            "The Vectored Interrupt Controller routes 32 hardware interrupt lines to the CPU core. "
            "It features programmable interrupt priority levels (0-15) and fast hardware interrupt vector lookup.",
            body_style,
        )
    )

    elements.append(Paragraph("3.1 VIC Register Map", h2_style))

    vic_table_data = [
        ["Register Name", "Offset", "Access", "Reset Value", "Description"],
        ["VIC_IRQ_STATUS", "0x00", "RO", "0x0000_0000", "Active Raw Interrupt Status"],
        ["VIC_INT_ENABLE", "0x04", "R/W", "0x0000_0000", "Interrupt Enable Mask"],
        ["VIC_VEC_ADDR", "0x08", "RO", "0x0000_0000", "Vector Address of Active Highest Priority IRQ"],
    ]

    t_vic = Table(vic_table_data, colWidths=[100, 50, 50, 80, 200])
    t_vic.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F1F8E9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C8E6C9")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    elements.append(t_vic)

    doc.build(elements)
    print(f"Generated test architectural specification PDF: {pdf_file.resolve()}")
    return pdf_file


if __name__ == "__main__":
    out_pdf = sys.argv[1] if len(sys.argv) > 1 else "sample_arch_spec.pdf"
    generate_sample_architecture_pdf(out_pdf)
