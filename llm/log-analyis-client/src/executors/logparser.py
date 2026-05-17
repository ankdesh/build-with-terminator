import ast
import os
from typing import Any

import pandas as pd
from logparser.Drain import LogParser

from executors.base import BaseExecutor


class LogparserExecutor(BaseExecutor):
    def __init__(self):
        self._parsed_df = None
        self._templates_df = None
        self._out_dir = "logparser_output"
        os.makedirs(self._out_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return "logparser"

    def capabilities(self) -> list[str]:
        return ["parse_templates", "get_templates", "query_parameters"]

    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        if action == "parse_templates":
            return self._parse_templates(args)
        elif action == "get_templates":
            return self._get_templates(args)
        elif action == "query_parameters":
            return self._query_parameters(args)
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _parse_templates(self, args: dict[str, Any]) -> dict[str, Any]:
        target_file = args.get("target_file")
        log_format = args.get("log_format")
        algorithm = args.get("algorithm", "drain").lower()

        if not target_file or not os.path.exists(target_file):
            raise ValueError("Invalid target_file")
        if not log_format:
            raise ValueError("log_format is required")

        if algorithm != "drain":
            raise ValueError(f"Unsupported algorithm: {algorithm}. Currently only 'drain' is supported.")

        # Drain specific parameters
        depth = args.get("depth", 4)
        st = args.get("st", 0.4)

        # logparser expects a log directory and log file name
        log_dir = os.path.dirname(os.path.abspath(target_file))
        if not log_dir:
            log_dir = "."
        log_file_name = os.path.basename(target_file)

        # Initialize parser
        parser = LogParser(log_format=log_format, indir=log_dir, outdir=self._out_dir, depth=depth, st=st)
        parser.parse(log_file_name)

        # Load the generated CSVs into memory
        structured_csv = os.path.join(self._out_dir, f"{log_file_name}_structured.csv")
        templates_csv = os.path.join(self._out_dir, f"{log_file_name}_templates.csv")

        if not os.path.exists(structured_csv) or not os.path.exists(templates_csv):
            raise RuntimeError("Parsing failed, output files not found.")

        self._parsed_df = pd.read_csv(structured_csv)
        self._templates_df = pd.read_csv(templates_csv)

        return {
            "status": "success",
            "total_templates_found": len(self._templates_df),
            "total_lines_parsed": len(self._parsed_df),
        }

    def _get_templates(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._templates_df is None:
            raise ValueError("No templates available. Call parse_templates first.")

        limit = args.get("limit", 10)
        sort_by = args.get("sort_by", "Occurrences")
        order = args.get("order", "desc")

        ascending = order.lower() == "asc"

        sorted_df = self._templates_df
        if sort_by in sorted_df.columns:
            sorted_df = sorted_df.sort_values(by=sort_by, ascending=ascending)

        top_n = sorted_df.head(limit)

        # Convert to a list of dicts
        templates = top_n.to_dict(orient="records")
        return {"status": "success", "templates": templates}

    def _query_parameters(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._parsed_df is None:
            raise ValueError("No parsed data available. Call parse_templates first.")

        event_id = args.get("event_id")
        if not event_id:
            raise ValueError("event_id is required")

        limit = args.get("limit", 50)

        filtered_df = self._parsed_df[self._parsed_df["EventId"] == event_id]
        limited_df = filtered_df.head(limit)

        # 'ParameterList' is stored as a string representation of a list
        parameters = []
        for param_str in limited_df["ParameterList"]:
            if pd.isna(param_str):
                continue
            try:
                # Safely evaluate the string to a python list
                parsed_list = ast.literal_eval(param_str)
                parameters.append(parsed_list)
            except (ValueError, SyntaxError):
                parameters.append([param_str])

        return {"status": "success", "event_id": event_id, "parameters": parameters}
