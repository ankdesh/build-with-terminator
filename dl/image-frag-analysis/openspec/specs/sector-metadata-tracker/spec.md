# Capability: Sector Metadata Tracker

## Purpose
The system SHALL provide enhanced lineage tracking for generated sectors, ensuring that fragment-level grouping and sequential offsets are preserved and verifiable.

## Requirements

### Requirement: Enhanced Lineage Tracking
The system SHALL extend the metadata tracking to include fragment-level grouping, allowing users to identify which sectors belong to the same contiguous fragment.

#### Scenario: Fragment grouping in metadata
- **WHEN** inspecting the `metadata.csv`
- **THEN** sectors belonging to the same fragment MUST share the same `fragment_id` and have sequential `offset_in_original` values.
