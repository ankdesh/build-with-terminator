# template-extractor Specification

## Purpose
TBD - created by archiving change llm-analysis-workflow. Update Purpose after archive.
## Requirements
### Requirement: Expose Parsed DataFrame
The `template_extractor` executor SHALL provide an action `get_parsed_info` to expose its internal parsed representations to the Orchestrator context.

#### Scenario: Orchestrator fetches parsed data
- **WHEN** the `get_parsed_info` instruction is dispatched to `template_extractor`
- **THEN** the executor returns a dictionary containing the full `df` (DataFrame object reference), `schema` (list of column names/types), and `templates` (dictionary of EventIds to EventTemplates).

