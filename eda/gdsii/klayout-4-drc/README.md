# Programmatic DRC with KLayout & DeepSeek Harness Flow

This repository provides an automated, programmatic pipeline for executing Design Rule Checking (DRC) on GDSII layouts using KLayout, generating structured intermediate violation databases (`.lyrdb`), creating human-readable textual reports, and exposing the entire workflow as a reusable flow within the **DeepSeek Harness** (`dsh`) flow subsystem.

---

## Architecture Overview

The system is organized into two decoupled tiers:

1. **Python DRC Core (`src/klayout_drc/`)**:
   - Executes KLayout in headless batch mode (`klayout -b -r <deck> -rd input=<gds> -rd report=<lyrdb>`).
   - Parses the XML report database (`.lyrdb`) and extracts per-category violation counts and geometric coordinates (edge-pairs, boxes, polygons).
   - Produces formatted human-readable reports and machine-readable structured JSON summaries.
   - Provides programmatic geometric healing for ASAP7 M1/V1 violations using `klayout.db.Region` operations.

2. **Harness Flow Subsystem (`harness/`)**:
   - Implements a local DeepSeek Harness product bundle (`@klayout/harness-drc`).
   - Links to local DeepSeek Harness packages (`/home/ankdesh/explore/deepseek-harness`) without modifying the harness repository.
   - Registers the `klayout.gds_drc_flow` flow definition and `klayout.run_drc_and_report` operation.
   - Provides both a standalone CLI flow runner (`npm run flow:drc`) and product profile configurations for headless and interactive execution.

---

## Directory Structure

```
klayout-4-drc/
├── pyproject.toml                     # Python package & CLI configuration (uv)
├── uv.lock                            # Deterministic uv lockfile
├── GEMINI.md                          # Project constitution & design principles
├── README.md                          # This documentation
├── src/
│   └── klayout_drc/
│       ├── __init__.py                # Package exports
│       ├── config.py                  # Hoisted constants, paths, and exceptions
│       ├── runner.py                  # Headless KLayout batch process runner
│       ├── parser.py                  # Report database (.lyrdb) parser
│       ├── reporter.py                # Human-readable & structured reporter
│       ├── fixer.py                   # Automated layout repair logic
│       └── cli.py                     # Unified CLI entry point
├── test_data/
│   ├── layouts/
│   │   ├── asap7_test.gds             # Sample GDS with intentional violations
│   │   ├── asap7_fixed.gds            # Sample repaired GDS
│   │   └── create_sample_layout.py    # Generator for test layout
│   └── rules/
│       └── asap7_mini.drc             # ASAP7 7nm mini DRC deck
├── reports/                           # Output directory for generated reports
│   ├── drc_violations.lyrdb           # Intermediate KLayout report database
│   └── drc_report.txt                 # Formatted textual report
├── tests/
│   └── test_drc_pipeline.py          # End-to-end integration test suite
└── harness/                           # DeepSeek Harness integration bundle
    ├── package.json                   # Bundle package manifest
    ├── harness.product.json           # Harness product profile configuration
    ├── tsconfig.json                  # TypeScript configuration
    ├── scripts/
    │   ├── link-harness.mjs           # Safe compile-time symlink manager
    │   └── run-flow.mjs               # Standalone Flow CLI runner
    ├── profile/
    │   ├── cordis.patch.yml           # Cordis profile configuration
    │   └── catalog/
    │       └── flows/
    │           └── run_drc.yaml       # Declarative flow specification
    └── src/
        ├── index.ts                   # Cordis plugin entry point
        ├── drc-operations.ts          # Flow operation registration
        └── types.ts                   # Input/output schemas
```

---

## Quickstart & Usage

### 1. Python DRC Pipeline (`uv`)

Run the complete DRC check and generate textual reports directly via Python:

```bash
# Execute DRC on default sample layout
uv run klayout-drc

# Output structured JSON for machine integration
uv run klayout-drc --json

# Run against custom layout and rule deck
uv run klayout-drc --gds test_data/layouts/asap7_test.gds --deck test_data/rules/asap7_mini.drc

# Automatically repair violations and write healed GDS
uv run klayout-drc --gds test_data/layouts/asap7_test.gds --fix-output test_data/layouts/my_healed.gds
```

### 2. DeepSeek Harness Flow Execution

Run the flow through the Harness runtime from the project root or from `harness/`:

```bash
# From project root:
node harness/scripts/run-flow.mjs

# Or from harness/ directory:
cd harness
npm run flow:drc

# Execute flow with custom arguments:
node scripts/run-flow.mjs --gds ../test_data/layouts/asap7_fixed.gds
```

### 3. Run Automated Tests

Execute the end-to-end test suite verifying violation detection, report formatting, and automated healing:

```bash
uv run pytest
```

---

## Verification Results

### Initial Layout (`asap7_test.gds`)
```text
=== DRC Violations Details ===
Source: /home/ankdesh/explore/build-with-terminator/eda/gdsii/klayout-4-drc/reports/drc_violations.lyrdb

Rule: M1_W - M1 minimum width is 18nm
  -> 1 violation(s) found:
    Violation 1 (Cell: TOP):
      Edge pair: (0,0;0,0.1)|(0.01,0.1;0.01,0)

Rule: M1_S - M1 minimum spacing is 18nm
  -> 1 violation(s) found:
    Violation 1 (Cell: TOP):
      Edge pair: (0.13,0;0.13,0.1)|(0.12,0.1;0.12,0)

Rule: V1_M1_ENC - V1 minimum enclosure by M1 is 9nm
  -> 6 violation(s) found:
    Violation 1 (Cell: TOP):
      Edge pair: (0.218,0.018;0.218,0)/(0.218,0.018;0.218,0)
    ...
==============================
Total Violations: 8
```

### Repaired Layout (`asap7_fixed.gds`)
```text
=== DRC Violations Details ===
Source: /home/ankdesh/explore/build-with-terminator/eda/gdsii/klayout-4-drc/reports/fixed_drc_violations.lyrdb

No DRC violations found.

==============================
Total Violations: 0
```
