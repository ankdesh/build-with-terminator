## ADDED Requirements

### Requirement: Automated Dataset Acquisition
The system SHALL provide a mechanism to programmatically download the VFF-16 (RFF) dataset from the specified source URLs on the internet, with support for configurable download volumes (e.g., full dataset or a smaller percentage subset).

#### Scenario: Successful download of 512-byte configuration with limit
- **WHEN** the preparation script is executed with `--sector-size 512 --max-gb 0.5`
- **THEN** the script downloads the 512-byte archive and extracts a subset not exceeding 0.5 GB to `./data/RFF/512/`

#### Scenario: Successful full download of 4k configuration
- **WHEN** the preparation script is executed with `--sector-size 4k` (without size limit)
- **THEN** the script downloads the complete 4k archive and extracts it to `./data/RFF/4k/`

### Requirement: Standardized Directory Structure
The system SHALL organize extracted data into a predictable directory structure required by the model and dataloaders.

#### Scenario: Directory tree validation
- **WHEN** the extraction process completes
- **THEN** the `./data/RFF/512/` and `./data/FFT/` (for classes.json) directories are present and populated

### Requirement: Class Mapping Metadata
The system SHALL ensure the `classes.json` file is present to map numerical indices to file extensions (jpg, pdf, etc.).

#### Scenario: Class map availability
- **WHEN** the dataloader is initialized
- **THEN** it reads `./data/FFT/classes.json` and creates a 16-class mapping dictionary
