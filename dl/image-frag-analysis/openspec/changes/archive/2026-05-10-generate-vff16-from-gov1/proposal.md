## Why

The current workflow relies on pre-constructed or dummy datasets, which limits the ability to evaluate model performance on custom forensic data or the full GovDocs1 corpus. To support realistic forensic research, there is a need for a tool that can replicate the VFF-16 (Variable-length File Fragment) dataset construction process from raw GovDocs1 files, while providing deep traceability through sector-level metadata.

## What Changes

- **New Dataset Generation Script**: Implementation of `generate_vff16.py` to transform GovDocs1 (or any folder of files) into a VFF-16 formatted dataset.
- **Variable-length Fragmentation**: Logic to randomly fragment files (1-10 fragments) and shuffle them to preserve intra-sector context while disrupting inter-sector order.
- **Metadata Sidecar Generation**: Creation of a comprehensive CSV mapping each generated sector back to its original file, offset, and fragment ID.
- **Configurable Sector Sizes**: Support for both 512-byte and 4096-byte (4K) sector configurations.

## Capabilities

### New Capabilities
- `vff16-data-generator`: Core logic for padding, fragmenting, shuffling, and assembling file fragments into a forensic dataset.
- `sector-metadata-tracker`: System to record and export the lineage of every data sector in the generated dataset.

### Modified Capabilities
- `fragment-dataset-manager`: Update to support local generation of datasets in addition to downloading pre-built ones.

## Impact

- **New Files**: `generate_vff16.py`
- **Dependencies**: Requires `numpy`, `pandas` (for metadata export), and access to a source corpus (e.g., GovDocs1).
- **Workflow**: Adds a "generation" step prior to training for users wishing to use custom data splits.
