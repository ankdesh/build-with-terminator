# SystemC Scaffold Generator (Phase 1)

This project implements a Python-based generator that parses IP-XACT (IEEE 1685) XML hardware block descriptions and produces C++ SystemC / TLM-2.0 Approximately Timed (AT) module scaffolding. 

Phase 1 generates a complete, clean, and compilable block scaffold from interface and memory map definitions. This acts as the baseline for Phase 2, which will generate the internal implementation logic using LLMs.

## Core Features

- **Standard TLM-2.0 Sockets**: Automatically maps IP-XACT master and slave bus interfaces to standard `tlm_utils::simple_initiator_socket` and `tlm_utils::simple_target_socket` using the `tlm::tlm_generic_payload`.
- **Structured Registers**: Generates a header file defining register maps, sub-structures, and field bit-unions (including automatic padding calculations) for easy, type-safe register manipulation.
- **Address-Decoding Callback**: Generates full read/write address decoding in target socket blocking transport (`b_transport`) and debug transport (`transport_dbg`) callbacks.
- **Discrete Signal Ports**: Automatically maps general hardware pins to standard SystemC ports (`sc_in`/`sc_out`), handling width-based types (`bool` vs `sc_dt::sc_bv`).
- **CMake Support**: Generates a project-level `CMakeLists.txt` to build the generated component as a library.
- **Verification Testbench**: Generates a self-contained dummy testbench executable (`<component_name>_tb.cpp`) that instantiates the module, binds all sockets/signals, and verifies basic register read/write transaction flows.

## Project Structure

```
├── main.py                    # CLI Entrypoint
├── pyproject.toml             # Python Project configuration
├── README.md                  # Project Documentation
├── systemc-gen/
│   └── GEMINI.md              # Project Constitution
├── systemc_gen/               # Main Generator Package
│   ├── __init__.py
│   ├── parser.py              # Namespace-agnostic IP-XACT XML Parser
│   ├── generator.py           # Jinja2 template rendering manager
│   ├── model/                 # Intermediate Representation (IR) Dataclasses
│   │   ├── __init__.py
│   │   ├── bus_interface.py
│   │   ├── component.py
│   │   ├── field.py
│   │   ├── port.py
│   │   └── register.py
│   └── templates/             # Code Generation Jinja2 templates
│       ├── block.cpp.jinja
│       ├── block.h.jinja
│       ├── block_regs.h.jinja
│       ├── block_tb.cpp.jinja
│       └── CMakeLists.txt.jinja
└── tests/                     # Test Suite
    ├── data/
    │   └── sample_ipxact.xml  # Mock IP-XACT component spec
    └── test_generator.py      # Parser/Generator tests
```

## Getting Started

### Prerequisites
Make sure you have [uv](https://github.com/astral-sh/uv) installed.

### Installation
Installs dependencies into a local virtual environment:
```bash
uv sync
```

### Running the Generator
To generate scaffolding from an IP-XACT XML description:
```bash
uv run python main.py --ipxact <path_to_ipxact.xml> --out <output_directory>
```

For example, to generate scaffolding for our mock component:
```bash
uv run python main.py --ipxact tests/data/sample_ipxact.xml --out output/
```
This generates the C++ files under `output/timer_block/`.

### Running Python Tests
To run the python test suite:
```bash
uv run pytest
```

## Generated Files Structure
For any component (e.g. `timer_block`), the generator creates:
1. `timer_block.h`: Class declaration, sockets, signal ports, register map object, and callback signatures.
2. `timer_block_regs.h`: Structs for register maps and bitfield register unions.
3. `timer_block.cpp`: Constructor binding callbacks, block transport callbacks (`b_transport` / `transport_dbg`) with register address decoding.
4. `timer_block_tb.cpp`: Dummy testbench initiating a sample register write/read verification transaction.
5. `CMakeLists.txt`: Build configurations to compile the generated block library and run the testbench.
