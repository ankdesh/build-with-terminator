## ADDED Requirements

### Requirement: Application Entry Point
The system SHALL provide a Python entry point (`main.py`).

#### Scenario: App Launch
- **WHEN** `python main.py` is run
- **THEN** it SHALL print a confirmation and exit

### Requirement: C++ Extension Loading
The system SHALL be able to load a C++ extension module compiled via `pybind11`.

#### Scenario: Call C++ from Python
- **WHEN** Python imports the extension and calls a test function
- **THEN** the C++ function SHALL return a "Hello" string
