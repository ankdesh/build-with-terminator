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

## Dataset Files

After running the script, the following Parquet files are generated in `data/`:

| File | Rows | Description |
|---|---|---|
| `data/tasks.parquet` | 1,000 | Task definitions, natural language prompt, rule specs, and gold DRC deck |
| `data/testcases.parquet` | 13,921 | Labeled GDS layout test cases with pass/fail violation labels |

## Project Structure

```
eda/rule2drc/
├── GEMINI.md               # Project constitution and engineering rules
├── README.md               # Documentation and setup instructions
├── pyproject.toml          # Project metadata and dependencies (uv)
├── scripts/
│   └── download_dataset.py # Self-contained download & validation script
├── src/                    # Reserved for future benchmark & synthesis modules
└── data/                   # Downloaded Parquet files
```
