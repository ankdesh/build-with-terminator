#!/usr/bin/env node
/**
 * Standalone Flow Runner for KLayout GDS+DRC Workflow.
 * 
 * Executes the klayout.gds_drc_flow pipeline using the Cordis service architecture
 * and delegates execution to the Python KLayout DRC engine.
 * 
 * Usage:
 *   node scripts/run-flow.mjs
 *   node scripts/run-flow.mjs --gds ../test_data/layouts/asap7_test.gds --deck ../test_data/rules/asap7_mini.drc
 */

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Context } from "@deepseek-ai/cordis";
import { registerDrcOperations } from "../lib/drc-operations.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const productRoot = resolve(__dirname, "..");
const projectRoot = resolve(productRoot, "..");

// Parse optional arguments
const args = process.argv.slice(2);
function getArg(flag, defaultValue) {
  const index = args.indexOf(flag);
  return index !== -1 && args[index + 1] ? resolve(process.cwd(), args[index + 1]) : defaultValue;
}

const gdsPath = getArg("--gds", resolve(projectRoot, "test_data/layouts/asap7_test.gds"));
const drcPath = getArg("--deck", resolve(projectRoot, "test_data/rules/asap7_mini.drc"));
const reportDbPath = getArg("--report-db", resolve(projectRoot, "reports/drc_violations.lyrdb"));
const textReportPath = getArg("--text-report", resolve(projectRoot, "reports/drc_report.txt"));

console.log("=================================================");
console.log("DeepSeek Harness Flow: KLayout GDS+DRC Execution");
console.log("=================================================");
console.log(`Input GDS:   ${gdsPath}`);
console.log(`DRC Deck:    ${drcPath}`);
console.log(`Report DB:   ${reportDbPath}`);
console.log(`Text Report: ${textReportPath}`);
console.log("-------------------------------------------------");

async function main() {
  const ctx = new Context();

  // In-memory registered operations store
  const registeredOperations = new Map();

  // Provide flows service seam on ctx
  ctx.provide("flows", {
    registerOperation(op) {
      registeredOperations.set(op.id, op);
      return () => registeredOperations.delete(op.id);
    },
    registerDefinition(def) {
      return () => {};
    },
    catalog() {
      return [];
    },
    compile() {},
    start() {},
    settled() {},
  });

  // Mount the DRC operations
  registerDrcOperations(ctx, projectRoot);

  const operation = registeredOperations.get("klayout.run_drc_and_report");
  if (!operation) {
    throw new Error("Operation 'klayout.run_drc_and_report' was not registered.");
  }

  console.log("Executing flow node: 'execute_drc' via operation 'klayout.run_drc_and_report'...\n");
  const startTime = Date.now();

  const result = await operation.execute({
    gds_path: gdsPath,
    drc_script_path: drcPath,
    output_report_path: reportDbPath,
    output_text_path: textReportPath,
  });

  const durationMs = Date.now() - startTime;

  console.log(result.textual_report);
  console.log("-------------------------------------------------");
  console.log(`Flow execution finished in ${durationMs}ms`);
  console.log(`Report database saved: ${result.report_db}`);
  if (result.text_report_file) {
    console.log(`Text report saved:    ${result.text_report_file}`);
  }
  console.log(`Total Violations:     ${result.total_violations}`);
  console.log("Rule breakdown:      ", JSON.stringify(result.rule_summary));
  console.log("=================================================");
}

main().catch((err) => {
  console.error("Flow execution failed:", err.message);
  process.exit(1);
});
