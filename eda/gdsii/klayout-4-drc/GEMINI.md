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
  - `src/klayout_drc/deck_extractor.py` (`DRCDeckExtractor`): XML macro unbundling and entity decoding with line provenance.
  - `src/klayout_drc/rule_catalog.py` (`DRCRuleCatalog`, `DRCRuleDefinition`): Audited rule catalog indexing constraints, layers, and upstream anomalies.
  - `src/klayout_drc/marker_geometry.py` (`MarkerGeometry`, `EdgePairMarker`, etc.): Strongly typed RDB violation marker representations.
  - `src/klayout_drc/parser.py` (`DRCParser`): Parsing `.lyrdb` violation databases into strongly typed models.
  - `src/klayout_drc/reporter.py` (`DRCReporter`): Generating formatted human-readable textual reports.
  - `src/klayout_drc/drc_context.py` (`DRCContextProcessor`): Extracting matching rule blocks and constraints from DRC decks.
  - `src/klayout_drc/gds_context.py` (`GDSContextProcessor`): Hierarchical windowed extraction of layout geometry with instance transforms.
  - `src/klayout_drc/knowledge_loader.py` (`KnowledgeLoader`): Merging domain knowledge base markdown documents.
  - `src/klayout_drc/fixer.py` (`DRCFixer`): Deterministic geometric polygon repair with KLayout Region operations.
  - `src/klayout_drc/repair_executor.py` (`RepairExecutor`): Out-of-process subprocess execution of repair patches with timeout and log capture.
  - `src/klayout_drc/validator.py` (`LayoutValidator`): Layout integrity validation (DBU, top-cell, BEOL layer scope, master-cell immutability).
  - `src/klayout_drc/layout_diff.py` (`LayoutDiffCalculator`): Per-layer geometric diffing (added/removed areas).
  - `src/klayout_drc/run_manifest.py` (`RunManifestManager`, `RunSpec`, `RunPaths`): Input snapshotting, hashing, environment capture, and run directory isolation.
  - `src/klayout_drc/run_reporter.py` (`RunReporter`): Before/after comparison, typed status assignment, and audit report generation.
  - `src/klayout_drc/single_shot.py` (`SingleShotOrchestrator`): Chaining the single-shot `Fix → Apply Patch → Report` pipeline.
  - `src/klayout_drc/benchmark/types.py`: Benchmark data contracts (`BenchmarkCaseSpec`, `DifficultyTier`, `BenchmarkVerdict`, `EvaluationResult`, `BenchmarkSummary`).
  - `src/klayout_drc/benchmark/manifest.py` (`BenchmarkManifestManager`): Manifest serialization, query filtering, and SHA-256 integrity verification.
  - `src/klayout_drc/benchmark/mutations.py`: Geometric shape operators for synthetic BEOL layout generation.
  - `src/klayout_drc/benchmark/generator.py` (`BenchmarkGenerator`): Seeded deterministic layout generation across the 100 benchmark cases.
  - `src/klayout_drc/benchmark/evaluator.py` (`BenchmarkEvaluator`): Batch execution orchestrator for benchmark evaluation.
  - `src/klayout_drc/benchmark/scorer.py` (`BenchmarkScorer`): Metric calculation, verdict classification, regression detection, and report generation (`.json`, `.csv`, `.md`).
  - `src/klayout_drc/cli.py`: Unified CLI supporting granular node modes, end-to-end evaluation (`--mode single-shot`), and benchmark suite operations (`benchmark-list`, `benchmark-verify`, `benchmark-generate`, `benchmark-evaluate`).
- **Fail Early & Explicitly**: Never let errors fail silently. Use dedicated exceptions (`DRCConfigurationError`, `DRCExecutionError`, `DRCParserError`).
- **No Silent Fallback**: In `mode=agent`, an LLM failure must produce `model_error` and exit explicitly; it must **never** substitute a heuristic script under an agent label.
- **Truthful Status Reporting**: DRC pass does not imply electrical validity. Successful DRC runs without independent LVS/connectivity checks are reported as `success_geometry_only`.
- **Immutable Inputs**: Input GDS layouts and DRC decks are strictly immutable. Each evaluation runs in a unique directory (`reports/runs/<case_name>_<timestamp>_<short_id>/`).

---

## 3. Testing Strategy
- Prioritize end-to-end integration tests over isolated unit tests.
- Maintain a balanced testing pyramid: unit tests for parsing/extraction and integration tests for end-to-end evaluation.
- Test suites exercise:
  - `tests/test_drc_pipeline.py`: Detection of violations, automated healing, context processors, CLI granular modes.
  - `tests/test_single_shot_pipeline.py`: Single-shot pipeline (`script_file`, `heuristic`, `agent`) and artifact generation.
  - `tests/test_patch_failures.py`: Rejection of syntax errors, infinite loops, missing outputs, delete-all, and edit scope violations.
  - `tests/test_asap7_profiles.py`: Multi-profile registry (`legacy_mini`, `asap7_curated`, `asap7_public_full`) and parameter adapters.
  - `tests/test_rule_catalog.py`: XML deck extraction, entity decoding, constraint cataloging, and upstream anomaly tracking.
  - `tests/test_marker_geometry.py`: Strongly typed RDB markers (`EdgeMarker`, `EdgePairMarker`, `PolygonMarker`, `BoxMarker`).
  - `tests/test_gds_hierarchy_context.py`: Hierarchical layout context windowing with complex instance transformations.
  - `tests/test_asap7_rule_boundaries.py`: 5 BEOL rule families across 4-case boundary matrix (20 testcases) + compound interaction.
  - `tests/test_phase_b_single_shot.py`: Single-shot agent and script evaluation under authentic ASAP7 profiles.
  - `tests/test_benchmark_manifest.py`: Schemas, serialization, filtering, and cryptographic SHA-256 integrity checks.
  - `tests/test_benchmark_generation.py`: 100-case generation, exact tier/rule distributions, and live DRC oracle verification.
  - `tests/test_benchmark_pipeline.py`: Benchmark evaluator execution, scoring engine, and CLI integration.

---

## 4. Directory Conventions
- `src/klayout_drc/`: Python package implementation.
- `src/klayout_drc/benchmark/`: Synthetic benchmark suite implementation (generator, manifest, evaluator, scorer).
- `knowledge/`: Markdown knowledge base files (`asap7_rules_guide.md`, `geometric_fix_techniques.md`, `klayout_api_patterns.md`).
- `test_data/layouts/`: Sample GDS files (`asap7_test.gds`, `asap7_fixed.gds`), versioned legacy fixtures (`legacy_mini_v2/`), and BEOL boundary fixtures (`asap7_beol_v1/`).
- `test_data/benchmark_v1/`: Authentic 100-case BEOL benchmark suite (`manifest.json` and `cases/*.gds`).
- `test_data/rules/`: DRC rule decks (`asap7_mini.drc`, `asap7_curated.lydrc`, `asap7.lydrc`).
- `reports/`: Output directory for report databases (`.lyrdb`), textual reports (`.txt`), and isolated run bundles (`reports/runs/<run_id>/`).
- `docs/`: Architecture documents, staged implementation plans, and evaluation reports (`docs/reports/`).
- `harness/`: Isolated DeepSeek Harness product bundle (`package.json`, `harness.product.json`, `scripts/`, `src/`, `profile/`).
