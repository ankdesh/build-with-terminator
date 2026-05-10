## Context

The project addresses the challenge of file fragment classification (FFC) in memory forensics. Traditional signature-based methods are ineffective when file headers are missing or when dealing with high-entropy data (compressed/encrypted). This design implements a deep learning baseline (CNN-4L) using raw byte sequences as input, focusing on the VFF-16 dataset which mimics realistic file system fragmentation.

## Goals / Non-Goals

**Goals:**
- Implement a parameterized CNN-4L model in PyTorch.
- Automate the acquisition and preparation of the VFF-16 dataset from the internet with configurable download sizes (512-byte and 4k configurations).
- Build a high-performance training pipeline using SGD with specialized learning rate schedules (warmup + cosine annealing).
- Develop operational tools for chunking custom files and reporting individual sector classifications.

**Non-Goals:**
- Implementation of attention mechanisms or transformer-based architectures (e.g., JSANet).
- Support for file types outside the 16 classes defined in VFF-16.

## Decisions

### 1. Model Architecture: CNN-4L with Position Embeddings
- **Rationale**: 1D convolutions are superior to 2D for sequential byte data. Position embeddings are critical for identifying headers/footers regardless of absolute position in the fragment.
- **Implementation**: `nn.Embedding(256, 128)` for bytes + `nn.Embedding(seq_len, 128)` for positions.

### 2. Handling 4k Sectors via Conditional Downsampling
- **Rationale**: Processing 4096-byte sequences directly in the core feature extractor is memory-intensive.
- **Implementation**: If `seq_len == 4096`, apply three `nn.Conv1d` layers (kernel=4, stride=2, padding=1) to compress the sequence to 512 before entering the core blocks.

### 3. Optimization Strategy: High-Momentum SGD
- **Rationale**: Based on the JSANet baseline research, SGD with high momentum (0.9) and significant weight decay (0.1) provides better generalization over binary noise than Adam.
- **Learning Rate**: 0.2 max LR with a 500-step linear warmup to prevent early gradient explosion.

### 4. Sector-Level Reporting for Forensic Analysis
- **Rationale**: While aggregation can hide noise, forensic analysts often need to see the classification of each individual sector to identify embedded files or structural anomalies.
- **Implementation**: Output a classification log mapping every fragment index to its predicted class and probability.

## Risks / Trade-offs

- **[Risk] High-Entropy Collision** → Fragments of compressed files (JPG, GZ, SWF) often appear mathematically similar. 
  - *Mitigation*: Report classification probabilities for each sector to help analysts gauge confidence.
- **[Risk] Resource Exhaustion** → Training on 1.3M samples can consume significant RAM/GPU memory.
  - *Mitigation*: Implement dynamic disk-to-memory loading in the `VFF16Dataset` class and use high batch sizes (512) for gradient stability.
- **[Risk] Sector-Level Noise** → Individual fragments may lack enough information for definitive classification.
  - *Mitigation*: Provide detailed logging that allows for manual secondary analysis of problematic fragments.
