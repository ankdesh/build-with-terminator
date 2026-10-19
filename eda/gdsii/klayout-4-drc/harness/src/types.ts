import type { JsonSchemaNode } from "@deepseek-ai/dsh-tools";

// --- 1. Run DRC ---
export interface RunDrcInputs {
  gds_path: string;
  drc_script_path: string;
  output_report_path?: string;
}

export interface RunDrcOutputs {
  status: string;
  input_gds: string;
  drc_script: string;
  report_db: string;
  total_violations: number;
  rule_summary: Record<string, number>;
}

export const runDrcInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    gds_path: { type: "string", description: "Path to input GDS layout" },
    drc_script_path: { type: "string", description: "Path to KLayout DRC deck" },
    output_report_path: { type: "string", description: "Optional output path for .lyrdb" },
  },
  required: ["gds_path", "drc_script_path"],
  additionalProperties: false,
};

export const runDrcOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    input_gds: { type: "string" },
    drc_script: { type: "string" },
    report_db: { type: "string" },
    total_violations: { type: "integer" },
    rule_summary: { type: "object", additionalProperties: true },
  },
  required: ["status", "input_gds", "drc_script", "report_db", "total_violations", "rule_summary"],
  additionalProperties: false,
};

// --- 2. Violation Context ---
export interface ViolationCtxInputs {
  report_db: string;
  output_text_path?: string;
}

export interface ViolationCtxOutputs {
  status: string;
  report_db: string;
  total_violations: number;
  rule_summary: Record<string, number>;
  violations_text: string;
  text_report_file?: string | null;
}

export const violationCtxInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    report_db: { type: "string", description: "Path to .lyrdb database" },
    output_text_path: { type: "string", description: "Optional path to save text report" },
  },
  required: ["report_db"],
  additionalProperties: false,
};

export const violationCtxOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    report_db: { type: "string" },
    total_violations: { type: "integer" },
    rule_summary: { type: "object", additionalProperties: true },
    violations_text: { type: "string" },
    text_report_file: { oneOf: [{ type: "string" }, { type: "null" }] },
  },
  required: ["status", "report_db", "total_violations", "rule_summary", "violations_text"],
  additionalProperties: false,
};

// --- 3. DRC Context ---
export interface DrcCtxInputs {
  drc_script_path: string;
  report_db: string;
}

export interface DrcCtxOutputs {
  status: string;
  drc_script: string;
  violated_rules: string[];
  drc_rules_text: string;
}

export const drcCtxInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    drc_script_path: { type: "string", description: "Path to DRC rule deck" },
    report_db: { type: "string", description: "Path to .lyrdb database to match violated rules" },
  },
  required: ["drc_script_path", "report_db"],
  additionalProperties: false,
};

export const drcCtxOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    drc_script: { type: "string" },
    violated_rules: { type: "array", items: { type: "string" } },
    drc_rules_text: { type: "string" },
  },
  required: ["status", "drc_script", "violated_rules", "drc_rules_text"],
  additionalProperties: false,
};

// --- 4. GDS Context ---
export interface GdsCtxInputs {
  gds_path: string;
  report_db: string;
  halo_um?: number;
}

export interface GdsCtxOutputs {
  status: string;
  gds_path: string;
  halo_um: number;
  gds_sections_text: string;
}

export const gdsCtxInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    gds_path: { type: "string", description: "Path to GDS file" },
    report_db: { type: "string", description: "Path to .lyrdb database" },
    halo_um: { type: "number", description: "Halo window margin in um (default: 0.1)" },
  },
  required: ["gds_path", "report_db"],
  additionalProperties: false,
};

export const gdsCtxOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    gds_path: { type: "string" },
    halo_um: { type: "number" },
    gds_sections_text: { type: "string" },
  },
  required: ["status", "gds_path", "halo_um", "gds_sections_text"],
  additionalProperties: false,
};

// --- 5. Knowledge Loader ---
export interface KnowledgeLoaderInputs {
  knowledge_dir?: string;
}

export interface KnowledgeLoaderOutputs {
  status: string;
  knowledge_dir: string;
  knowledge_text: string;
}

export const knowledgeLoaderInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    knowledge_dir: { type: "string", description: "Directory with markdown knowledge files" },
  },
  additionalProperties: false,
};

export const knowledgeLoaderOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    knowledge_dir: { type: "string" },
    knowledge_text: { type: "string" },
  },
  required: ["status", "knowledge_dir", "knowledge_text"],
  additionalProperties: false,
};

// --- 6. Save Fix Script ---
export interface SaveScriptInputs {
  script_content: string;
  output_path?: string;
}

export interface SaveScriptOutputs {
  status: string;
  saved_path: string;
}

export const saveScriptInputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    script_content: { type: "string", description: "Content of the generated Python fix script" },
    output_path: { type: "string", description: "Target path to write the script" },
  },
  required: ["script_content"],
  additionalProperties: false,
};

export const saveScriptOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    saved_path: { type: "string" },
  },
  required: ["status", "saved_path"],
  additionalProperties: false,
};

// --- Legacy / Composite Operation (for backwards compatibility) ---
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
    gds_path: { type: "string" },
    drc_script_path: { type: "string" },
    output_report_path: { type: "string" },
    output_text_path: { type: "string" },
  },
  required: ["gds_path", "drc_script_path"],
  additionalProperties: false,
};

export const drcOutputSchema: JsonSchemaNode = {
  type: "object",
  properties: {
    status: { type: "string" },
    input_gds: { type: "string" },
    drc_script: { type: "string" },
    report_db: { type: "string" },
    text_report_file: { oneOf: [{ type: "string" }, { type: "null" }] },
    total_violations: { type: "integer" },
    rule_summary: { type: "object", additionalProperties: true },
    textual_report: { type: "string" },
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
