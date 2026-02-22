# gdstk Examples Setup

This directory contains scripts and instructions for setting up and running [gdstk](https://github.com/heitzmann/gdstk) with sample GDSII files.

## Prerequisites
- Python 3 environment (a local `.venv` is recommended)
- `uv` package manager (optional, but used in these steps for faster installation)

## Installation

1. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Install the required dependencies (`gdstk`):
   ```bash
   uv pip install gdstk
   ```

## Usage

### 1. Download GDSII Examples
Place the downloaded GDSII files in the `../gds_samples/` directory relative to this folder.

Example manual download:
```bash
mkdir -p ../gds_samples
cd ../gds_samples
wget https://www.yzuda.org/download/_GDSII_examples/inv.gds2
cd ../gdstk
```

### 2. Run the Sample Script
The `main.py` script automatically finds and parses all `.gds` and `.gds2` files located in the `../gds_samples/` directory.

Run the script to see the statistics for each file:

```bash
python main.py
```

### Expected Output
The script will output the library name, number of cells, and details (number of polygons, paths, labels) for up to the first 5 cells in each file:

```
Hello from gdstk!
Loading ../gds_samples/inv.gds2
Library name: mentor.db
Number of cells: 2
Cell 1: via - Polygons: 3, Paths: 0, Labels: 0
Cell 2: inv1 - Polygons: 59, Paths: 10, Labels: 0
```
