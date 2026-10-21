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
  - `src/klayout_drc/profile.py` (`DRCProfileManager`, `DRCProfile`): Typed profile models (`legacy_mini`, `asap7_curated`, `asap7_public_full`).
  - `src/klayout_drc/runner.py` (`DRCRunner`): Headless KLayout batch execution with profile parameter binding.
  - `src/klayout_drc/parser.py` (`DRCParser`): Parsing `.lyrdb` violation databases into strongly typed models.
  - `src/klayout_drc/reporter.py` (`DRCReporter`): Generating formatted human-readable textual reports.
  - `src/klayout_drc/drc_context.py` (`DRCContextProcessor`): Extracting matching rule blocks and constraints from DRC decks.
  - `src/klayout_drc/gds_context.py` (`GDSContextProcessor`): Windowed extraction of layout geometry around violation coordinates.
  - `src/klayout_drc/knowledge_loader.py` (`KnowledgeLoader`): Merging domain knowledge base markdown documents.
  - `src/klayout_drc/fixer.py` (`DRCFixer`): Deterministic geometric polygon repair with KLayout Region operations.
  - `src/klayout_drc/repair_executor.py` (`RepairExecutor`): Out-of-process subprocess execution of repair patches with timeout and log capture.
  - `src/klayout_drc/validator.py` (`LayoutValidator`): Layout integrity validation (DBU, top-cell preservation, non-empty shapes, bounding box sanity).
  - `src/klayout_drc/layout_diff.py` (`LayoutDiffCalculator`): Per-layer geometric diffing (added/removed areas).
  - `src/klayout_drc/run_manifest.py` (`RunManifestManager`, `RunSpec`): Input snapshotting, hashing, environment capture, and run directory isolation.
  - `src/klayout_drc/run_reporter.py` (`RunReporter`): Before/after comparison, typed status assignment, and audit report generation.
  - `src/klayout_drc/single_shot.py` (`SingleShotOrchestrator`): Chaining the single-shot `Fix → Apply Patch → Report` pipeline.
  - `src/klayout_drc/cli.py`: Unified CLI supporting granular node modes and end-to-end evaluation (`--mode single-shot`).
- **Fail Early & Explicitly**: Never let errors fail silently. Use dedicated exceptions (`DRCConfigurationError`, `DRCExecutionError`, `DRCParserError`).
- **No Silent Fallback**: In `mode=agent`, an LLM failure must produce `model_error` and exit explicitly; it must **never** substitute a heuristic script under an agent label.
- **Truthful Status Reporting**: DRC pass does not imply electrical validity. Successful DRC runs without independent LVS/connectivity checks are reported as `success_geometry_only`.
- **Immutable Inputs**: Input GDS layouts and DRC decks are strictly immutable. Each evaluation runs in a unique directory (`reports/runs/<case_name>_<timestamp>_<short_id>/`).

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
- Test suites in `tests/test_single_shot_pipeline.py` & `tests/test_patch_failures.py` exercise:
  - Single-shot execution across candidate modes (`script_file`, `heuristic`, `agent`).
  - Truthful artifact generation in `reports/runs/<run_id>/`.
  - Rejection of syntax errors, infinite loops, missing outputs, and destructive layouts (delete-all).

---

## 4. Directory Conventions
- `src/klayout_drc/`: Python package implementation.
- `knowledge/`: Markdown knowledge base files (`asap7_rules_guide.md`, `geometric_fix_techniques.md`, `klayout_api_patterns.md`).
- `test_data/layouts/`: Sample GDS files (`asap7_test.gds`, `asap7_fixed.gds`) and versioned fixtures (`legacy_mini_v2/`).
- `test_data/rules/`: DRC rule decks (`asap7_mini.drc`, `drc_ASAP7.lydrc`).
- `reports/`: Output directory for report databases (`.lyrdb`), textual reports (`.txt`), and isolated run bundles (`reports/runs/<run_id>/`).
- `docs/`: Architecture documents, staged implementation plans, and reference packages.
- `harness/`: Isolated DeepSeek Harness product bundle (`package.json`, `harness.product.json`, `scripts/`, `src/`, `profile/`).
