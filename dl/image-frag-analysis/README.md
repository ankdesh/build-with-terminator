# File Fragment Analysis (VFF-16)

This project implements a deep learning pipeline for **File Fragment Classification (FFC)** using a parameterized **CNN-4L** architecture. It supports automated dataset acquisition (VFF-16/RFF), custom generation from GovDocs1, and forensic inference with sector-level reporting.

## Project Structure

All core logic resides in the `src/` directory:
- `src/data_preparation.py`: Unified entry point for all data tasks (benchmark, generate, custom).
- `src/train.py`: High-performance training pipeline with warmup and cosine annealing.
- `src/predict_custom.py`: Forensic inference script for sector-level classification.
- `src/model.py`: Parameterized CNN-4L model with dynamic depth and downsampling.
- `src/dataset.py`: Efficient disk-to-memory PyTorch loader.

Generated files are organized into:
- `data/`: All datasets (benchmark, generated, and custom chunks).
- `models/`: Serialized model weights (`best_cnn_model.pth`).
- `output/`: Classification reports and forensic linkage metadata.

---

## 🚀 Getting Started

### 1. Prerequisites
This project uses [uv](https://github.com/astral-sh/uv) for dependency management. Create a virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # Linux/macOS
uv pip install torch torchvision numpy requests scikit-learn gdown tqdm
```

### 2. Unified Data Processing
The `src/data_preparation.py` script handles all data ingestion via three distinct modes.

#### Mode A: Benchmark (Download VFF-16)
Automatically downloads and extracts the standard RFF (VFF-16) dataset from Google Drive.
```bash
python src/data_preparation.py benchmark --sector-size 512 --max-gb 0.5
```
- `--sector-size`: Supports `512` or `4k`.
- `--max-gb`: Optional. Limits extraction to a smaller section of the dataset for testing.

#### Mode B: Generate (From GovDocs1)
Reproduces the VFF-16 construction logic (padding, random fragmentation, shuffling) from raw source files.
```bash
python src/data_preparation.py generate --source-dir /path/to/govdocs1 --sector-size 512
```

#### Mode C: Custom (Forensic Chunking)
Segments user-provided files into padded sectors for inference.
```bash
python src/data_preparation.py custom /path/to/evidence --sector-size 512
```
- **Metadata Linkage**: Automatically generates `data/custom/metadata.csv` to map fragments back to parent files.

---

### 3. Training
Train the model on any dataset generated above. The script reports both **Training Accuracy** and **Validation Accuracy** for better monitoring.

```bash
python src/train.py \
    --data-dir ./data/benchmark/512 \
    --sector-size 512 \
    --batch-size 512 \
    --epochs 96 \
    --num-layers 4
```
- `--num-layers`: Dynamically adjust the CNN depth from the command line.
- **Optimization**: Uses SGD with 500-step linear warmup and Cosine Annealing.
- **Output**: The best model is saved to `models/best_cnn_model.pth`.

---

### 4. Forensic Inference
Perform classification on custom chunks. The engine reports results for every individual sector independently.

```bash
python src/predict_custom.py \
    --chunks-dir ./data/custom/512/unlabeled \
    --model-path ./models/best_cnn_model.pth \
    --num-layers 4 \
    --sector-size 512
```
- **Results**: Detailed classification log (fragment name, predicted class, confidence) saved to `output/results/inference_results.csv`.

---

## 🛠 Advanced Features

### Variable-Length Fragmentation (VFF)
Unlike traditional fixed-sector datasets, this project mimics real-world storage by preserving inter-sector context through randomized fragmentation (1-10 sectors per fragment) before shuffling.

### Parameterized Architecture
- **Position Embeddings**: Learnable vectors added to byte embeddings to preserve spatial awareness within a sector.
- **4k Downsampling**: If `sector-size` is set to 4096, the model automatically adds a 3-layer convolutional downsampling block to compress the sequence to 512 before the core feature extractor, preventing GPU memory exhaustion.

## 📄 License
This project is for research and forensic analysis purposes.
