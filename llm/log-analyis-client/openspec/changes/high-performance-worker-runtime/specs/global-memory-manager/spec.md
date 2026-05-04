## ADDED Requirements

### Requirement: Unified Memory Access
The system SHALL map log files exactly once via the GMM and provide zero-copy access to all tools.

#### Scenario: Shared Mapping
- **WHEN** multiple tools request the same file
- **THEN** they SHALL receive handles to the same memory mapping
