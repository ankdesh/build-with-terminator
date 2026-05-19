## ADDED Requirements

### Requirement: Sample Parse and Get Templates Workflow
The repository SHALL provide a sample YAML workflow demonstrating how to parse a log file and retrieve its templates using the `logparser` executor.

#### Scenario: Parse and get templates
- **WHEN** the user executes the `parse_and_get_templates.yaml` workflow with a valid target log
- **THEN** the system executes the `parse_templates` instruction followed by the `get_templates` instruction successfully

### Requirement: Sample Extract Stats Workflow
The repository SHALL provide a sample YAML workflow demonstrating how to extract statistics from a log file using the `stats` executor.

#### Scenario: Extract log statistics
- **WHEN** the user executes the `extract_stats.yaml` workflow with a valid target log
- **THEN** the system executes the `get_stats` instruction and returns the log characteristics
