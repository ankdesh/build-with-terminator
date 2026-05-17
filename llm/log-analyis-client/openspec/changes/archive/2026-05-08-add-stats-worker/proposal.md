## Why

We need a lightweight way to retrieve basic information and a preview sample from a log file without running heavy parsing algorithms. This allows the LLM Planner or the Orchestrator to quickly understand the size, format, and general characteristics of a log file before deciding on a more comprehensive analysis strategy.

## What Changes

- Introduce a new Python worker called `StatsWorker` implementing the unified `WorkerBase` interface.
- Add capability to compute and return general file statistics (e.g., total line count).
- Add capability to return a sample of lines from the log file. Based on a parameter `n` defined at initialization (or passed via instructions), it will return exactly `n` lines, or the total number of lines if the file is smaller than `n`.
- Register the new worker in the Orchestrator.

## Capabilities

### New Capabilities
- `log-statistics`: Capability to compute basic file statistics and return a restricted sample of lines from a log file.

### Modified Capabilities

## Impact

- **New Code**: A new worker file (`stats_worker.py`) will be created in the Python worker layer.
- **Orchestrator**: The Orchestrator's worker registry in `main.py` will be updated to instantiate and load the `StatsWorker`.
- **No Breaking Changes**: This is a purely additive feature and does not affect existing workers (like the C++ Scanner or the Logparser worker).
