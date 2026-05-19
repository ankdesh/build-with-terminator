## 1. Directory Setup

- [x] 1.1 Create the `workflows/` directory at the root of the project if it doesn't already exist.

## 2. Implement Workflow 1

- [x] 2.1 Create `workflows/parse_and_get_templates.yaml` with an instruction list.
- [x] 2.2 Add the `logparser` executor instruction for `parse_templates` targeting a log like `datasets/loghub_raw_logs_2k/HDFS_2k.log` with `log_format: "<Date> <Time> <Pid> <Level> <Component>: <Content>"`.
- [x] 2.3 Add the `logparser` executor instruction for `get_templates` with a limit parameter.

## 3. Implement Workflow 2

- [x] 3.1 Create `workflows/extract_stats.yaml` with an instruction list.
- [x] 3.2 Add the `stats` executor instruction for `get_stats` targeting a log like `datasets/loghub_raw_logs_2k/Apache_2k.log`.

## 4. Verification

- [x] 4.1 Run the `parse_and_get_templates.yaml` workflow using the CLI and verify successful execution and output.
- [x] 4.2 Run the `extract_stats.yaml` workflow using the CLI and verify successful execution and output.

