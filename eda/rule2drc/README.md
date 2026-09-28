# Rule2DRC Dataset & Benchmark Runner

This project provides tools and scripts to download, manage, and benchmark the **Rule2DRC** dataset from Hugging Face ([`jusjinuk/Rule2DRC`](https://huggingface.co/datasets/jusjinuk/Rule2DRC)).

## Overview

**Rule2DRC** is a benchmark for evaluating LLM agents on synthesizing executable KLayout DRC Ruby runsets from natural-language design rule specifications.

- **Tasks**: 1,000 problem rows with prompts, design rule specifications, and gold DRC decks.
- **Testcases**: 13,921 labeled GDS testcases with binary layouts to evaluate functional DRC script execution.

## Setup with `uv`

Ensure [`uv`](https://github.com/astral-sh/uv) is installed.

```bash
# Initialize virtual environment and install all dependencies
uv sync
```

## Downloading the Dataset

Run the self-contained downloader script:

```bash
# Download both tasks and testcases into data/
uv run python scripts/download_dataset.py

# Force re-download even if already present
uv run python scripts/download_dataset.py --force

# Download tasks only (excluding testcases)
uv run python scripts/download_dataset.py --skip-testcases

# Specify custom destination directory
uv run python scripts/download_dataset.py --output-dir path/to/output
```

## Extracting GDS Testcase Layouts

To extract all 13,921 binary `.gds` layout files into a folder structure and tabulate size statistics:

```bash
# Extract into data/extracted_gds/ (default) and display statistics
uv run python scripts/extract_gds.py

# Extract organized by problem subdirectories: problems/{problem_id}/{split}/*.gds
uv run python scripts/extract_gds.py --by-problem

# Specify custom output directory
uv run python scripts/extract_gds.py --output-dir extracted_gds
```

## Downloading Large Sky130 Production GDS Layouts

To download full-scale production GDS files (`user_proj_example.gds` ~53 MB or `caravel.gds` ~54 MB gz / ~250 MB raw):

```bash
# Download user_proj_example.gds
uv run python scripts/download_large_gds.py --targets user_proj_example

# Download full Caravel SoC harness
uv run python scripts/download_large_gds.py --targets caravel

# Download all available large targets
uv run python scripts/download_large_gds.py --targets all
```

## Running the Master Pipeline

To run all download, extraction, and statistical analysis scripts in a unified sequence:

```bash
# Run all standard pipeline stages
uv run python scripts/run_all.py

# Run all pipeline stages including large Sky130 GDS download
uv run python scripts/run_all.py --include-large-gds --large-target user_proj_example

# Dry-run mode (simulates pipeline execution)
uv run python scripts/run_all.py --dry-run
```

## Dataset Files

After running the download and extraction scripts, the following artifacts are generated:

| File / Folder | Rows / Files | Description |
|---|---|---|
| `data/tasks.parquet` | 1,000 | Task definitions, natural language prompt, rule specs, and gold DRC deck |
| `data/testcases.parquet` | 13,921 | Labeled GDS layout test cases with pass/fail violation labels |
| `data/extracted_gds/` | 13,921 | Extracted binary `.gds` layout files (`pass/` and `fail/`) |
| `data/large_gds/` | 1-2 files | Production-scale Sky130 GDS layouts (`user_proj_example.gds`, `caravel.gds`) |

## Documentation

Comprehensive project documentation:
- **[`docs/dataset_reference.md`](file:///home/ankdesh/explore/build-with-terminator/eda/rule2drc/docs/dataset_reference.md)**: In-depth Rule2DRC benchmark reference, schema details, ER diagram, `gds_path` distribution, and layout size statistics.
- **[`docs/sky130_fd_sc_hd_gds_stats.md`](file:///home/ankdesh/explore/build-with-terminator/eda/rule2drc/docs/sky130_fd_sc_hd_gds_stats.md)**: GDSII layout statistics, functional categorization, and size percentiles for the SkyWater SKY130 HD standard cell library.

## Project Structure

```
eda/rule2drc/
├── GEMINI.md                  # Project constitution and engineering rules
├── README.md                  # Documentation and setup instructions
├── pyproject.toml             # Project metadata and dependencies (uv)
├── docs/
│   ├── dataset_reference.md   # In-depth dataset reference, schemas & size stats
│   └── sky130_fd_sc_hd_gds_stats.md # SkyWater 130nm HD standard cell GDS statistics
├── scripts/
│   ├── run_all.py             # Top-level master orchestrator script
│   ├── download_dataset.py    # Self-contained download & validation script
│   ├── extract_gds.py         # Binary GDS extractor & size statistics analyzer
│   ├── sky130_gds_stats.py    # SkyWater 130nm HD library GDS statistics collector
│   └── download_large_gds.py  # Production Sky130 large GDS downloader
├── src/                       # Reserved for future benchmark & synthesis modules
└── data/                      # Downloaded Parquet files and extracted GDS layouts
```



