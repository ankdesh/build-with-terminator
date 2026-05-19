## Context

The workflow execution engine uses a declarative YAML format to define a deterministic sequence of instructions for log analysis. To help users understand how to construct these workflows, we need sample workflows demonstrating common patterns, such as parsing logs to extract templates and calculating basic statistics over a log dataset. The repository contains sample logs in `datasets/loghub_raw_logs_2k` which can be used as inputs for these workflows.

## Goals / Non-Goals

**Goals:**
- Provide clear, functional YAML examples of workflows.
- Demonstrate chaining instructions: parsing logs and then using `get_templates`.
- Demonstrate using the `stats` executor to extract log statistics.

**Non-Goals:**
- Creating complex, multi-layered workflows that cover every possible configuration of executors.
- Adding new executor capabilities.

## Decisions

- **Workflow location**: Place the sample YAML files in a `workflows/` directory at the root of the project. This makes them easily discoverable for new users.
- **Workflow contents**:
  - `workflows/parse_and_get_templates.yaml`: Uses `logparser` to `parse_templates` on a log file (e.g., `datasets/loghub_raw_logs_2k/HDFS_2k.log`), followed by `get_templates` with a limit to return the top templates.
  - `workflows/extract_stats.yaml`: Uses the `stats` executor to `get_stats` on a log file (e.g., `datasets/loghub_raw_logs_2k/Apache_2k.log`).
- **Log Source**: Utilize the `datasets/loghub_raw_logs_2k` directory that contains samples like `HDFS_2k.log` to provide out-of-the-box runnable examples.

## Risks / Trade-offs

- **Risk**: Hardcoded paths to datasets might fail if run from different directories.
  - **Mitigation**: Instruct users to run the client from the root repository directory where `datasets/` and `workflows/` paths are correctly resolved relative to the current working directory, or define the paths relative to the repository root.
