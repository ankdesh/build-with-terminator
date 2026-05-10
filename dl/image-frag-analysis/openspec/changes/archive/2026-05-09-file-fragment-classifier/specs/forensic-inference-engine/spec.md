## ADDED Requirements

### Requirement: Sequential File Chunking with Padding
The inference system SHALL be able to divide any file into exact sector-sized chunks, applying zero-padding to the final chunk if necessary.

#### Scenario: Chunking a non-aligned file
- **WHEN** a 1000-byte file is chunked with 512-byte sector size
- **THEN** two chunks are produced: one 512-byte chunk and one 488-byte chunk padded with 24 zero-bytes to reach 512 bytes

### Requirement: Sector-Level Prediction Reporting
The system SHALL report classification results for each individual sector/fragment independently, including the predicted class and the confidence score (probability).

#### Scenario: Detailed sector-level log
- **WHEN** a file with 10 fragments is processed
- **THEN** the system outputs a log with 10 entries, each identifying the specific fragment index, its predicted file type, and the softmax probability.

### Requirement: Inference Mode Configuration
The system SHALL ensure the model is in evaluation mode (`model.eval()`) and gradients are disabled during custom data processing.

#### Scenario: Evaluation mode activation
- **WHEN** the `predict_custom.py` script starts
- **THEN** it executes `model.eval()` and wraps inference in `torch.no_grad()`
