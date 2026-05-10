## ADDED Requirements

### Requirement: VFF-16 fragmentation logic
The system SHALL provide a command-line tool `generate_vff16.py` that implements the VFF-16 dataset construction algorithm, including sector-boundary padding and variable-length fragmentation.

#### Scenario: Basic fragmentation and padding
- **WHEN** the tool is run on a folder containing 10 JPEG files with 512B sector size
- **THEN** it pads each file to a multiple of 512 bytes with random data, splits each file into 1-10 fragments, shuffles the fragments, and outputs individual 512B sectors.

### Requirement: Sector-level metadata tracking
The system SHALL generate a metadata file (CSV) that maps every generated sector file (`sample_i.bin`) back to its original source file, its offset within that file, and its fragment ID.

#### Scenario: Verifying sector lineage
- **WHEN** a dataset is generated
- **THEN** a `metadata.csv` is produced where each row contains `sample_name`, `original_file_path`, `offset_in_original`, and `is_padding_sector`.

### Requirement: Configurable generation parameters
The tool SHALL support parameters for sector size (512 vs 4096), output directory, and maximum data volume per class.

#### Scenario: Generating a subset for 4K sectors
- **WHEN** run with `--sector-size 4096 --max-mb-per-class 10`
- **THEN** the tool generates exactly 10MB of 4096-byte sectors for each class in the source directory.
