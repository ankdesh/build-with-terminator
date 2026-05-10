## Why

The recovery and identification of digital evidence from raw binary data (file carving) is a foundational challenge in forensics, especially when file system metadata is missing or corrupted. Traditional signature-based methods fail on fragmented data or high-entropy compressed streams, necessitating a deep learning approach that can autonomously discover latent patterns in raw byte streams.

## What Changes

- **New Dataset Management**: Implementation of scripts to download, extract, and standardize the VFF-16 (Variable-length File Fragment) dataset.
- **Parametric CNN Architecture**: Creation of a flexible 4-layer Convolutional Neural Network (CNN-4L) capable of processing 512-byte and 4,096-byte memory sectors.
- **High-Efficiency Training Pipeline**: Implementation of a training loop utilizing Stochastic Gradient Descent (SGD) with linear warmup and cosine annealing learning rate schedules.
- **Forensic Inference Tools**: Development of operational scripts for chunking arbitrary files, applying necessary padding, and reporting classification results for each individual sector.

## Capabilities

### New Capabilities
- `fragment-dataset-manager`: Programmatic acquisition, extraction, and directory structuring of the VFF-16 (RFF) dataset from the internet with configurable download sizes.
- `cnn-4l-model`: A parameterized PyTorch `nn.Module` implementing the 4-layer CNN architecture, including embedding projection, learnable position embeddings, and dynamic downsampling for 4k sectors.
- `training-pipeline`: A robust training and validation engine with custom dataset loaders, SGD optimization, and specialized learning rate scheduling.
- `forensic-inference-engine`: Operational tools for real-world data ingestion (chunking/padding) and sector-level classification reporting for deep binary analysis.

### Modified Capabilities
<!-- No existing capabilities are modified by this change -->

## Impact

- **New Dependencies**: Adds `torch`, `torchvision`, `numpy`, `requests`, and `scikit-learn` to the project.
- **Resource Requirements**: Training the model on 1.3M+ samples will require a CUDA-capable GPU for reasonable convergence times.
- **Project Structure**: Introduces a structured `/data` directory and dedicated scripts for data preparation, training, and inference.
