# klayout-as-pylib

This repository demonstrates how to set up and use the `klayout` Python library to generate and read GDSII files programmatically.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (A fast Python package installer and resolver)
- Python 3.12+

## Setup Instructions

1. **Initialize the project (if not already done)**:
   ```bash
   uv init
   ```

2. **Add `klayout` as a dependency**:
   ```bash
   uv add klayout
   ```
   *This automatically resolves and installs the `klayout` PyPI package into a `.venv` virtual environment.*

## Running the Sample Scripts

We have provided two sample scripts to demonstrate the basic capabilities of the `klayout` API. You can run them directly using `uv run`, which will automatically use the correct virtual environment.

### 1. Generating a GDSII File (`create_sample.py`)

This script creates a new GDSII file from scratch with a Top cell, custom layers, and inserts a Box, a Polygon, and some Text.

**To run:**
```bash
uv run create_sample.py
```

**What it does:**
- Creates an empty layout with a database unit (DBU) of 1 nm (0.001 um).
- Adds shapes (Box, Polygon) and text annotations to specific layers.
- Saves the resulting layout as `sample.gds` in the current directory.

### 2. Reading a GDSII File (`read_sample.py`)

This script demonstrates how to parse an existing GDSII file, iterate through its cells, and inspect the shapes on each layer.

**To run:**
```bash
uv run read_sample.py sample.gds
```

**What it does:**
- Reads the input GDSII file.
- Prints the layout's database unit (DBU).
- Iterates through the given layers and shape types.
- Calculates and extracts relevant information such as the width/height of boxes in user units (um).

## Next Steps
- Refer to the [KLayout Python API Documentation](https://www.klayout.de/doc-qt5/programming/index.html) for more advanced layout manipulations, DRC checks, and boolean operations.
