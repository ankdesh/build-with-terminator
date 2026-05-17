## Context

The system needs a lightweight way to quickly inspect log files before committing to heavy parsing tasks (like Drain). By retrieving general file stats (like line count and file size) and reading a small subset of lines, the Orchestrator or LLM Planner can make more informed decisions about how to proceed with log analysis. We will implement this as a new Python worker named `StatsWorker` that adheres to our unified `WorkerBase` interface.

## Goals / Non-Goals

**Goals:**
- Provide basic file metadata (e.g., total lines, size in bytes) without loading the entire file into memory.
- Allow querying an exact `n` number of lines from the file for preview.
- Ensure the worker seamlessly integrates with the `WorkerBase` unified interface.

**Non-Goals:**
- This worker will *not* perform any regex parsing, structuring, or semantic extraction of the logs.
- It will not support complex tailing or searching; it is meant strictly for basic stats and head-like previews.

## Decisions

- **File Reading Approach**: For getting the sample lines, we will read the file line-by-line up to `n` lines to avoid loading massive files into memory. For calculating total lines efficiently, we will iterate over the file in chunks or line-by-line counting, instead of using `readlines()`.
- **Worker Initialization**: The parameter `n` can be set at initialization to define a default preview size, but should also be configurable via the instruction arguments during the `execute` call for maximum flexibility.
- **Capabilities**: The worker will expose two primary actions:
    - `get_stats`: Returns total line count and file size.
    - `get_sample`: Returns the first `n` lines.

## Risks / Trade-offs

- **Performance on Extremely Large Files**: Counting lines on multi-gigabyte files in pure Python can take a few seconds. 
  - *Mitigation*: Since this is for initial reconnaissance, a few seconds is acceptable. If it becomes a bottleneck, we could optimize it later or use the C++ worker for basic stats.
