## ADDED Requirements

### Requirement: Unified Worker execution
All worker modules MUST inherit from a `WorkerBase` class and implement a unified `execute` method that takes an action string and an arguments dictionary.

#### Scenario: Dispatching an instruction
- **WHEN** the Orchestrator receives a declarative JSON instruction
- **THEN** the Orchestrator routes the instruction to the appropriate worker's `execute` method

### Requirement: Worker Capability Discovery
All worker modules MUST implement a `capabilities` method that returns a list of action strings they support.

#### Scenario: Discovering capabilities
- **WHEN** the Orchestrator initializes or registers workers
- **THEN** the Orchestrator can query `worker.capabilities()` to understand which actions can be routed to that worker
