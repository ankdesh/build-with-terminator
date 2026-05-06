# Capability: log-parsing

## Purpose
TBD: Ability to run structure-extraction algorithms on log files and query the resulting templates and parameters.

## Requirements

### Requirement: Parse templates from logs
The system MUST be able to parse log files using the Drain algorithm to extract log templates and structured parameters.

#### Scenario: Successful full-file parsing
- **WHEN** the `parse_templates` instruction is dispatched to the `LogparserWorker` with a target file and log format
- **THEN** the worker reads the file, extracts the templates, and stores the resulting structured data in memory

### Requirement: Query top templates
The system MUST allow querying the most frequent log templates after parsing is complete.

#### Scenario: Requesting top templates
- **WHEN** the `get_templates` instruction is dispatched with a limit `N`
- **THEN** the worker returns a list of the top `N` templates sorted by frequency

### Requirement: Query parameters for specific event
The system MUST allow querying the exact extracted parameters for a given template ID.

#### Scenario: Requesting parameters
- **WHEN** the `query_parameters` instruction is dispatched with an `event_id`
- **THEN** the worker returns the extracted parameter lists for lines matching that event
