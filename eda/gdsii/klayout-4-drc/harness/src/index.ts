/** Main Cordis plugin for the KLayout DRC Harness integration. */
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import type { Context } from "@deepseek-ai/cordis";
import { registerDrcOperations } from "./drc-operations.js";

export * from "./types.js";
export * from "./drc-operations.js";

export const name = "klayout-harness-drc";
export const inject = ["flows"];

/**
 * Apply the KLayout DRC harness plugin to a Cordis Context.
 * 
 * Registers the KLayout batch execution operation and the declarative
 * GDS+DRC flow definition in ctx.flows.
 */
export function apply(ctx: Context): void {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const productRoot = resolve(currentDir, "..");
  const projectRoot = resolve(productRoot, "..");

  // 1. Register the executable DRC operations
  const disposeOperation = registerDrcOperations(ctx, projectRoot);
  ctx.effect(() => disposeOperation);

  // 2. Load and register the declarative Flow definition
  const flowYamlPath = resolve(productRoot, "profile/catalog/flows/run_drc.yaml");
  const yamlContent = readFileSync(flowYamlPath, "utf8");
  const flowDefinition = JSON.parse(yamlContent);

  const disposeDefinition = ctx.flows.registerDefinition(flowDefinition);
  ctx.effect(() => disposeDefinition);
}

export default apply;
