## ADDED Requirements

### Requirement: Multi-core Slab Scanning
The system SHALL divide files into slabs and scan them in parallel.

#### Scenario: 10GB Search
- **WHEN** a search is initiated on a 10GB file
- **THEN** it SHALL be processed by multiple threads in parallel

### Requirement: Search Interruption
The system SHALL support immediate cancellation of search tasks.

#### Scenario: User Stop
- **WHEN** a stop signal is received
- **THEN** all scanning threads SHALL exit within 100ms
