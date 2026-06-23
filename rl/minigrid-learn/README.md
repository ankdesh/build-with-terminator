# MiniGrid RL Learning Lab

An experiment-first project for learning reinforcement learning one concept at a
time. Phase 1 establishes reproducible single-environment PPO baselines on:

- `MiniGrid-Empty-8x8-v0`
- `MiniGrid-Dynamic-Obstacles-8x8-v0`

The architecture keeps environment creation, policy features, training,
evaluation, metrics, and reporting separate so later phases can introduce
vectorized workers, intrinsic rewards, recurrence, and curricula without
rewriting the baseline.

## Setup with uv

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

Create the project-local `.venv` and install the locked dependencies:

```bash
uv venv
uv sync
```

`uv sync` normally creates `.venv` itself; the explicit `uv venv` command makes
the environment setup visible for learning purposes.

## Validate the pipeline

```bash
uv run pytest
uv run ruff check .
uv run minigrid-learn smoke
```

The smoke run trains briefly, evaluates, saves and reloads a model, and writes
artifacts under `artifacts/phase1/smoke/`.

## Run Phase 1

Run all six environment/seed experiments:

```bash
uv run minigrid-learn train --all
```

Run or resume investigation with a shorter explicit budget:

```bash
uv run minigrid-learn train --env empty-8x8 --seed 0 --timesteps 100000
```

Regenerate the tracked GitHub report from saved metrics:

```bash
uv run minigrid-learn report
```

Open TensorBoard:

```bash
uv run tensorboard --logdir artifacts/phase1
```

The generated report is [`reports/phase1/phase1_report.md`](reports/phase1/phase1_report.md).
Its plots and compact source data are tracked; large models, checkpoints, and
TensorBoard event files are intentionally ignored.

## Reproducibility and stopping

Configuration lives in [`configs/phase1.toml`](configs/phase1.toml). Each run
copies its effective configuration into its artifact directory. Training stops
after three consecutive deterministic evaluations meet the environment reward
threshold, or after 500,000 environment steps. A maximum-step result remains a
valid observation and is never mislabeled as convergence.

Evaluation uses 20 episodes and a seed offset of 10,000 to avoid evaluating the
same random stream used for training. PyTorch, NumPy, Python, Gymnasium, and the
action space are seeded.

## Troubleshooting

- If `uv` is not found after installation, run
  `export PATH="$HOME/.local/bin:$PATH"` or restart the shell.
- On machines without CUDA, SB3 automatically uses CPU.
- The custom `MiniGridCNN` is required because SB3's default NatureCNN expects
  images larger than MiniGrid's 7×7 symbolic observation.
- If an experiment is interrupted, completed CSV rows and checkpoints remain
  available. Starting the same run again replaces its metric CSVs and writes a
  fresh final summary.

