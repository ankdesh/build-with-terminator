## 1. Core Worker Implementation

- [x] 1.1 Create `stats_worker.py` and define the `StatsWorker` class implementing `WorkerBase`.
- [x] 1.2 Implement the `get_stats` capability to count the total lines and return the file size efficiently.
- [x] 1.3 Implement the `get_sample` capability to read and return the first `n` lines of a file without loading the entire file into memory.

## 2. Integration with Orchestrator

- [x] 2.1 Update `main.py` to import and register the `StatsWorker` in the Orchestrator's worker registry.

## 3. Testing and Verification

- [x] 3.1 Write a unit test `test_stats_worker.py` to verify `get_stats` computes correct line count and size.
- [x] 3.2 Add test cases to verify `get_sample` returns the exact requested number of lines, or all lines if `n` is greater than file length.
