## ADDED Requirements

### Requirement: Expose Parsed DataFrame
The `logparser` executor SHALL provide an action `get_parsed_info` to expose its internal parsed representations to the Orchestrator context.

#### Scenario: Orchestrator fetches parsed data
- **WHEN** the `get_parsed_info` instruction is dispatched to `logparser`
- **THEN** the executor returns a dictionary containing the full `df` (DataFrame object reference), `schema` (list of column names/types), and `templates` (dictionary of EventIds to EventTemplates).
