## Context

The VFF-16 (Variable-length File Fragment) dataset is essential for training the JSANet architecture, as it provides the inter-sector context needed for the model's attention mechanisms. Currently, the project lacks a tool to generate this dataset from a local GovDocs1 corpus. Providing such a tool enables users to create their own splits, support more than 16 classes, and verify the model's performance using granular metadata.

## Goals / Non-Goals

**Goals:**
- Reproduce the exact fragmentation and shuffling logic from the VFF-16 paper.
- Generate a sector-level metadata mapping for traceability.
- Support configurable sector sizes (512B, 4KB) and volume targets (e.g., 50MB per class).
- Ensure consistent output directory structures compatible with `VFF16Dataset` in `dataset.py`.

**Non-Goals:**
- Downloading the GovDocs1 corpus automatically (the user must provide the source directory).
- Implementing the training loop (handled by `train.py`).
- Real-time augmentation during training (this is a pre-processing tool).

## Decisions

### 1. Fragmentation Strategy: Fragment-Level Shuffling
- **Decision**: Pad files to sector boundaries, randomly partition into 1-10 fragments, and then shuffle the *fragments* before assembling the final per-class stream.
- **Rationale**: Shuffling at the sector level (traditional approach) destroys all inter-sector context. Shuffling at the fragment level preserves local context (e.g., within a 5-sector chunk of a PDF) while simulating the randomness of a fragmented disk image.
- **Alternative**: Randomly picking individual sectors from different files. *Rejected* because it fails to test the model's ability to utilize context.

### 2. Metadata Storage: Parallel CSV File
- **Decision**: Store metadata in a single `metadata.csv` file per class (or per dataset) using `pandas`.
- **Rationale**: CSV is easy to inspect manually and programmatically. It separates the "raw byte" requirement of the model from the "forensic lineage" requirement of the user.
- **Alternative**: Storing metadata in the filename (e.g., `file_off_frag.bin`). *Rejected* due to path length limits and difficulty in parsing.

### 3. Sector Padding: Random Bytes
- **Decision**: Pad files to the nearest sector boundary using `os.urandom(N)`.
- **Rationale**: Random bytes better simulate the "noise" or "unallocated space" found in real disk images compared to zero-padding, which can be an easy-to-learn but unrealistic feature for a CNN.

## Risks / Trade-offs

- **[Risk] High Memory Usage during Shuffling** → **Mitigation**: Instead of loading all bytes into memory, store a list of "Fragment Metadata" objects (source path, start, length). Shuffle this list, then read/write fragments sequentially to the output stream.
- **[Risk] Small Files < 10 Sectors** → **Mitigation**: If a file has $N < 10$ sectors, the script will limit $K$ (number of fragments) to $N$, ensuring every fragment has at least one sector.
- **[Risk] Large Datasets** → **Mitigation**: Implement a `--max-mb-per-class` flag to allow users to generate manageable subsets.
