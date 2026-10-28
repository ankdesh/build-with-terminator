# Handoff validation: 2026-10-28

The reference host and the clean test container use Ubuntu 24.04 on x86_64.
The checks made no live model requests. The credentialed smoke test remains
optional. The DRC rules, repair logic, prompts, scores, and retry policies were
not changed.

## Results

| Check | Result |
|---|---|
| Full Python regression suite | 280 passed; 1 credentialed test skipped |
| Final focused handoff and visual-guide checks | 37 passed, including alias paths and combined case/limit options |
| TypeScript type check | Passed |
| Node contract/reference tests | Both files passed; direct execution passed all 7 tests |
| Complete setup in a different checkout path | Passed, including locked dependencies and clean pinned Harness build |
| Clean Ubuntu system/Python setup | Passed without the original home directory or Codex dependency cache |
| Clean Ubuntu headless export, fonts, and versions | Passed |
| Clean Ubuntu archive and dataset verification | Passed |
| Clean Ubuntu candidate sandbox and C1 heuristic smoke | Passed with the outer Docker namespace permissions described below |
| Local A/B and C1 heuristic smoke runs | Passed |
| C2+C3 no-change evaluation on restored inputs | All 50 cases completed; all 50 public audits completed; 0 model requests |
| Restored C1 data | All 100 entries passed integrity and acceptance-evidence checks |
| Restored C2+C3 data | All 50 accepted entries passed integrity and qualification checks |
| Archive pack/restore at a different path | All 15,449 files verified; manifest checksum unchanged |
| Historical C2+C3 comparison and failure analysis | Comparison JSON/CSV, accounting JSON, and failure CSV matched recorded outputs |
| PDF rebuild in the relocated checkout | All 10 PDFs matched original page counts and extracted text |
| Original finished media | All original PDF/PPT hashes remained unchanged |
| Interrupted creation, collisions, unsupported options | Focused checks passed; originals stayed intact |
| Configured external data/work roots and fresh-result reporting | Focused checks passed |

The PDF page counts are 15 for the C1 guide, 2 for its quick review, 4 for the
Bedrock review, 25 for the C2+C3 atlas, 5 for each of its five level PDFs, and 10
for the selected-case review. Representative regenerated pages were rendered
with Poppler and inspected. Original media remain in the dated archive.

The restored no-change baseline reproduced every historical per-case verdict
and pass flag. It passed all 10 clean controls and all 10 no-edit controls. It
made no repairs to the 30 repair cases, as expected. Timings from these checks
must not be used for performance comparisons; other checks ran concurrently.

The machine-readable receipt is
[`handoff/2026-10-28-validation.json`](handoff/2026-10-28-validation.json).
It records archive/bundle checksums, runtime pins, original media hashes, PDF
checks, historical-report checks, and the restored baseline outcomes.

## Environment details and limits

Full Harness installation and build were tested in an independent checkout at
a different path, using commit `7388d01e24fa31ef47a5dcb8f9e71f1a488b0946`.
The checkout used independent Git objects and remained clean. The retained
install lock corrects workspace links; it adds or removes no external package
versions. The source lock is restored after installation, including on failure.

The clean Ubuntu container installed system packages and locked Python
packages. It used the separately prepared, pinned Harness checkout through a
read-only mount, then built its own integration. Tool and data paths inside the
container used `/workspace`, `/opt`, and `/evidence`. Its Python environment was
created in the container. It did not use the Codex document runtime.

Docker's default namespace and proc restrictions block a nested Bubblewrap
probe. The successful test used `NET_ADMIN` and `SYS_ADMIN` in the outer test
container, with Docker seccomp, AppArmor, and system-path masking set to
unconfined. Evidence and Harness mounts remained read-only. The candidate
worker still used its original namespaces, policy, resource limits, and
capability drop. No candidate-sandbox fallback was added. Normal native Linux
use does not require Docker. Run `doctor` on each destination machine.

These checks cover a separate checkout and a clean Ubuntu container. They do
not claim tests on every Linux distribution or on a separate physical machine.
OpenROAD image preparation remains optional; the ASIC flow was not rerun for
this handoff. PowerPoint generation remains deferred. Its original bytes,
figures, builder sources, and receipts were preserved.

The initial snapshot preserves the evidence present when preservation started.
New validation runs stay under the ignored `work/` tree. Later snapshots include
new evaluation and report outputs from the configured work root.
