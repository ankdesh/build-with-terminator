# Capability: log-statistics

## Purpose
TBD: Ability to retrieve general metadata and sample logs from a log file efficiently.

## Requirements

### Requirement: Get General File Statistics
The system MUST allow retrieving general metadata about a log file without full analysis.

#### Scenario: Requesting general statistics
- **WHEN** the `get_stats` instruction is dispatched to the `StatsWorker` with a target file
- **THEN** the worker reads the file efficiently and returns the total line count and the file size in bytes

### Requirement: Get Preview Sample
The system MUST provide a way to sample exact `n` lines from a log file.

#### Scenario: Requesting a file preview
- **WHEN** the `get_sample` instruction is dispatched with a target file and an optional `limit` parameter `n`
- **THEN** the worker reads and returns exactly the first `n` lines from the file

#### Scenario: File is smaller than the requested limit
- **WHEN** the `get_sample` instruction is dispatched with a target file and a `limit` parameter `n`
- **AND WHEN** the total line count of the file is less than `n`
- **THEN** the worker reads and returns all the lines in the file
