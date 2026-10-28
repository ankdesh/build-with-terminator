# Source and verification receipts

`toolchain.json` records the ORFS source pins, official image digest, actual tool versions and binary hashes, and ASAP7 collateral hashes. `source_bundles.json` identifies the selected local build directories. `stress_selection.json` records the measured stress trials. `build_receipts/` retains complete and failed flow attempts; a receipt is complete only when its status says so.

The selected builds retain GDS, DEF, ODB, netlist, SDC, configuration, logs, metrics, and net ownership catalogs under the local `output/c2c3/toolchain/builds/` directories. Receipt hashes verify these artifacts. The source bundle paths are relative to the project root.

`qualification/` contains the 24 boundary fixtures and checker reports. All legal fixtures have zero scored markers. `reproducibility.json` compares two independently generated 50-case corpora. Two public report files differ in item order; canonical markers agree. `verification.json` states the test results and their scope.

`obstacle_audit.json` verifies the L3/L4 gate with actual polygon intersections.
`control_scope_audit.json` verifies that all ten clean controls have zero native
scored markers. Public deck observations remain separate.

Private reference layouts, mutation recipes, and expected actions remain under `../oracle/`. Neither the model nor the candidate worker receives that directory.
