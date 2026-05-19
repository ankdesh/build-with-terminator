## Why

The CLI workflow execution engine requires sample workflows to validate its functionality and provide a reference for users. These out-of-the-box examples will demonstrate how to construct instruction traces using the declarative YAML format and execute tasks like log parsing deterministically.

## What Changes

- Create a `workflows/` directory at the root of the project to house sample workflows.
- **Workflow 1 (`parse_and_get_templates.yaml`)**: A workflow that calls the `logparser` executor to `parse_templates` on a log (e.g. `datasets/loghub_raw_logs_2k/HDFS_2k.log`), and then calls `get_templates` to retrieve the identified log templates.
- **Workflow 2 (`extract_stats.yaml`)**: A second sample workflow demonstrating the use of the `stats` executor to extract statistics from a log and print/return them.

## Capabilities

### New Capabilities
- `sample-workflows`: Definition and inclusion of reference YAML workflows in the `workflows/` directory that demonstrate the orchestration of executors (`logparser` and `stats`) using datasets from the `datasets/` folder.

### Modified Capabilities

## Impact

- **Affected code**: Addition of new `.yaml` files in the `workflows/` directory. No core Python/C++ code will be modified.

