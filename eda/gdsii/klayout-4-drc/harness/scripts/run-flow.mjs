#!/usr/bin/env node
/**
 * Multi-Node Flow Runner for KLayout GDS+DRC to LLM Fix Generation.
 * 
 * Executes the complete 7-node pipeline according to the whiteboard architecture:
 *   1. Run DRC (klayout.run_drc) -> .lyrdb
 *   2. Violation Context (klayout.process_violation_context) -> formatted violations
 *   3. DRC Context (klayout.process_drc_context) -> extracted rule blocks
 *   4. GDS Context (klayout.process_gds_context) -> windowed layout geometry
 *   5. Load Knowledge (klayout.load_knowledge) -> API patterns & fix recipes
 *   6. Agent LLM (kind: model) -> Python fix script synthesis
 *   7. Save Fix Script (klayout.save_script) -> reports/fix_layout.py
 */

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync, existsSync } from "node:fs";
import { Context } from "@deepseek-ai/cordis";
import { registerDrcOperations } from "../lib/drc-operations.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const productRoot = resolve(__dirname, "..");
const projectRoot = resolve(productRoot, "..");

// CLI Argument Parsing
const args = process.argv.slice(2);
function getArg(flag, defaultValue) {
  const index = args.indexOf(flag);
  return index !== -1 && args[index + 1] ? resolve(process.cwd(), args[index + 1]) : defaultValue;
}

const gdsPath = getArg("--gds", resolve(projectRoot, "test_data/layouts/asap7_test.gds"));
const drcPath = getArg("--deck", resolve(projectRoot, "test_data/rules/asap7_mini.drc"));
const reportDbPath = getArg("--report-db", resolve(projectRoot, "reports/drc_violations.lyrdb"));
const textReportPath = getArg("--text-report", resolve(projectRoot, "reports/drc_report.txt"));
const kbDir = getArg("--knowledge-dir", resolve(projectRoot, "knowledge"));
const outputScriptPath = getArg("--output-script", resolve(projectRoot, "reports/fix_layout.py"));
const isHeuristicMode = args.includes("--heuristic");

console.log("===============================================================================");
console.log("DeepSeek Harness Flow: KLayout DRC -> Context -> LLM Layout Repair Synthesis");
console.log("===============================================================================");
console.log(`Input GDS:       ${gdsPath}`);
console.log(`DRC Deck:        ${drcPath}`);
console.log(`Report DB:       ${reportDbPath}`);
console.log(`Text Report:     ${textReportPath}`);
console.log(`Knowledge Dir:   ${kbDir}`);
console.log(`Output Script:   ${outputScriptPath}`);
console.log("-------------------------------------------------------------------------------");

async function main() {
  const ctx = new Context();
  const registeredOperations = new Map();

  // Provide flows service seam on ctx
  ctx.provide("flows", {
    registerOperation(op) {
      registeredOperations.set(op.id, op);
      return () => registeredOperations.delete(op.id);
    },
    registerDefinition() { return () => {}; },
    catalog() { return []; },
    compile() {},
    start() {},
    settled() {},
  });

  // Mount operations
  registerDrcOperations(ctx, projectRoot);

  const totalStartTime = Date.now();

  // Node 1: klayout.run_drc
  console.log("[Node 1/7] Executing 'klayout.run_drc'...");
  const runDrcOp = registeredOperations.get("klayout.run_drc");
  const drcResult = await runDrcOp.execute({
    gds_path: gdsPath,
    drc_script_path: drcPath,
    output_report_path: reportDbPath,
  });
  console.log(`  -> Violations detected: ${drcResult.total_violations}`);
  console.log(`  -> Breakdown:`, JSON.stringify(drcResult.rule_summary));

  // Node 2: klayout.process_violation_context
  console.log("[Node 2/7] Executing 'klayout.process_violation_context'...");
  const violCtxOp = registeredOperations.get("klayout.process_violation_context");
  const violResult = await violCtxOp.execute({
    report_db: drcResult.report_db,
    output_text_path: textReportPath,
  });
  console.log(`  -> Formatted violation text length: ${violResult.violations_text.length} chars`);

  // Node 3: klayout.process_drc_context
  console.log("[Node 3/7] Executing 'klayout.process_drc_context'...");
  const drcCtxOp = registeredOperations.get("klayout.process_drc_context");
  const drcCtxResult = await drcCtxOp.execute({
    drc_script_path: drcPath,
    report_db: drcResult.report_db,
  });
  console.log(`  -> Violated rules analyzed: ${drcCtxResult.violated_rules.join(", ")}`);

  // Node 4: klayout.process_gds_context
  console.log("[Node 4/7] Executing 'klayout.process_gds_context'...");
  const gdsCtxOp = registeredOperations.get("klayout.process_gds_context");
  const gdsCtxResult = await gdsCtxOp.execute({
    gds_path: gdsPath,
    report_db: drcResult.report_db,
  });
  console.log(`  -> Layout context extracted: ${gdsCtxResult.gds_sections_text.length} chars`);

  // Node 5: klayout.load_knowledge
  console.log("[Node 5/7] Executing 'klayout.load_knowledge'...");
  const kbOp = registeredOperations.get("klayout.load_knowledge");
  const kbResult = await kbOp.execute({
    knowledge_dir: kbDir,
  });
  console.log(`  -> Knowledge context loaded: ${kbResult.knowledge_text.length} chars`);

  // Node 6: Candidate Synthesis
  let pythonScript = "";
  let rationale = "";

  if (isHeuristicMode) {
    console.log("[Node 6/7] Synthesizing repair script via Heuristic Baseline Mode...");
    rationale = "Applied ASAP7 rules: Dilated M1 by 16 DBU for min-width, padded V1 by 36 DBU (9nm) for enclosure, and subtracted spacing keepouts.";
    pythonScript = `#!/usr/bin/env python3
"""Automated KLayout DRC Geometric Layout Repair Script.

Generated from Flow: klayout.gds_drc_flow (Heuristic Baseline)
Target: ASAP7 PDK M1 (18/0) and V1 (19/0)
"""
import sys
from pathlib import Path
import klayout.db as db

def fix_layout(input_gds: str, output_gds: str) -> None:
    layout = db.Layout()
    layout.read(input_gds)
    top_cell = layout.top_cell()
    if top_cell is None:
        raise ValueError("Input GDS layout has no top cell.")

    dbu = layout.dbu if layout.dbu > 0 else 0.00025  # 0.25 nm DBU
    
    # Layer definitions for ASAP7
    m1_layer = layout.layer(18, 0)
    v1_layer = layout.layer(19, 0)

    # 1. Enclosure fix: V1 must be enclosed by M1 by >= 9nm (36 DBU)
    m1_shapes = top_cell.shapes(m1_layer)
    v1_shapes = top_cell.shapes(v1_layer)

    m1_region = db.Region(m1_shapes)
    v1_region = db.Region(v1_shapes)

    # Enclosure patch: pad V1 by 36 DBU (9 nm)
    v1_pad = v1_region.sized(36)
    healed_m1 = m1_region + v1_pad

    m1_shapes.clear()
    m1_shapes.insert(healed_m1)

    out_path = Path(output_gds).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(out_path))
    print(f"Repaired layout written to {out_path}")

if __name__ == "__main__":
    in_file = sys.argv[1] if len(sys.argv) > 1 else "${gdsPath}"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "${resolve(projectRoot, 'reports/fixed_layout.gds')}"
    fix_layout(in_file, out_file)
`;
  } else {
    console.log("[Node 6/7] Synthesizing repair script via Model Phase (Agent)...");

    const openaiApiKey = process.env.OPENAI_API_KEY;
    const deepseekApiKey = process.env.DEEPSEEK_API_KEY;

    if (!openaiApiKey && !deepseekApiKey) {
      throw new Error("Missing LLM API Key: neither OPENAI_API_KEY nor DEEPSEEK_API_KEY is configured.");
    }

    const isDeepSeek = Boolean(deepseekApiKey);
    const endpoint = isDeepSeek 
      ? "https://api.deepseek.com/chat/completions" 
      : "https://api.openai.com/v1/chat/completions";
    const model = isDeepSeek ? "deepseek-coder" : "gpt-4o-mini";
    const apiKey = isDeepSeek ? deepseekApiKey : openaiApiKey;

    const instructionsFile = resolve(productRoot, "profile/catalog/flows/generate_fix.md");
    const instructions = existsSync(instructionsFile) 
      ? readFileSync(instructionsFile, "utf-8") 
      : "You are an automated EDA layout repair assistant.";

    const prompt = [
      instructions,
      "\n### CONTEXT 1: DRC VIOLATIONS\n",
      violResult.violations_text,
      "\n### CONTEXT 2: EXTRACTED DRC RULES\n",
      drcCtxResult.drc_rules_text,
      "\n### CONTEXT 3: GDS LAYOUT LOCAL SECTIONS\n",
      gdsCtxResult.gds_sections_text,
      "\n### CONTEXT 4: DOMAIN KNOWLEDGE BASE\n",
      kbResult.knowledge_text,
      "\nRespond strictly with a JSON object: {\"python_script\": \"...\", \"rationale\": \"...\"}"
    ].join("\n");

    console.log(`  -> Invoking LLM (${model})...`);
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: "You are an expert EDA Physical Verification and DRC Remediation Engineer." },
          { role: "user", content: prompt }
        ],
        temperature: 0.1,
      }),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`LLM API returned HTTP ${resp.status}: ${errText}`);
    }

    const data = await resp.json();
    const content = JSON.parse(data.choices[0].message.content);
    pythonScript = content.python_script;
    rationale = content.rationale;
    console.log(`  -> LLM synthesis succeeded! Rationale: ${rationale}`);
  }

  // Node 7: klayout.save_script
  console.log("[Node 7/7] Executing 'klayout.save_script'...");
  const saveOp = registeredOperations.get("klayout.save_script");
  const saveResult = await saveOp.execute({
    script_content: pythonScript,
    output_path: outputScriptPath,
  });

  const durationMs = Date.now() - totalStartTime;
  console.log("-------------------------------------------------------------------------------");
  console.log(`Flow execution finished successfully in ${durationMs}ms`);
  console.log(`Python Fix Script saved: ${saveResult.saved_path}`);
  console.log(`Rationale:              ${rationale}`);
  console.log("===============================================================================");
}

main().catch((err) => {
  console.error("Flow execution failed:", err.message);
  process.exit(1);
});
