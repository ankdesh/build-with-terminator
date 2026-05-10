# File Fragment Analysis (VFF-16)

This project implements a deep learning pipeline for **File Fragment Classification (FFC)** using the **CNN-4L** architecture. It supports the generation of the **VFF-16 (Variable-length File Fragment)** dataset from raw source files (like GovDocs1), training the model on raw byte sequences, and performing inference on custom forensic data.

## Project Structure

- `generate_vff16.py`: Reproduces the VFF-16 dataset construction logic (padding, fragmentation, shuffling).
- `verify_vff16.py`: Validates the integrity of a generated VFF-16 dataset.
- `train.py`: Main training script for the CNN-4L model.
- `predict_custom.py`: Inference script for classifying unknown binary fragments.
- `data_preparation.py`: Script to download pre-built VFF-16 archives from the internet.
- `model.py`: CNN-4L model architecture definition.
- `dataset.py`: PyTorch Dataset implementation for VFF-16 sectors.

---

## 🚀 Getting Started

### 1. Prerequisites
This project uses [uv](https://github.com/astral-sh/uv) for dependency management. Install dependencies:
```bash
uv pip install -r requirements.txt
```

### 2. Dataset Preparation

#### Option A: Generate from GovDocs1 (Local)
Use this if you have the raw GovDocs1 files or any folder of files grouped by extension or in subdirectories.
```bash
uv run python3 generate_vff16.py \
    --source-dir /path/to/gov1 \
    --output-dir ./data/RFF \
    --sector-size 512 \
    --max-mb-per-class 50
```
*   **Fragmentation**: Randomly splits files into 1-10 fragments.
*   **Metadata**: Generates a `metadata.csv` for each class mapping sectors back to original files.

#### Option B: Download Pre-built Dataset
```bash
uv run python3 data_preparation.py --sector-size 512
```

#### Verify Dataset
```bash
uv run python3 verify_vff16.py --dataset-path ./data/RFF/512 --sector-size 512
```

---

### 3. Training
Train the model on the generated fragments. The training script automatically detects classes based on the folder structure in `./data/RFF/`.

```bash
uv run python3 train.py \
    --sector-size 512 \
    --batch-size 128 \
    --epochs 20 \
    --lr 0.001
```
*Weights are saved to `cnn4l_512.pth`.*

---

### 4. Testing & Inference
To classify unknown binary chunks or test on a new set of data:

```bash
uv run python3 predict_custom.py \
    --chunks-dir ./custom_chunks \
    --model-path cnn4l_512.pth \
    --sector-size 512 \
    --output-csv results.csv
```

---

## 🛠 Advanced Features

### Variable-Length Fragmentation (VFF)
Unlike traditional fixed-sector datasets, this project preserves **inter-sector context** by shuffling fragments rather than individual sectors. This mimics real-world file system fragmentation.

### Sector Lineage Tracking
The generation script produces a metadata CSV with:
- `sample_name`: The `.bin` file name.
- `original_file`: Source filename from GovDocs1.
- `offset_in_original`: Byte offset in the source file.
- `fragment_id`: Grouping ID for contiguous sectors.
- `is_padding`: Boolean flag for sectors created via random padding.

## 📄 License
This project is for research and forensic analysis purposes.
