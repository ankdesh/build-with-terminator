## 1. Setup and Abstraction

- [x] 1.1 Create `worker_base.py` and define the `WorkerBase` abstract class with `name`, `capabilities`, and `execute` methods.
- [x] 1.2 Refactor the existing C++ Scanner logic into a `CppScannerWorker` class that implements `WorkerBase`.
- [x] 1.3 Add `logparser` as a project dependency (e.g. `uv add logparser`).

## 2. Python Logparser Worker Implementation

- [x] 2.1 Create `logparser_worker.py` and define the `LogparserWorker` class inheriting from `WorkerBase`.
- [x] 2.2 Implement the `parse_templates` instruction logic to run the Drain algorithm and store the results in memory.
- [x] 2.3 Implement the `get_templates` instruction logic to return the top N templates sorted by frequency.
- [x] 2.4 Implement the `query_parameters` instruction logic to return the extracted parameter lists for a specific event ID.
- [x] 2.5 Hook up the `LogparserWorker` to the Orchestrator's execution loop.

## 3. Testing and Verification

- [x] 3.1 Write a unit test to verify `WorkerBase` dispatch logic.
- [x] 3.2 Write a unit test for `LogparserWorker` parsing a sample log file and executing query instructions.
- [x] 3.3 Verify the end-to-end flow: the Orchestrator successfully dispatches JSON instructions to `LogparserWorker`.
