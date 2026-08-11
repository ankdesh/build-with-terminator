# archdoc2modules: Automated PDF Specification Ingestion & Modular Architecture Decomposition

A two-stage pipeline for parsing Electronic System-Level (ESL) hardware architectural specifications (PDF) and decomposing them into structured, modular Markdown documentation with externalized figures and register map tables.

---

## Architectural Overview

```
                                  +---------------------------------------+
                                  |            Target PDF File            |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |     STAGE 1: Docling PDF Parser       |
                                  | - Layout & Vision Recognition         |
                                  | - TableFormer CSV Table Extraction    |
                                  | - High-DPI Figure Bitmap Export       |
                                  | - Sectional MD & Manifest Generation  |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      Stage 1 Intermediate Assets      |
                                  |  - parsed_spec/sections/*.md          |
                                  |  - parsed_spec/assets/figures/*.png   |
                                  |  - parsed_spec/assets/tables/*.csv    |
                                  |  - parsed_spec/parsing_manifest.json  |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |     STAGE 2: OpenAI gpt-4o            |
                                  |           Module Decomposer           |
                                  | - Architectural Hierarchy Analysis    |
                                  | - Top-Level & IP Block Identification |
                                  | - Asset Localization & Link Rewrite   |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |  STAGE 2: Modular Output Directory    |
                                  |  - output/top_level/                  |
                                  |      ├── README.md                    |
                                  |      └── assets/ (figures & tables)   |
                                  |  - output/modules/<module_name>/      |
                                  |      ├── README.md                    |
                                  |      └── assets/ (figures & tables)   |
                                  +---------------------------------------+
```

---

## Installation

This project prefers `uv` for environment and dependency management.

```bash
# Create and activate virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

For Stage 2 OpenAI integration, export your API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

---

## CLI Usage

### 1. Run End-to-End Pipeline (Stage 1 -> Stage 2)
```bash
python cli.py run --pdf path/to/spec.pdf --output-dir ./decomposed_arch
```

### 2. Run Stage 1 Only (PDF Ingestion -> MD + Assets)
```bash
python cli.py stage1 --pdf path/to/spec.pdf --output-dir ./parsed_stage1
```

### 3. Run Stage 2 Only (Decomposition of Stage 1 Outputs)
```bash
python cli.py stage2 --input-dir ./parsed_stage1 --output-dir ./decomposed_stage2 --model gpt-4o
```

---

## Python API Usage

```python
from stage1_parser import Stage1DoclingParser
from stage2_decomposer import Stage2Decomposer

# Stage 1: Parse PDF into section Markdown files, figures, and CSV tables
parser = Stage1DoclingParser(output_dir="./parsed_stage1")
section_files = parser.parse_pdf("soc_spec.pdf")

# Stage 2: Decompose into top-level and module-level Markdown directories
decomposer = Stage2Decomposer(
    stage1_dir="./parsed_stage1",
    output_dir="./decomposed_stage2",
    openai_model="gpt-4o"
)
summary = decomposer.decompose()
print(f"Decomposed {summary['total_modules']} modules.")
```

---

## Testing & Verification

Generate a synthetic architectural specification PDF and run the integration test suite:

```bash
# Run unit & integration tests
python -m unittest test_pipeline.py
```

---

## Output Structure

The decomposed directory contains:

```
decomposed_stage2/
├── decomposition_manifest.json
├── top_level/
│   ├── README.md
│   └── assets/
│       ├── figures/
│       └── tables/
└── modules/
    ├── dma_controller/
    │   ├── README.md
    │   └── assets/
    │       ├── figures/
    │       └── tables/
    └── vectored_interrupt_controller/
        ├── README.md
        └── assets/
            ├── figures/
            └── tables/
```
