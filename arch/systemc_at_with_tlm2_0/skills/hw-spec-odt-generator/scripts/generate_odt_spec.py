#!/usr/bin/env python3
"""
generate_odt_spec.py
Programmatically constructs professional OpenDocument Text (.odt) Hardware Specification
Documents for all 4 performance modeling examples (Examples 0, 1, 2, and 3) using odfpy.
"""

import os
import sys
from odf.opendocument import OpenDocumentText
from odf.style import (Style, TextProperties, ParagraphProperties, TableProperties,
                       TableColumnProperties, TableCellProperties, GraphicProperties)
from odf.text import H, P, Span
from odf.table import Table, TableColumn, TableRow, TableCell
from odf.draw import Frame, Image

DIAGRAM_DIR = "generated_diagrams"

def build_generic_odt_spec(output_filename, doc_title, doc_subtitle, callout_text,
                           sections_data):
    """
    Helper function to generate a styled .odt hardware specification document.
    """
    doc = OpenDocumentText()

    # Define Styles
    style_title = Style(name="SpecTitle", family="paragraph")
    style_title.addElement(ParagraphProperties(margintop="0.2in", marginbottom="0.1in", textalign="center"))
    style_title.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="22pt", fontweight="bold", color="#0F172A"))
    doc.styles.addElement(style_title)

    style_subtitle = Style(name="SpecSubtitle", family="paragraph")
    style_subtitle.addElement(ParagraphProperties(margintop="0.0in", marginbottom="0.3in", textalign="center"))
    style_subtitle.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="11pt", fontstyle="italic", color="#475569"))
    doc.styles.addElement(style_subtitle)

    style_h1 = Style(name="Heading1_Custom", family="paragraph")
    style_h1.addElement(ParagraphProperties(margintop="0.3in", marginbottom="0.1in", keepwithnext="always"))
    style_h1.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="15pt", fontweight="bold", color="#1E293B"))
    doc.styles.addElement(style_h1)

    style_h2 = Style(name="Heading2_Custom", family="paragraph")
    style_h2.addElement(ParagraphProperties(margintop="0.2in", marginbottom="0.08in", keepwithnext="always"))
    style_h2.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="12pt", fontweight="bold", color="#0369A1"))
    doc.styles.addElement(style_h2)

    style_body = Style(name="BodyText_Custom", family="paragraph")
    style_body.addElement(ParagraphProperties(margintop="0.05in", marginbottom="0.08in", lineheight="120%"))
    style_body.addElement(TextProperties(fontfamily="DejaVu Serif", fontsize="10.5pt", color="#1E293B"))
    doc.styles.addElement(style_body)

    style_callout = Style(name="CalloutBox", family="paragraph")
    style_callout.addElement(ParagraphProperties(margintop="0.1in", marginbottom="0.1in", backgroundcolor="#F0F9FF",
                                                 padding="0.1in", borderleft="0.05in solid #0284C7"))
    style_callout.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="9.5pt", color="#0369A1"))
    doc.styles.addElement(style_callout)

    style_th = Style(name="TableHeader", family="table-cell")
    style_th.addElement(TableCellProperties(backgroundcolor="#1E293B", padding="0.08in", border="0.5pt solid #475569"))
    doc.styles.addElement(style_th)

    style_th_text = Style(name="TableHeaderText", family="paragraph")
    style_th_text.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="9.5pt", fontweight="bold", color="#FFFFFF"))
    doc.styles.addElement(style_th_text)

    style_td = Style(name="TableCell", family="table-cell")
    style_td.addElement(TableCellProperties(backgroundcolor="#FFFFFF", padding="0.06in", border="0.5pt solid #CBD5E1"))
    doc.styles.addElement(style_td)

    style_td_alt = Style(name="TableCellAlt", family="table-cell")
    style_td_alt.addElement(TableCellProperties(backgroundcolor="#F8FAFC", padding="0.06in", border="0.5pt solid #CBD5E1"))
    doc.styles.addElement(style_td_alt)

    style_td_text = Style(name="TableCellText", family="paragraph")
    style_td_text.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="9pt", color="#0F172A"))
    doc.styles.addElement(style_td_text)

    style_caption = Style(name="ImageCaption", family="paragraph")
    style_caption.addElement(ParagraphProperties(margintop="0.05in", marginbottom="0.2in", textalign="center"))
    style_caption.addElement(TextProperties(fontfamily="DejaVu Sans", fontsize="9pt", fontstyle="italic", color="#475569"))
    doc.styles.addElement(style_caption)

    # Title & Header
    doc.text.addElement(P(stylename=style_title, text=doc_title))
    doc.text.addElement(P(stylename=style_subtitle, text=doc_subtitle))
    doc.text.addElement(P(stylename=style_callout, text=f"HARDWARE SPEC NOTE: {callout_text}"))

    def add_image(image_path, caption, width="6.0in", height="3.5in"):
        if not os.path.exists(image_path):
            print(f"Warning: Image {image_path} not found. Skipping image embed.")
            return
        href = doc.addPicture(image_path)
        p = P(stylename=style_caption)
        frame = Frame(width=width, height=height)
        frame.addElement(Image(href=href))
        p.addElement(frame)
        doc.text.addElement(p)
        doc.text.addElement(P(stylename=style_caption, text=caption))

    def create_table(headers, rows):
        tbl = Table()
        for _ in headers:
            tbl.addElement(TableColumn())
        header_tr = TableRow()
        for h in headers:
            tc = TableCell(stylename=style_th)
            tc.addElement(P(stylename=style_th_text, text=h))
            header_tr.addElement(tc)
        tbl.addElement(header_tr)

        for idx, row in enumerate(rows):
            tr = TableRow()
            c_style = style_td_alt if idx % 2 == 1 else style_td
            for val in row:
                tc = TableCell(stylename=c_style)
                tc.addElement(P(stylename=style_td_text, text=str(val)))
                tr.addElement(tc)
            tbl.addElement(tr)

        doc.text.addElement(tbl)
        doc.text.addElement(P(stylename=style_body, text=""))

    # Render sections
    for sec in sections_data:
        if sec["type"] == "h1":
            doc.text.addElement(H(outlinelevel=1, stylename=style_h1, text=sec["text"]))
        elif sec["type"] == "h2":
            doc.text.addElement(H(outlinelevel=2, stylename=style_h2, text=sec["text"]))
        elif sec["type"] == "p":
            doc.text.addElement(P(stylename=style_body, text=sec["text"]))
        elif sec["type"] == "callout":
            doc.text.addElement(P(stylename=style_callout, text=f"NOTE: {sec['text']}"))
        elif sec["type"] == "image":
            add_image(sec["path"], sec["caption"], sec.get("width", "6.0in"), sec.get("height", "3.5in"))
        elif sec["type"] == "table":
            create_table(sec["headers"], sec["rows"])

    doc.save(output_filename)
    print(f"Successfully generated ODT Specification: {output_filename}")


# =============================================================================
# BUILDER FOR EXAMPLE 0: SIMPLE PIPELINE STAGE
# =============================================================================
def build_ex0_spec():
    sections = [
        {"type": "h1", "text": "1. Executive Summary & Hardware Microarchitecture"},
        {"type": "p", "text": "This document describes a 3-stage hardware compute pipeline consisting of three connected functional blocks: Component A (Initiator Core), Component B (3-Cycle Pipelined Compute Stage), and Component C (1-Cycle Endpoint Compute Unit)."},
        {"type": "p", "text": "The pipeline decouples input handshaking from compute latency using 1-cycle register setup delays, allowing continuous throughput across all three stages."},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex0_architecture_block_diagram.png"), "caption": "Figure 1: 3-Stage Pipeline Hardware Microarchitecture Block Diagram", "width": "6.2in", "height": "3.5in"},
        {"type": "h2", "text": "1.1 Sub-Block Specifications"},
        {"type": "p", "text": "1. Component A (Initiator): Master core generating instruction transactions and driving output data payload."},
        {"type": "p", "text": "2. Component B (Pipelined Stage): Accepts requests with a 1-cycle A_to_B_ready acknowledgment, processes transactions through a 3-cycle internal compute pipeline, and forwards completed payloads to Component C."},
        {"type": "p", "text": "3. Component C (Target Endpoint): Accepts requests with a 1-cycle B_to_C_ready acknowledgment, executes a 1-cycle doubling calculation, and commits final data."},

        {"type": "h1", "text": "2. Hardware Interface Signal Specifications"},
        {"type": "h2", "text": "2.1 Primary Input/Output Signals"},
        {"type": "table", "headers": ["Signal Name", "Direction", "Width", "Description"], "rows": [
            ["clk", "Input", "1 bit", "Master clock (100 MHz, 10 ns period)"],
            ["rst_n", "Input", "1 bit", "Active-low system reset"],
            ["A_to_B_valid", "Internal", "1 bit", "High when Component A drives valid data to B"],
            ["A_to_B_ready", "Internal", "1 bit", "High for 1 cycle when B accepts A's request"],
            ["B_to_C_valid", "Internal", "1 bit", "High when B forwards completed data to C"],
            ["B_to_C_ready", "Internal", "1 bit", "High for 1 cycle when C accepts B's request"],
            ["tx_data", "Internal", "32 bits", "32-bit transaction payload data"]
        ]},
        {"type": "h2", "text": "2.2 Performance Tracing Register Map"},
        {"type": "table", "headers": ["Signal Name", "Type", "Range", "Description"], "rows": [
            ["pipeline_depth", "Output", "0 to 3 items", "Count of active transactions inside B's pipeline"],
            ["A_B_req_tx", "Output", "0 to 255 ID", "Transaction ID currently active on A-B interface"],
            ["B_C_req_tx", "Output", "0 to 255 ID", "Transaction ID currently active on B-C interface"]
        ]},

        {"type": "h1", "text": "3. Timing & Control State Specifications"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex0_sequence_diagram.png"), "caption": "Figure 2: Pipeline Stage A -> B -> C Sequence Flow", "width": "6.0in", "height": "3.5in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex0_pipeline_states.png"), "caption": "Figure 3: 3-Stage Pipeline Control State Machine", "width": "6.2in", "height": "2.6in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex0_timing_diagram.png"), "caption": "Figure 4: Cycle-Accurate Pipeline Timing Waveforms (Scenario 1)", "width": "6.2in", "height": "3.8in"},

        {"type": "h1", "text": "4. SystemC TLM 2.0 Performance Model Implementation Guide"},
        {"type": "table", "headers": ["Hardware Spec Feature", "SystemC TLM 2.0 AT Implementation Pattern"], "rows": [
            ["A-B & B-C Valid/Ready Handshakes", "Use 2-Phase protocol: nb_transport_fw(BEGIN_REQ) returning TLM_UPDATED(END_REQ, delay=10ns)."],
            ["Component B Execution (3 cy)", "Register payload with PEQ: m_peq.notify(trans, delay + 30ns). Pop payload on expiration and forward to C."],
            ["Component C Endpoint Execution (1 cy)", "Register payload with PEQ: m_peq.notify(trans, delay + 10ns). Double data value on expiration."],
            ["Tracing Signals", "Instantiate sc_signal<int> sig_pipeline_depth, sig_A_B_req_tx, sig_B_C_req_tx and update on event triggers."]
        ]},
        {"type": "callout", "text": "A SystemC performance modeling engineer reading Section 4 will build an Approximately-Timed model identical to example0_simple in this repository!"},

        {"type": "h1", "text": "5. Verification Scenarios"},
        {"type": "table", "headers": ["Scenario", "Traffic Pattern", "Observed Behavior", "Expected Retirement Cycles"], "rows": [
            ["Scenario 1", "Single Request at cy 1", "Single transaction propagates through B and C", "A sends cy 1, B accepts cy 2, B forwards cy 4, C retires cy 6"],
            ["Scenario 2", "5 Back-to-Back Requests", "Pipeline holds multiple items in flight", "Transactions retire consecutively at cy 6, 7, 8, 9, 10"],
            ["Scenario 3", "Alternate Cycle Requests", "Dynamic pipeline filling and draining", "Transactions retire at cy 6, 8, 10"]
        ]}
    ]

    build_generic_odt_spec(
        "simple_pipeline_hw_spec.odt",
        "Simple 3-Stage Pipeline Hardware Specification",
        "Hardware Microarchitecture Specification & SystemC TLM AT Performance Modeling Guide • Rev 2.0",
        "This specification details a 3-stage hardware compute pipeline (Component A -> Stage B -> Endpoint C) and provides SystemC TLM 2.0 2-Phase AT performance modeling instructions.",
        sections
    )


# =============================================================================
# BUILDER FOR EXAMPLE 1: PIPELINED ALU
# =============================================================================
def build_ex1_spec():
    sections = [
        {"type": "h1", "text": "1. Executive Summary & Hardware Microarchitecture"},
        {"type": "p", "text": "The Pipelined ALU is a high-performance 32-bit arithmetic compute block designed for integration into superscalar processor cores. The core supports parallel execution of 32-bit Addition (3 clock cycles execution latency) and 32-bit Multiplication (4 clock cycles execution latency)."},
        {"type": "p", "text": "The input interface uses a decoupled Valid/Ready handshake protocol with a 1-cycle input register setup delay. Output results are committed in strict program issue order via an internal Reorder Buffer (ROB)."},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "alu_architecture_block_diagram.png"), "caption": "Figure 1: Pipelined ALU Microarchitectural Block Diagram", "width": "6.2in", "height": "3.7in"},
        {"type": "h2", "text": "1.1 Sub-Block Microarchitecture"},
        {"type": "p", "text": "1. Initiator Core (Master): Generates instruction requests, driving valid signals, operation codes (0 = ADD, 1 = MUL), and 32-bit operands (A, B)."},
        {"type": "p", "text": "2. Input Register Stage: Samples incoming requests when req_valid is high. Asserts req_ready 1 clock cycle later to acknowledge request receipt, freeing the initiator interface."},
        {"type": "p", "text": "3. Execution Pipelines: Parallel processing pipelines: 3-cycle pipelined Adder Unit and 4-cycle pipelined Multiplier Unit."},
        {"type": "p", "text": "4. Reorder Buffer (ROB) & Retirement Queue: A multi-entry FIFO buffer that tracks issue order. Out-of-order completed results are held in ROB slots until all preceding in-flight operations have retired."},

        {"type": "h1", "text": "2. Hardware Interface Signal Specifications"},
        {"type": "h2", "text": "2.1 Primary Input/Output Signals"},
        {"type": "table", "headers": ["Signal Name", "Direction", "Width", "Description"], "rows": [
            ["clk", "Input", "1 bit", "System master clock (100 MHz, 10 ns period)"],
            ["rst_n", "Input", "1 bit", "Asynchronous active-low system reset"],
            ["req_valid", "Input", "1 bit", "Initiator asserts high when driving valid command and operands"],
            ["req_ready", "Output", "1 bit", "ALU asserts high for 1 cycle when input stage accepts request"],
            ["op_code", "Input", "1 bit", "0 = 32-bit Addition (ADD), 1 = 32-bit Multiplication (MUL)"],
            ["operand_a", "Input", "32 bits", "First 32-bit input operand"],
            ["operand_b", "Input", "32 bits", "Second 32-bit input operand"],
            ["out_valid", "Output", "1 bit", "ALU asserts high when retired result is valid"],
            ["result_data", "Output", "32 bits", "32-bit computation result output"]
        ]},
        {"type": "h2", "text": "2.2 Performance Monitor & Tracing Register Map"},
        {"type": "table", "headers": ["Signal Name", "Type", "Range", "Description"], "rows": [
            ["input_stage_occupied", "Output", "0 (Idle), 1 (Occupied)", "Active high during 1-cycle input register setup"],
            ["pipeline_depth", "Output", "0 to 8 operations", "Current count of active in-flight operations"],
            ["active_op", "Output", "00:IDLE, 01:ADD, 10:MUL, 11:MIXED", "Current execution pipeline activity state"],
            ["retired_tx_id", "Output", "0 (None), 1-255 (Tx ID)", "ID of transaction retired in current clock cycle"]
        ]},

        {"type": "h1", "text": "3. Timing & Control State Specifications"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "alu_sequence_diagram.png"), "caption": "Figure 2: Hardware Valid/Ready Handshake & Pipeline Execution Flow", "width": "6.0in", "height": "3.8in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "alu_pipeline_states.png"), "caption": "Figure 3: Hardware Pipeline Control State Machine", "width": "6.2in", "height": "2.8in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "alu_timing_diagram.png"), "caption": "Figure 4: Cycle-Accurate Digital Waveforms (Scenario 1)", "width": "6.3in", "height": "4.0in"},

        {"type": "h1", "text": "4. SystemC TLM 2.0 Performance Model Implementation Guide"},
        {"type": "table", "headers": ["Hardware Spec Feature", "SystemC TLM 2.0 AT Implementation Pattern"], "rows": [
            ["Valid/Ready Handshake (req_valid / req_ready)", "Use 2-Phase protocol: Initiator sends nb_transport_fw(BEGIN_REQ). Target responds after 1 cycle with TLM_UPDATED(END_REQ, delay=10ns)."],
            ["Execution Pipeline Delays (3cy ADD, 4cy MUL)", "Use Payload Event Queue (tlm_utils::peq_with_get). Target notifies PEQ: m_peq.notify(trans, delay + 30ns or 40ns)."],
            ["Out-of-Order Execution vs In-Order Retire", "PEQ worker thread retrieves finished payloads out-of-order, setting completed=true. Main pipeline_thread monitors head of m_pipeline_queue to retire in-order."]
        ]},
        {"type": "callout", "text": "A SystemC performance modeling engineer reading Section 4 will build a 2-Phase Approximately-Timed model that behaves identically to example1_pipeline in this repository!"},

        {"type": "h1", "text": "5. Verification Scenarios"},
        {"type": "table", "headers": ["Scenario", "Traffic Pattern", "Observed Behavior", "Expected Retirement Cycles"], "rows": [
            ["Scenario 1", "Mixed (ADD, MUL, ADD)", "Continuous execution with out-of-order completion", "Tx 0 (ADD) retires at cy 4; Tx 1 (MUL) & Tx 2 (ADD) retire at cy 6"],
            ["Scenario 2", "Slow MUL followed by Fast ADDs", "In-order retirement stall in ROB", "Fast ADDs complete at cy 4 but stall in ROB until cy 6 to retire behind MUL"],
            ["Scenario 3", "Continuous Back-to-Back ADDs", "100% compute pipeline saturation", "Pipeline depth stays at 3 in-flight items; 1 operation retires every cycle"]
        ]}
    ]

    build_generic_odt_spec(
        "pipelined_alu_hw_spec.odt",
        "Pipelined ALU Hardware Architecture Specification",
        "Hardware Microarchitecture Specification & SystemC TLM AT Performance Modeling Guide • Rev 2.0",
        "This document provides the formal hardware microarchitecture specification for a Pipelined Arithmetic Logic Unit (ALU) and provides SystemC TLM 2.0 2-Phase AT performance modeling instructions.",
        sections
    )


# =============================================================================
# BUILDER FOR EXAMPLE 2: FIFO BACKPRESSURE STREAMING
# =============================================================================
def build_ex2_spec():
    sections = [
        {"type": "h1", "text": "1. Executive Summary & Hardware Microarchitecture"},
        {"type": "p", "text": "This document specifies a streaming data interconnect featuring flow control backpressure: Producer Core -> 4-Entry Streaming FIFO Interconnect -> Consumer Core."},
        {"type": "p", "text": "The FIFO interconnect buffers bursty stream traffic. When the FIFO queue depth reaches 4 (full), the FIFO deasserts p2f_ready, backpressuring the Producer. When the Consumer is busy processing, it deasserts f2c_ready, stalling the FIFO."},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex2_architecture_block_diagram.png"), "caption": "Figure 1: Streaming FIFO Interconnect Hardware Microarchitecture Diagram", "width": "6.2in", "height": "3.5in"},

        {"type": "h1", "text": "2. Hardware Interface Signal Specifications"},
        {"type": "table", "headers": ["Signal Name", "Direction", "Width", "Description"], "rows": [
            ["clk", "Input", "1 bit", "Master clock (100 MHz, 10 ns period)"],
            ["rst_n", "Input", "1 bit", "Active-low system reset"],
            ["p2f_valid", "Input", "1 bit", "Producer asserts high when driving stream data"],
            ["p2f_ready", "Output", "1 bit", "FIFO asserts high when buffer space is available; deasserts Low on FULL"],
            ["f2c_valid", "Output", "1 bit", "FIFO asserts high when popped data is forwarded to Consumer"],
            ["f2c_ready", "Input", "1 bit", "Consumer asserts high when ready; deasserts Low when BUSY"],
            ["stream_data", "Input/Output", "32 bits", "32-bit streaming data packet payload"]
        ]},
        {"type": "h2", "text": "2.2 Performance Tracing Register Map"},
        {"type": "table", "headers": ["Signal Name", "Type", "Range", "Description"], "rows": [
            ["fifo_size", "Output", "0 to 4 items", "Current count of data packets buffered in FIFO storage queue"],
            ["producer_stalled", "Output", "1 bit (Bool)", "Active High when Producer is backpressured by full FIFO"],
            ["consumer_stalled", "Output", "1 bit (Bool)", "Active High when FIFO is stalled by busy Consumer"]
        ]},

        {"type": "h1", "text": "3. Timing & Control State Specifications"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex2_sequence_diagram.png"), "caption": "Figure 2: Backpressure Streaming Flow Control Sequence", "width": "6.0in", "height": "3.5in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex2_pipeline_states.png"), "caption": "Figure 3: Streaming FIFO Flow Control State Machine", "width": "6.2in", "height": "2.6in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex2_timing_diagram.png"), "caption": "Figure 4: Cycle-Accurate Backpressure Streaming Waveforms (Scenario 1)", "width": "6.2in", "height": "4.0in"},

        {"type": "h1", "text": "4. SystemC TLM 2.0 Performance Model Implementation Guide"},
        {"type": "table", "headers": ["Hardware Spec Feature", "SystemC TLM 2.0 AT Implementation Pattern"], "rows": [
            ["Producer Stall on FIFO Full (p2f_ready Low)", "In nb_transport_fw_write: If fifo_size == 4, return TLM_ACCEPTED without END_REQ phase. Stash trans in m_pending_writes. Producer thread blocks on wait(m_end_req_event)."],
            ["FIFO Stall Release Backward", "When Consumer drains a packet, pop pending write from m_pending_writes and call socket->nb_transport_bw(*trans, phase=END_REQ, delay=10ns) backward."],
            ["Consumer Busy Stall (f2c_ready Low)", "In Consumer nb_transport_fw: If busy, return TLM_ACCEPTED without END_REQ. FIFO push_to_consumer_thread blocks on wait(m_consumer_released_event)."],
            ["FIFO Write Buffer Execution Delay (2 cy)", "Register accepted write with PEQ: m_peq.notify(trans, delay + 20ns). Push to m_fifo_data queue on expiration."]
        ]},
        {"type": "callout", "text": "A SystemC performance modeling engineer reading Section 4 will build an Approximately-Timed streaming model identical to example2_backpressure in this repository!"},

        {"type": "h1", "text": "5. Verification Scenarios"},
        {"type": "table", "headers": ["Scenario", "Traffic Pattern", "Observed Behavior", "Expected Verification Results"], "rows": [
            ["Scenario 1", "Fast Producer (1 cy), Slow Consumer (starts cy 10)", "FIFO fills to capacity=4 at cy 5. Producer stalls cy 5-10. Drains when Consumer starts.", "Producer stalls on write 5. Releases at cy 10 as Consumer processes."],
            ["Scenario 2", "Slow Producer (6 cy), Fast Consumer", "FIFO stays mostly empty. No backpressure stalls.", "Smooth continuous streaming without producer stalls."],
            ["Scenario 3", "Bursty Producer & Bursty Consumer", "Transient queue buildup with temporary stalls", "FIFO absorbs burst, temporary backpressure pulse released as consumer drains."]
        ]}
    ]

    build_generic_odt_spec(
        "fifo_backpressure_hw_spec.odt",
        "Interblock Streaming FIFO with Backpressure Hardware Specification",
        "Hardware Microarchitecture Specification & SystemC TLM AT Performance Modeling Guide • Rev 2.0",
        "This specification details a streaming FIFO interconnect with valid/ready backpressure flow control and provides SystemC TLM 2.0 2-Phase AT performance modeling instructions.",
        sections
    )


# =============================================================================
# BUILDER FOR EXAMPLE 3: SHARED SWITCH ARBITRATION
# =============================================================================
def build_ex3_spec():
    sections = [
        {"type": "h1", "text": "1. Executive Summary & Hardware Microarchitecture"},
        {"type": "p", "text": "This document specifies a Shared Crossbar Switch interconnect connecting 4 Initiator Cores (Core 0..3) to 4 Target Memory Nodes (Node 0..3)."},
        {"type": "p", "text": "When multiple cores issue simultaneous write requests, a Round-Robin arbiter selects a winning core, grants access, and locks the switch for 3 clock cycles (30 ns transmission duration). Other contending cores are held in a pending request queue and granted sequentially every 3 cycles."},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex3_architecture_block_diagram.png"), "caption": "Figure 1: Shared Switch Crossbar Interconnect Microarchitecture Diagram", "width": "6.2in", "height": "3.6in"},

        {"type": "h1", "text": "2. Hardware Interface Signal Specifications"},
        {"type": "table", "headers": ["Signal Name", "Direction", "Width", "Description"], "rows": [
            ["clk", "Input", "1 bit", "Master clock (100 MHz, 10 ns period)"],
            ["rst_n", "Input", "1 bit", "Active-low system reset"],
            ["req_valid[3:0]", "Input Vector", "4 bits", "1 valid request bit per Initiator Core (0 to 3)"],
            ["req_grant[3:0]", "Output Vector", "4 bits", "1-cycle grant pulse returned to winning Core"],
            ["dest_addr", "Input Bus", "4 bits", "Destination Target Node index (0 to 3)"],
            ["write_data", "Input Bus", "32 bits", "32-bit transaction payload data"]
        ]},
        {"type": "h2", "text": "2.2 Performance Tracing Register Map"},
        {"type": "table", "headers": ["Signal Name", "Type", "Range", "Description"], "rows": [
            ["switch_busy", "Output", "1 bit (Bool)", "Active High while switch is locked transmitting (3 cycles)"],
            ["switch_rr_index", "Output", "0 to 3 ID", "Current Round-Robin arbiter pointer index"],
            ["active_initiator_id", "Output", "0 (None), 1-4 (Core ID)", "ID of currently granted initiator core"],
            ["pending_req_count", "Output", "0 to 4 cores", "Number of contending cores currently queued and stalled"]
        ]},

        {"type": "h1", "text": "3. Timing & Control State Specifications"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex3_sequence_diagram.png"), "caption": "Figure 2: Round-Robin Switch Contention Sequence Flow", "width": "6.0in", "height": "3.5in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex3_pipeline_states.png"), "caption": "Figure 3: Shared Switch Arbitration Control State Machine", "width": "6.2in", "height": "2.6in"},
        {"type": "image", "path": os.path.join(DIAGRAM_DIR, "ex3_timing_diagram.png"), "caption": "Figure 4: Cycle-Accurate Switch Arbitration Waveforms (Scenario 1)", "width": "6.2in", "height": "4.0in"},

        {"type": "h1", "text": "4. SystemC TLM 2.0 Performance Model Implementation Guide"},
        {"type": "table", "headers": ["Hardware Spec Feature", "SystemC TLM 2.0 AT Implementation Pattern"], "rows": [
            ["Multi-Core Socket Binding", "Use tlm_utils::multi_passthrough_target_socket<SwitchTarget> for inputs and multi_passthrough_initiator_socket for outputs."],
            ["Contention Stalling", "In nb_transport_fw(id, trans, phase, delay): Push request to m_pending_requests and return TLM_ACCEPTED without END_REQ. Initiator thread stalls on wait(m_end_req_event)."],
            ["Round-Robin Arbiter Thread", "arbiter_thread loops on m_pending_requests. Selects winner using m_rr_index pointer, sends backward nb_transport_bw(END_REQ, delay=10ns) grant pulse to winner."],
            ["Switch Transmission Lock (3 cy)", "Register busy transmission with PEQ: m_peq.notify(trans, 30ns). busy_release_thread unlocks switch when PEQ expires, triggering arbiter for remaining queued cores."]
        ]},
        {"type": "callout", "text": "A SystemC performance modeling engineer reading Section 4 will build an Approximately-Timed arbitration model identical to example3_arbitration in this repository!"},

        {"type": "h1", "text": "5. Verification Scenarios"},
        {"type": "table", "headers": ["Scenario", "Traffic Pattern", "Observed Behavior", "Expected Grant Cycles"], "rows": [
            ["Scenario 1", "Coordinated Contention (Cores 0,1,2,3 request at cy 1)", "All 4 cores contend simultaneously. Round-Robin arbiter serializes grants.", "Core 0 granted cy 1; Core 1 granted cy 4; Core 2 granted cy 7; Core 3 granted cy 10."],
            ["Scenario 2", "Staggered Requests (requests spaced 4 cycles apart)", "No contention. Switch is free for every incoming request.", "Every core receives immediate grant at its request cycle without arbitration delay."],
            ["Scenario 3", "Unbalanced Traffic (Core 0 floods, others sparse)", "Core 0 requests repeatedly; arbiter fairly yields to sparse requests from Cores 1,2,3.", "Fair Round-Robin bandwidth distribution prevents starvation."]
        ]}
    ]

    build_generic_odt_spec(
        "switch_arbitration_hw_spec.odt",
        "Shared Switch Crossbar Interconnect Hardware Specification",
        "Hardware Microarchitecture Specification & SystemC TLM AT Performance Modeling Guide • Rev 2.0",
        "This specification details a 4-by-4 shared crossbar switch interconnect with Round-Robin arbitration and provides SystemC TLM 2.0 2-Phase AT performance modeling instructions.",
        sections
    )


# Run all builders
if __name__ == "__main__":
    build_ex0_spec() # Example 0
    build_ex1_spec() # Example 1
    build_ex2_spec() # Example 2
    build_ex3_spec() # Example 3
    print("All 4 Hardware Specification ODT documents built successfully!")
