# workflow-templates

## Purpose
TBD: Core capability to store and resolve parameterized workflow templates from a predefined directory.

## Requirements

### Requirement: Predefined Workflow Templates Storage
The system SHALL store predefined workflow templates as parameterized YAML files inside an internal `workflow_templates/` directory.

#### Scenario: Read template from directory
- **WHEN** the interactive analysis agent requests a workflow template by name
- **THEN** the system reads and parses the corresponding YAML file from `workflow_templates/`
