# Project Constitution: KLayout DRC & DeepSeek Harness Flow Integration

This document defines the architectural guidelines, standards, and workflow invariants for the `klayout-4-drc` project.

---

## 1. Environment & Dependency Management
- **Python Toolchain**: Exclusively use `uv` and `uv venv` for dependency resolution, virtual environment management, and script execution (`uv run pytest`, `uv run python -m klayout_drc.cli`).
- **Harness Subsystem**: Managed in the `harness/` directory using npm/node and linked to local `/home/ankdesh/explore/deepseek-harness` workspaces via `node scripts/link-harness.mjs`. Zero modifications are made to the core harness repository.

---

## 2. Architecture & Modular Design
- **Single Responsibility (One primary class per file)**:
  - `src/klayout_drc/config.py`: Centralized configuration, hoisted constants, and exceptions.
  - `src/klayout_drc/runner.py` (`DRCRunner`): Headless KLayout batch execution.
  - `src/klayout_drc/parser.py` (`DRCParser`): Parsing `.lyrdb` / `.gds` violation databases into strongly typed models.
  - `src/klayout_drc/reporter.py` (`DRCReporter`): Generating formatted human-readable textual reports.
  - `src/klayout_drc/drc_context.py` (`DRCContextProcessor`): Extracting matching rule blocks and constraints from DRC decks.
  - `src/klayout_drc/gds_context.py` (`GDSContextProcessor`): Windowed extraction of layout geometry around violation coordinates.
  - `src/klayout_drc/knowledge_loader.py` (`KnowledgeLoader`): Merging domain knowledge base markdown documents.
  - `src/klayout_drc/fixer.py` (`DRCFixer`): Geometric polygon repair with KLayout Region operations.
  - `src/klayout_drc/cli.py`: Unified CLI supporting both full pipeline execution and granular node modes (`--mode run-drc`, `violation-ctx`, `drc-ctx`, `gds-ctx`, `load-knowledge`, `save-script`).
- **Fail Early & Explicitly**: Never let errors fail silently. Use dedicated exceptions (`DRCConfigurationError`, `DRCExecutionError`, `DRCParserError`).
- **Interface-Driven Flow**: Harness interaction uses the 7-node typed `klayout.gds_drc_flow` flow definition:
  1. `run_drc` (`klayout.run_drc`)
  2. `violation_ctx` (`klayout.process_violation_context`)
  3. `drc_ctx` (`klayout.process_drc_context`)
  4. `gds_ctx` (`klayout.process_gds_context`)
  5. `load_knowledge` (`klayout.load_knowledge`)
  6. `agent_llm` (`kind: model`, instructions: `generate_fix.md`)
  7. `save_script` (`klayout.save_script`)

---

## 3. Testing Strategy
- Prioritize end-to-end integration tests over isolated unit tests.
- Test suites in `tests/test_drc_pipeline.py` exercise:
  - Detection of intentional DRC violations on ASAP7 layouts.
  - Automated geometric healing reducing violations to zero.
  - DRC rule deck context extraction (`DRCContextProcessor`).
  - Local layout geometry window extraction (`GDSContextProcessor`).
  - Domain knowledge loading (`KnowledgeLoader`).
  - Granular CLI execution modes matching all flow nodes.
  - Fail-early checks on invalid input paths.

---

## 4. Directory Conventions
- `src/klayout_drc/`: Python package implementation.
- `knowledge/`: Markdown knowledge base files (`asap7_rules_guide.md`, `geometric_fix_techniques.md`, `klayout_api_patterns.md`).
- `test_data/layouts/`: Sample GDS files (`asap7_test.gds`, `asap7_fixed.gds`).
- `test_data/rules/`: DRC rule decks (`asap7_mini.drc`).
- `reports/`: Output directory for report databases (`.lyrdb`), textual reports (`.txt`), and generated fix scripts (`fix_layout.py`).
- `harness/`: Isolated DeepSeek Harness product bundle (`package.json`, `harness.product.json`, `scripts/`, `src/`, `profile/`).
