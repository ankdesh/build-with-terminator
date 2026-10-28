# Portable setup and evaluation handoff

The reference platform is Linux x86_64, Ubuntu 24.04. Keep the Git checkout and
its evidence bundle together when you transfer this project. Git contains code,
experiment definitions, and a small archive index. It does not contain the large
snapshot or bundle. Copy those files separately.

## Start on another machine

Install Python 3.12, uv, Node 22.23.2 (including its development headers), and pnpm 11.7.0. The locked versions and
Ubuntu packages are in `config/runtime-lock.json`. Node and pnpm must match these
versions. Set credentials in the shell only. Do not put credentials in TOML.
The Harness source requires access to its Git repository.

```sh
cp config/local.example.toml config/local.toml
# Edit local.toml if tools or data use other paths.
./scripts/drc setup --dry-run
./scripts/drc setup --system-packages
./scripts/drc doctor
```

`--system-packages` explicitly permits apt package installation. Without this
option, setup does not install system packages. Setup uses `uv sync --locked`,
installs the pinned Harness Node dependencies, builds its host runtime, links the
integration, and compiles the TypeScript package. The Harness checkout must be
clean and at commit `7388d01e24fa31ef47a5dcb8f9e71f1a488b0946`.
Use `[paths].harness` for an existing checkout. Otherwise setup clones it into
`.tools/deepseek-harness`. Setup does not change a supplied checkout to another
commit. The pinned source lock has a stale workspace dependency specifier. Setup
uses the retained `config/harness-pnpm-lock.yaml` during frozen installation and
restores the source lock in a `finally` block. Both lock hashes are pinned in
`config/runtime-lock.json`. Harness source files and its commit stay unchanged.
An interrupted process killed with SIGKILL can leave the install lock in place;
Git status then reports it and setup stops until the source lock is restored.
Package manager and Git errors remain visible. No model calls occur.

Engineers who need only restored evidence and reports can use:

```sh
./scripts/drc setup --python-only --system-packages
./scripts/drc doctor --reports-only
```

`doctor` checks actual headless image export, required fonts, runtime versions,
and the real candidate sandbox. CLI KLayout 0.28.16 and Python KLayout 0.30.8
serve different roles. Do not replace one with the other. A failed Bubblewrap
probe blocks candidate execution. Host user-namespace policy must allow the
sandbox; no unsandboxed fallback is provided.

The setup reference uses Python 3.12.3; other 3.12 patch releases are recorded.
The Python lock includes report dependencies Pillow, ReportLab, and pypdf.
PowerPoint creation does not form part of setup.

## Transfer the first snapshot

The first snapshot is `archives/2026-10-28`. It contains original files under
`root/`, a size and SHA-256 manifest, original absolute paths, dataset status,
and a manifest checksum. `archives/index.json` is the small Git index.
`reports/handoff_original_report_sources` retains the pre-port report builders.
Historical corrections remain in the original reports and correction documents.

```sh
./scripts/drc archive list
./scripts/drc archive verify --snapshot 2026-10-28
./scripts/drc archive pack --snapshot 2026-10-28 --bundle archives/2026-10-28.tar.gz
# Copy the .tar.gz AND its .sha256 sidecar to the destination machine.
./scripts/drc archive restore --bundle /transfer/2026-10-28.tar.gz --output archives/2026-10-28
./scripts/drc archive verify --snapshot 2026-10-28
```

A destination must not exist. Restore verifies the bundle checksum before
extraction, rejects unsafe paths and links, then verifies every evidence file.
Use `--sha256 HASH` instead of a sidecar if the checksum arrives separately.
The bundle and sidecar need a trusted transfer channel. The index manifest hash
can also be checked against the restored snapshot.

To create a later snapshot, use a new ID. Existing snapshots cannot be replaced.
Only `--move-reports` removes rendered PDFs, PPT, and report figures from their
old locations, after the copied snapshot passes verification. Working datasets,
campaign records, and report sources stay in place. Dependency trees, secrets,
tool checkouts, and ASIC build directories are excluded. Retained C2+C3 source
collateral and tool receipts remain available. PicoRV32 setup and baseline
summaries remain tracked; its large build outputs are outside this snapshot.
Later snapshots also include the configured data root and new evidence under
`work/runs` and `work/reports`. If those roots are outside the checkout, the
manifest records their original paths and maps them to `external/` in the
snapshot. The path resolver and dataset restore command use these mappings.

```sh
./scripts/drc archive create --snapshot YYYY-MM-DD --dry-run
./scripts/drc archive create --snapshot YYYY-MM-DD --move-reports
```

Python callers can use `klayout_drc.handoff.archive.Resolver(snapshot).resolve(path)`
to map an old absolute path to the copied file. The resolver does not change
historical records. Their original hashes remain valid.

## Restore and check datasets

```sh
./scripts/drc datasets list --snapshot archives/2026-10-28
./scripts/drc datasets restore --snapshot archives/2026-10-28 --output work/restored-data
./scripts/drc datasets verify --data-root work/restored-data
```

The primary checks cover all A/B fixtures, all 100 C1 entries and accepted
references/oracles, and all 50 accepted C2+C3 cases. Verification also requires
the qualified checker bytes and versions. Its installation path can differ.
The archive manifest checks every secondary dataset, including partial staging
files. The catalogue labels secondary datasets experimental; a complete
secondary generation does not become the accepted benchmark.

## Evaluate a new run

Every output directory must be new. `handoff_run.json` records resolved options,
dataset/source/tool identities, runtime versions, and the selected experiment.
Existing engine records retain deck hashes and per-case evidence. A model or
infrastructure failure stays visible. Dispatch and retry policies are unchanged.
A stopped campaign is not silently resumed or retried by this interface.

```sh
./scripts/drc evaluate --suite ab --profile legacy_mini --limit 1 --run-id ab-smoke
./scripts/drc evaluate --suite ab --profile asap7_curated --mode heuristic --run-id b-local
./scripts/drc evaluate --suite c1 --case m1_w1_iso_01 --mode heuristic --run-id c1-smoke
./scripts/drc evaluate --suite c2c3 --mode no_change --workers 1 --run-id c2c3-local
# Inspect a live command without a provider call:
./scripts/drc evaluate --suite c1 --mode agent --provider bedrock --model qwen.qwen3-coder-next --limit 1 --dry-run
# Optional live smoke. This can incur provider charges:
./scripts/drc evaluate --suite c1 --mode agent --provider bedrock --model qwen.qwen3-coder-next --limit 1 --run-id c1-live-smoke
```

Live requests require `--mode agent --provider openai|bedrock`. Credentials stay
in `OPENAI_API_KEY` or `AWS_API_KEY` as required by the existing integration.
`--model` sets the provider model; `--region` applies to Bedrock. Use
`--temperature` for an explicit sampling temperature. Omit it to keep the existing
provider/default settings.
C2+C3 agent campaigns require Bedrock and all 50 qualified cases. They reject
case filters and limits. `--allow-incomplete` applies only to local C2+C3
baselines. C1 supports case, rule, tier, and limit filters with 1 to 4 workers.
A/B supports case and limit filters. A/B and C1 also accept `script_file` mode
with `--candidate-script`. Use an absolute candidate-script path from other
working directories.

`experiments/historical.json` contains recorded campaign definitions and their
summary checksums. `--experiment ID` selects a historical corpus selection for
a **new** run. It does not rerun an old output directory. Agent mode must still
be explicit. Fresh service results need not match historical scores.

All commands resolve default paths from the repository root. Relative TOML
paths also start there. Relative `--config` and `--*-root` settings also start at the repository root.
Other explicit input/output CLI paths start at the caller's working directory. Precedence is CLI options, local TOML, project defaults.
Use `--config`, `--data-root`, `--work-root`, `--archive-root`, `--fonts-root`,
`--harness-root`, `--cpus`, `--workers`, `--memory-mb`, and `--timeout-seconds`
where shown by `--help`. Candidate memory is an address-space limit; CPU count
limits inherited affinity. Public diagnostic audits retain their 600-second
limit. Scored checks and workers default to 120 seconds. Changed resource
options describe new runs; they do not redefine historical results.

## Rebuild saved reports

```sh
./scripts/drc report --kind saved --snapshot archives/2026-10-28 --output work/saved-report
./scripts/drc report --kind all --snapshot archives/2026-10-28 --output work/visual-rebuild
./scripts/drc report --kind c1-quick --snapshot archives/2026-10-28 --output work/quick-review
```

The saved report command copies the recorded summaries and historical Markdown
and CSV files. It also exports a paired JSON/CSV comparison and a Markdown view
of the recorded aggregates, including the original denominators. It does not
invoke current scoring. Use repeated `--campaign` options for a smaller set. To report a fresh working
run, omit `--snapshot` and supply its path explicitly:

```sh
./scripts/drc report --campaign work/runs/c1-smoke --output work/c1-smoke-report
```

Without an explicit campaign, the default source is the dated historical
snapshot when it is present.
With a snapshot, campaign paths can be original absolute paths or snapshot-root
relative paths such as `reports/runs/c1_corrected_heuristic`.

Visual builders run in a new `workspace/` under the requested output directory.
They use copied report inputs and resolve old paths to retained evidence.
They preserve the existing scientific content, selections, and layouts. The
archive is verified before and after. PDFs can differ in creation metadata or
font/runtime rendering; page counts and reported values are the acceptance
checks. Original PDF/PPT files retain their archived hashes.

The original PowerPoint, figures, renderings, builder sources, and validation
receipts are archived. Its original builder uses the Codex presentation runtime.
Portable PowerPoint generation is deferred and is not needed for normal setup.

## Optional ASIC preparation

`./scripts/drc setup --with-asic` pulls the pinned ORFS image. Docker must already
be installed and usable. ASIC settings are separate in `[asic]`; this handoff
command prepares the image only. Use the existing scripts and resource options
in `flows/picorv32_asap7/README.md` to run synthesis through GDS. No ASIC build,
rule changes, repair changes, prompt tuning, scoring changes, or paid full
campaign is part of setup or report rebuilding.

## Checks

```sh
uv run --locked --extra test pytest -q
node harness/node_modules/typescript/bin/tsc -p harness/tsconfig.json --noEmit
node --test harness/tests/*.test.mjs
```

Unset provider credentials when running regression tests. Some pre-existing
integration tests can make live calls when credentials are present.
See `docs/HANDOFF_VALIDATION.md` for the checks actually run for this handoff,
including any environment limits. A second checkout path on the current Ubuntu
host is useful transfer validation; it is not a separate clean virtual machine.
