# Project Constitution: KLayout DRC & DeepSeek Harness Flow Integration

This document defines the architectural guidelines, standards, and workflow invariants for the `klayout-4-drc` project.

---

## 1. Environment & Dependency Management
- **Python Toolchain**: Exclusively use `uv` and `uv venv` for dependency resolution, virtual environment management, and script execution (`uv run pytest`, `uv run klayout-drc`).
- **Harness Subsystem**: Managed in the `harness/` directory using npm/node and linked to local `/home/ankdesh/explore/deepseek-harness` workspaces via `node scripts/link-harness.mjs`. No modifications are made to the core harness repository.

---

## 2. Architecture & Modular Design
- **Single Responsibility**: Enforce one primary class per file:
  - `src/klayout_drc/config.py`: Centralized configuration, hoisted constants, and exceptions.
  - `src/klayout_drc/runner.py` (`DRCRunner`): Headless KLayout batch execution.
  - `src/klayout_drc/parser.py` (`DRCParser`): Parsing `.lyrdb` / `.gds` violation databases into strongly typed models.
  - `src/klayout_drc/reporter.py` (`DRCReporter`): Generating formatted human-readable textual reports.
  - `src/klayout_drc/fixer.py` (`DRCFixer`): Geometric polygon repair with KLayout Region operations.
  - `src/klayout_drc/cli.py`: Unified CLI and structured JSON subprocess interface.
- **Fail Early & Explicitly**: Never let errors fail silently. Use dedicated exceptions (`DRCConfigurationError`, `DRCExecutionError`, `DRCParserError`).
- **Interface-Driven Flow**: Harness interaction uses the typed `klayout.gds_drc_flow` flow definition and `klayout.run_drc_and_report` operation.

---

## 3. Testing Strategy
- Prioritize end-to-end integration tests over isolated unit tests.
- Test suites in `tests/test_drc_pipeline.py` exercise:
  - Detection of intentional DRC violations on ASAP7 layouts.
  - Automated geometric healing reducing violations to zero.
  - Fail-early checks on invalid input paths.

---

## 4. Directory Conventions
- `src/klayout_drc/`: Python package implementation.
- `test_data/layouts/`: Sample GDS files (`asap7_test.gds`, `asap7_fixed.gds`).
- `test_data/rules/`: DRC rule decks (`asap7_mini.drc`).
- `reports/`: Output directory for report databases (`.lyrdb`) and textual reports (`.txt`).
- `harness/`: Isolated DeepSeek Harness product bundle (`package.json`, `harness.product.json`, `scripts/`, `src/`).
