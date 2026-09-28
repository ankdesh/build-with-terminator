# Project Constitution: Rule2DRC

## Overview
This repository manages the Rule2DRC benchmark dataset and tooling for synthesizing and validating KLayout DRC Ruby runsets from natural language specifications.

## Core Rules & Engineering Standards

### 1. Environment & Dependency Management
- Always use `uv` and `uv venv` for environment setup and deterministic dependency resolution.
- Run scripts and tools using `uv run python scripts/<script_name>.py`.

### 2. Error Handling & Reliability
- Fail explicitly and early. Never let errors pass silently or float downstream.
- Use precise domain exceptions (e.g., `DatasetDownloadError`, `DatasetValidationError`) and structured console output.
- Avoid overusing lax default values.
- Apply static type hinting throughout.

### 3. Architecture & Code Structure
- Hoist all constants (HF repository IDs, file paths, thresholds, counts) to the top of modules.
- Maintain decoupled, clear responsibilities.
- The `src/` directory is reserved for core benchmark/synthesis modules. Operational scripts live under `scripts/`.

### 4. Testing & Verification
- Validate data integrity upon every download (row counts, column schemas, payload presence).
- Prioritize end-to-end integration verification.
