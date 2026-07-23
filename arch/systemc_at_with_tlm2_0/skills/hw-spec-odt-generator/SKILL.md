---
name: hw-spec-odt-generator
description: Automate the generation of structured, professional OpenDocument Text (.odt) Hardware Architecture Specification Documents for SystemC TLM performance models, complete with RTL microarchitecture diagrams, valid/ready hardware waveforms, sequence flowcharts, formatted signal maps, and SystemC AT modeling guides.
---

# HW Spec ODT Generator Skill

This skill provides an automated, repeatable workflow and Python toolkit for generating rich OpenDocument Text (`.odt`) Hardware Specification Documents from SystemC performance models or textual specs.

---

## Hardware-First Design Principles

1. **RTL Hardware Perspective**:
   - The specification document describes **actual hardware microarchitecture**, signals (`clk`, `rst_n`, `req_valid`, `req_ready`, `op_code`, `operands`, `out_valid`, `result_data`), pipelines, and Reorder Buffers (ROB).
   - It does not frame the system as "this is C++ SystemC code", but rather as a **formal RTL Hardware Specification**.

2. **SystemC TLM Performance Model Mapping**:
   - Includes a dedicated section explaining how a SystemC developer should map the hardware spec (valid/ready handshakes, pipeline execution latencies, ROB arrival order) into a **2-Phase Approximately-Timed (AT) TLM 2.0 performance model** using PEQs (`peq_with_get`) and `sc_signal` trace drivers.
   - **Golden Rule**: A SystemC performance modeling engineer reading this document will design a SystemC model identical to `example1_pipeline`.

3. **No Added Functionality or Ports**:
   - Strictly preserves the interface boundaries and timing rules of the performance model without adding extra ports or features.

---

## Tools and Prerequisites

### Required Python Libraries (Installed in `.venv`)
- **`odfpy`**: Low-level OpenDocument XML builder library for creating `.odt` files with custom styles, tables, callout blocks, and picture frames.
- **`matplotlib`**: Rendering engine used to produce high-resolution (300 DPI) hardware diagrams.
- **`Pillow` (PIL)**: Image processing support for embedding PNG graphics into OpenDocument containers.
- **`numpy`**: Signal step function and digital waveform generator.

---

## Skill Toolkit

```text
skills/hw-spec-odt-generator/
├── SKILL.md                          # Skill manual and usage instructions (this file)
└── scripts/
    ├── diagram_generator.py           # Render 4 high-res hardware specification PNGs
    └── generate_odt_spec.py           # ODT builder script using odfpy
```

---

## Step-by-Step Workflow Instructions

### Step 1: Render Hardware Diagrams (`diagram_generator.py`)
Run `diagram_generator.py` to generate the 4 standard hardware specification diagrams in `generated_diagrams/`:

```bash
.venv/bin/python skills/hw-spec-odt-generator/scripts/diagram_generator.py
```

#### Generated Diagrams:
1. **Hardware Microarchitecture Block Diagram (`alu_architecture_block_diagram.png`)**:
   - Master Initiator Core, Interface Channels (`valid`/`ready`), Input Register Stage, Dispatch Unit, 3-cycle Adder Unit, 4-cycle Multiplier Unit, and In-Order Reorder Buffer (ROB).
2. **Cycle-Accurate Hardware Waveforms (`alu_timing_diagram.png`)**:
   - Multi-channel digital waveform plot showing `clk`, `req_valid`, `req_ready`, `input_stage`, `pipe_depth`, `active_op`, and `retired_tx`.
3. **Valid/Ready Handshake Sequence (`alu_sequence_diagram.png`)**:
   - Sequence flow tracing hardware handshake assertions, pipeline dispatch, ROB slot completion, and retirement.
4. **Hardware Pipeline Control State Machine (`alu_pipeline_states.png`)**:
   - Control states: `IDLE` $\rightarrow$ `REQ_ACK` $\rightarrow$ `EXECUTE` $\rightarrow$ `ROB_STALL` $\rightarrow$ `RETIRE`.

### Step 2: Build the `.odt` Hardware Specification (`generate_odt_spec.py`)
Run `generate_odt_spec.py` to build the `.odt` specification document:

```bash
.venv/bin/python skills/hw-spec-odt-generator/scripts/generate_odt_spec.py
```

---

## How to Adapt This Skill for Future Examples

To use this skill for **Example 0 (Simple Pipeline Stage)**, **Example 2 (FIFO Backpressure Streaming)**, or **Example 3 (Shared Switch Arbitration)**:

1. **Customize Diagram Script**: Update `skills/hw-spec-odt-generator/scripts/diagram_generator.py` to draw the hardware microarchitecture, interface signals, and timing waveforms for the new example.
2. **Customize Hardware Tables**: Update `generate_odt_spec.py` with the signal maps, parameters, valid/ready rules, and verification scenarios for the new hardware block.
3. **Re-run Builders**: Execute `diagram_generator.py` followed by `generate_odt_spec.py`.
