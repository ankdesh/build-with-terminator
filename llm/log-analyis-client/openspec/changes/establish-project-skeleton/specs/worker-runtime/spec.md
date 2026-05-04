## ADDED Requirements

### Requirement: CMake Build System
The system SHALL use CMake to compile C++ code into a shared library.

#### Scenario: Compilation
- **WHEN** `cmake` and `make` are run in the build directory
- **THEN** a `.so` file SHALL be produced
