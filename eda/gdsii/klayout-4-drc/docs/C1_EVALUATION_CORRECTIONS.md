# C1 evaluation corrections

C1 delivered working infrastructure. The earlier completion reports did not
establish reliable benchmark scoring. The corrected acceptance gate includes
validation rejection, exact mode selection, checker evidence, and reproducible
model provenance.

## Corrected contracts

Result schema 2 preserves absent observations as null. It records requested and
actual candidate mode, pipeline verdict, benchmark outcome, validation level,
failure stage, preservation results, and marker comparison. Clean inputs receive
`clean_unchanged` or `unnecessary_edit`, rather than repair credit. Rejected
patches, checker errors, model errors, oracle mismatches, and blocked runs are
separate outcomes. Only completed, validated, checker-clean dirty cases count as
`clean_success`. This means geometry success within the curated scope.

Marker matching compares the same rule and checker-cell coordinate frame. It
uses canonical exact geometry, then mutual unique bounding-box matches within
one manufacturing-grid step. Unparsed or nonunique matches remain ambiguous.
A new unmatched marker or any per-rule count increase is a regression. These
conservative matching rules do not establish electrical correctness.

The selected profile supplies physical layers and units. Rule context uses the
XML extractor and audited catalog, including all branches of reused categories.
Area constraints retain area units. Local geometry keeps physical precision and
reports omitted windows and shape caps. Polygon vertices and holes are retained.

The Python orchestrator is the evaluation entry point. The standalone harness
runner is the canonical synthesis entry point. The declarative flow uses the
same shared request function. There is one request per attempt, with no feedback,
retry, or heuristic fallback. The runner inherits the orchestrator's Python
interpreter, so it does not depend on a Snap `uv` subprocess.

## Execution boundary

The worker requires Linux Bubblewrap user, PID, mount, and network namespaces.
It mounts only the system runtime, the selected virtual environment, input,
script, trusted worker policy, and private output directory. It receives a small
explicit environment without credentials. Inputs and runtime are read-only.

Limits are 120 seconds wall time and CPU, 2 GiB address space, 64 threads,
64 MiB output, 1 MiB logs, and 16 MiB temporary storage. A seccomp policy permits
threads but rejects new processes and namespaces. This keeps candidate memory
within one address space. Missing Bubblewrap, namespace support, libseccomp,
or runtime imports block execution before model synthesis. There is no
unrestricted execution fallback. Inputs and deck hashes are checked afterward.

Validation uses recursive physical geometry. It compares protected master
contents and protected instance definitions, including placements. It accepts
instance-only top cells. Per-case component and protected-region constraints
apply before after-DRC scoring. Multiple or conflicting top cells are rejected;
the pinned deck must check the same unique top used by the evaluator.

## Dataset and experiment

Release 1.1.0 keeps the existing 100 GDS cases and five categories. See the
dataset README for legal-reference construction, accepted evidence, and limits.
No enclosure coverage, C2/C3 inputs, or full electrical validation is added.

The campaign runs one attempt per entry for the frozen assisted model and one
for the unchanged heuristic comparator. Up to four independent entries can run
at once. The first model entry checks infrastructure before further dispatch.
A preflight or synthesis failure there blocks the remaining entries without
sending model requests for them. Resume uses saved per-case results. An
interrupted claim without a completed result requires inspection; it is never
retried automatically. An exclusive campaign lock prevents concurrent dispatch.

Campaign identity includes source, manifest, model, temperature, profile, mode,
case list, and comparator script. Changing these requires a new campaign output
directory. The campaign saves source contents once, and each run records source
hashes, tool/package versions, exact request, raw response, returned model,
rationale, usage, stage logs, artifact hashes, and null cost when no verified
price is available. Credentials are never included in saved request headers.

Report repair success over the 78 dirty entries and report the 22 clean controls
separately. Report by category, tier, and duplicate group. These are descriptive
development results. One attempt per entry cannot establish model consistency,
held-out generalization, electrical repair validity, or population success rates.

## Reproduce

Run from the project root, on a host that permits Bubblewrap namespaces:

```bash
uv run pytest -q
node harness/node_modules/typescript/bin/tsc --noEmit -p harness/tsconfig.json
node --test harness/tests/baseline-contract.test.mjs
uv run python -m klayout_drc.cli --mode benchmark-verify --json
```

Live API tests require `KLAYOUT_DRC_RUN_LIVE_TESTS=1` plus explicit model and API
credentials. Ordinary tests use mocked model requests or test missing credentials.
They do not send paid requests merely because an API key is present.

```bash
OPENAI_MODEL=gpt-6-luna uv run python -m klayout_drc.cli \
  --mode benchmark-evaluate --candidate-mode agent \
  --benchmark-output reports/runs/c1_corrected_agent
uv run python -m klayout_drc.cli \
  --mode benchmark-evaluate --candidate-mode heuristic \
  --benchmark-output reports/runs/c1_corrected_heuristic
```

If Snap `uv` cannot start in a restricted session, the same installed project
virtual environment can run `python -m pytest` or `python -m klayout_drc.cli`.
The OS namespace gate still applies. A blocked tool or model is not a pass.

## AWS Bedrock candidate provider

The shared synthesis contract supports `openai` (default) and `bedrock`. Select
Bedrock explicitly. Its API key comes from `AWS_API_KEY`, matching the local
`bedrock.py` example. Set the key in the process environment before launch; do
not put it in a command argument, source file, or report. The selected Bedrock
model must be available to the account in the selected region.

```bash
# AWS_API_KEY must already be set in the process environment.
export KLAYOUT_DRC_MODEL_PROVIDER=bedrock
export BEDROCK_REGION=ap-southeast-2
export BEDROCK_MODEL='<approved Bedrock model ID>'
# Optional: export BEDROCK_TEMPERATURE=0
.venv/bin/python -m klayout_drc.cli \
  --mode benchmark-evaluate --candidate-mode agent \
  --benchmark-output reports/runs/c1_bedrock_agent
```

The endpoint is
`https://bedrock-runtime.ap-southeast-2.amazonaws.com/openai/v1/chat/completions`
for this region. Requests use bearer authentication and the same JSON candidate
contract as the direct OpenAI provider. HTTP redirects are rejected. There are
no automatic retries or provider fallbacks. Bedrock never uses `OPENAI_API_KEY`,
`OPENAI_MODEL`, or `OPENAI_TEMPERATURE` as substitutes for its own settings.

Campaign identity and generation manifests record provider, endpoint, region,
model, and temperature without credentials. Python reads these settings through
the same Node configuration module that sends the request. Use a new campaign
directory when changing provider, region, model, or source. The earlier blocked
OpenAI campaign and its payload review remain historical records; their payload
hashes and destination approval do not describe a Bedrock campaign.

Before dispatch, confirm the model and credential source and prepare the payload
review for the selected AWS destination. Test the first case before dispatching
remaining entries. A model or infrastructure failure stops further dispatch as
specified above. All results remain geometry-only within the curated scope.

AWS documents the endpoint and bearer API key format in
[Chat Completions API](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html).

## Verified KLayout Python API guidance

Candidate knowledge includes an executable API reference from
`src/klayout_drc/api_reference.py`. The generated, self-contained document is
`knowledge/klayout_api_patterns.md`. It covers layout I/O, geometry types, call
arguments and return types, units, mutation behavior, selection/check markers,
safe component replacement, and hierarchical access/transformations. Its size
is limited to 18,000 characters, including examples and official source links.
Every published call contract has executable behavior checks.

The knowledge loader includes this complete canonical document exactly once,
even when a custom knowledge directory has no API document or a stale copy.
The Markdown file is generated for standalone reading; runtime prompt content
comes from the same verified renderer. The prompt and repair guide refer to
this document instead of maintaining another copy of API signatures.

Regenerate the Markdown after changing canonical contracts or examples:

```bash
.venv/bin/python -m klayout_drc.api_reference --format markdown > knowledge/klayout_api_patterns.md
```

The default reference command still returns JSON. Tests require the generated
file to equal the renderer's output and enforce the size limit.

The reference is checked against the installed Python KLayout binding before
agent synthesis. Checks execute only fixed package examples on synthetic
geometry; Markdown and generated candidates are never executed by this gate.
Each check asserts returned values or geometry. API-name checks alone are not
sufficient because Python overloads can accept arguments with another meaning.
The reference context records the runtime version and its SHA-256 digest.
Generation manifests also record reference metadata, and the existing context
hash covers the exact reference text sent to the model.

Both standalone and declarative synthesis use the same reference gate. They use
`KLAYOUT_DRC_PYTHON` when set, otherwise the project virtual environment if it
exists. The Python orchestrator supplies its own interpreter. Missing runtimes,
failed examples, and stale reference text stop dispatch. The benchmark records
reference failures as `blocked`, without a model attempt or heuristic fallback.

Verify locally without model credentials:

```bash
.venv/bin/python -m klayout_drc.api_reference
.venv/bin/python -m pytest -q tests/test_api_reference.py
node harness/tests/api-reference.test.mjs
```

For a fresh comparison with the original ten-case Bedrock pilot, load the AWS
environment and use a new output directory:

```bash
.venv/bin/python scripts/run_c1_bedrock_pilot.py \
  --compare-to reports/runs/c1_bedrock_pilot10_20261027 \
  --output reports/runs/<new-comparison-directory>
```

Before any model request, comparison mode requires the original ten case IDs,
five dirty inputs and five clean controls, matching model/provider/region/
temperature, profile, deck hash, dataset manifest hash, and case geometry hashes.
It also requires completed original responses. Original artifacts remain intact.
The runner saves baseline hashes and its own source alongside the new campaign.
There is one attempt per entry, with no automatic retry or expansion to 100.
