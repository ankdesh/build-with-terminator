# xls2datasets: XLS/XLSX Table Extraction & Dataset Generation Tool

A standalone two-stage pipeline for extracting tables from XLS/XLSX files and generating analysis-ready CSV datasets with LLM-generated schema metadata.

---

## Architecture

```
Input XLSX → [Stage 1: Docling Extract] → CSVs + Manifest
                                              ↓
                                  [Stage 2: LLM Analyze] → Schema JSONs + Data Dictionary
```

- **Stage 1**: Uses IBM Docling's `DocumentConverter` to detect and extract all tables across all sheets. Each table becomes an individual CSV file.
- **Stage 2**: Sends sample data from each CSV to a configurable OpenAI-compatible LLM (supports vLLM-hosted models) to generate structured data dictionaries with column types, units, and descriptions.

---

## Installation

```bash
# Create and activate virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

---

## Configuration

### LLM Configuration (`llm_config.yaml`)

```yaml
base_url: "https://api.openai.com/v1"   # Or your vLLM endpoint
model: "gpt-4o-mini"                     # Model name
temperature: 0.2
max_tokens: 4096
```

### API Key (Environment Variable)

```bash
export OPENAI_API_KEY="your-api-key-here"
```

---

## CLI Usage

### End-to-End (Stage 1 → Stage 2)
```bash
python cli.py run --xls data.xlsx --output-dir ./output --config llm_config.yaml
```

### Stage 1 Only (Extract Tables)
```bash
python cli.py stage1 --xls data.xlsx --output-dir ./extracted_tables
```

### Stage 2 Only (Analyze Schemas)
```bash
python cli.py stage2 --input-dir ./extracted_tables --output-dir ./analyzed --config llm_config.yaml
```

---

## Python API

```python
from stage1_extractor import Stage1XlsExtractor
from stage2_schema_analyzer import Stage2SchemaAnalyzer

# Stage 1: Extract tables
extractor = Stage1XlsExtractor(output_dir="./extracted")
csv_files = extractor.extract("data.xlsx")

# Stage 2: Analyze schemas
analyzer = Stage2SchemaAnalyzer(
    stage1_dir="./extracted",
    output_dir="./analyzed",
    config_path="llm_config.yaml",
)
data_dict = analyzer.analyze()
```

---

## Output Structure

```
output/
├── tables/
│   ├── SensorData_table_01.csv
│   ├── Experiments_table_01.csv
│   ├── Experiments_table_02.csv
│   └── Summary_table_01.csv
├── schemas/
│   ├── SensorData_table_01_schema.json
│   ├── Experiments_table_01_schema.json
│   ├── Experiments_table_02_schema.json
│   └── Summary_table_01_schema.json
├── extraction_manifest.json
└── data_dictionary.json
```

---

## Testing

```bash
python -m unittest test_pipeline.py
```
