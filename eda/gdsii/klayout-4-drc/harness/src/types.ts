import type { JsonSchemaNode } from "@deepseek-ai/dsh-tools";

export interface DrcFlowInputs {
  gds_path: string;
  drc_script_path: string;
  output_report_path?: string;
  output_text_path?: string;
}

export interface DrcFlowOutputs {
  status: string;
  input_gds: string;
  drc_script: string;
  report_db: string;
  text_report_file: string | null;
  total_violations: number;
  rule_summary: Record<string, number>;
  textual_report: string;
  details?: Record<string, unknown>;
}

export const drcInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    gds_path: {
      type: "string",
      description: "Path to the layout GDS file to verify.",
    },
    drc_script_path: {
      type: "string",
      description: "Path to the KLayout DRC script deck.",
    },
    output_report_path: {
      type: "string",
      description: "Optional destination path for the .lyrdb report database.",
    },
    output_text_path: {
      type: "string",
      description: "Optional destination path for the formatted textual report.",
    },
  },
  required: ["gds_path", "drc_script_path"],
  additionalProperties: false,
};

export const drcOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: {
      type: "string",
      description: "Execution status indicator ('success' or 'error').",
    },
    input_gds: {
      type: "string",
      description: "Resolved input GDS path.",
    },
    drc_script: {
      type: "string",
      description: "Resolved DRC script path.",
    },
    report_db: {
      type: "string",
      description: "Path to the generated KLayout .lyrdb report database.",
    },
    text_report_file: {
      oneOf: [{ type: "string" }, { type: "null" }],
      description: "Path to the saved text report on disk, if specified.",
    },
    total_violations: {
      type: "integer",
      description: "Total number of design rule violations detected.",
    },
    rule_summary: {
      type: "object",
      description: "Map of rule names to individual violation counts.",
      additionalProperties: true,
    },
    textual_report: {
      type: "string",
      description: "Complete human-readable textual report listing coordinates and violation categories.",
    },
    details: {
      type: "object",
      description: "Detailed per-violation shapes and bounding coordinates.",
      additionalProperties: true,
    },
  },
  required: [
    "status",
    "input_gds",
    "drc_script",
    "report_db",
    "total_violations",
    "rule_summary",
    "textual_report",
  ],
  additionalProperties: false,
};
