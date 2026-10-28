/** Flow operations for executing KLayout DRC and context processors via the local Python engine. */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, isAbsolute } from "node:path";
import type { Context } from "@deepseek-ai/cordis";
import {
  runDrcInputSchema,
  runDrcOutputSchema,
  violationCtxInputSchema,
  violationCtxOutputSchema,
  drcCtxInputSchema,
  drcCtxOutputSchema,
  gdsCtxInputSchema,
  gdsCtxOutputSchema,
  knowledgeLoaderInputSchema,
  knowledgeLoaderOutputSchema,
  saveScriptInputSchema,
  saveScriptOutputSchema,
  drcInputSchema,
  drcOutputSchema,
  type RunDrcInputs,
  type RunDrcOutputs,
  type ViolationCtxInputs,
  type ViolationCtxOutputs,
  type DrcCtxInputs,
  type DrcCtxOutputs,
  type GdsCtxInputs,
  type GdsCtxOutputs,
  type KnowledgeLoaderInputs,
  type KnowledgeLoaderOutputs,
  type SaveScriptInputs,
  type SaveScriptOutputs,
  type DrcFlowInputs,
  type DrcFlowOutputs,
} from "./types.js";

export interface FlowOperation {
  id: string;
  version: string;
  effect: "read" | "write";
  cancellation: "cooperative" | "abort";
  recovery: "repeat" | "reconcile" | "manual";
  inputSchema: unknown;
  outputSchema: unknown;
  execute: (input: unknown) => Promise<unknown>;
}

/**
 * Execute a Python CLI command through 'uv run python -m klayout_drc.cli' and parse stdout JSON.
 */
function runPythonCli<T>(projectRoot: string, cliArgs: string[], profileName?: string): Promise<T> {
  const localPython = resolve(projectRoot, '.venv/bin/python');
  const python = process.env.KLAYOUT_DRC_PYTHON || (existsSync(localPython) ? localPython : undefined);
  const launcher = python || "uv";
  const args = [...(python ? [] : ["run", "python"]), "-m", "klayout_drc.cli", ...cliArgs,
    ...(profileName ? ["--profile", profileName] : []), "--json"];

  return new Promise<T>((resolvePromise, rejectPromise) => {
    const proc = spawn(launcher, args, {
      cwd: projectRoot,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (chunk: Buffer | string) => {
      stdout += chunk.toString();
    });

    proc.stderr.on("data", (chunk: Buffer | string) => {
      stderr += chunk.toString();
    });

    proc.on("error", (err: Error) => {
      rejectPromise(new Error(`Failed to launch 'uv' subprocess: ${err.message}`));
    });

    proc.on("close", (code: number | null) => {
      if (code !== 0) {
        try {
          const failure = JSON.parse(stderr || stdout);
          if (failure.stage === 'api_reference') {
            rejectPromise(Object.assign(new Error(failure.message), {stage: failure.stage}));
            return;
          }
        } catch { /* Non-JSON tool errors keep the captured diagnostic below. */ }
        rejectPromise(
          new Error(
            `KLayout CLI process exited with code ${code}.\nStderr: ${stderr}\nStdout: ${stdout}`
          )
        );
        return;
      }

      try {
        const parsed = JSON.parse(stdout);
        if (parsed.status === "error" || parsed.status === "fatal") {
          rejectPromise(new Error(`CLI reported error: ${parsed.message || stdout}`));
          return;
        }
        resolvePromise(parsed as T);
      } catch (parseError: any) {
        rejectPromise(
          new Error(
            `Failed to parse JSON output from KLayout CLI: ${parseError.message}\nOutput: ${stdout}`
          )
        );
      }
    });
  });
}

function resolvePath(projectRoot: string, p?: string, defaultRelative?: string): string {
  if (!p) {
    return resolve(projectRoot, defaultRelative || ".");
  }
  return isAbsolute(p) ? p : resolve(projectRoot, p);
}

/**
 * Register all KLayout DRC and context processor operations on ctx.flows.
 */
export function registerDrcOperations(ctx: Context, projectRoot: string): () => void {
  const disposers: Array<() => void> = [];

  // 1. klayout.run_drc
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.run_drc",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: runDrcInputSchema,
      outputSchema: runDrcOutputSchema,
      execute: async (rawInput: unknown): Promise<RunDrcOutputs> => {
        const inputs = rawInput as RunDrcInputs;
        const gds = resolvePath(projectRoot, inputs.gds_path);
        const deck = resolvePath(projectRoot, inputs.drc_script_path);
        const reportDb = resolvePath(
          projectRoot,
          inputs.output_report_path,
          "reports/drc_violations.lyrdb"
        );

        return runPythonCli<RunDrcOutputs>(projectRoot, [
          "--mode",
          "run-drc",
          "--gds",
          gds,
          "--deck",
          deck,
          "--report-db",
          reportDb,
        ], inputs.profile_name);
      },
    })
  );

  // 2. klayout.process_violation_context
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.process_violation_context",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: violationCtxInputSchema,
      outputSchema: violationCtxOutputSchema,
      execute: async (rawInput: unknown): Promise<ViolationCtxOutputs> => {
        const inputs = rawInput as ViolationCtxInputs;
        const reportDb = resolvePath(projectRoot, inputs.report_db);
        const cliArgs = ["--mode", "violation-ctx", "--report-db", reportDb];
        if (inputs.edit_policy_path) cliArgs.push("--edit-policy", resolvePath(projectRoot, inputs.edit_policy_path));
        if (inputs.output_text_path) {
          cliArgs.push("--text-report", resolvePath(projectRoot, inputs.output_text_path));
        }

        return runPythonCli<ViolationCtxOutputs>(projectRoot, cliArgs, inputs.profile_name);
      },
    })
  );

  // 3. klayout.process_drc_context
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.process_drc_context",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: drcCtxInputSchema,
      outputSchema: drcCtxOutputSchema,
      execute: async (rawInput: unknown): Promise<DrcCtxOutputs> => {
        const inputs = rawInput as DrcCtxInputs;
        const deck = resolvePath(projectRoot, inputs.drc_script_path);
        const reportDb = resolvePath(projectRoot, inputs.report_db);

        return runPythonCli<DrcCtxOutputs>(projectRoot, [
          "--mode",
          "drc-ctx",
          "--deck",
          deck,
          "--report-db",
          reportDb,
          ...(inputs.edit_policy_path ? ["--edit-policy", resolvePath(projectRoot, inputs.edit_policy_path)] : []),
        ], inputs.profile_name);
      },
    })
  );

  // 4. klayout.process_gds_context
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.process_gds_context",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: gdsCtxInputSchema,
      outputSchema: gdsCtxOutputSchema,
      execute: async (rawInput: unknown): Promise<GdsCtxOutputs> => {
        const inputs = rawInput as GdsCtxInputs;
        const gds = resolvePath(projectRoot, inputs.gds_path);
        const reportDb = resolvePath(projectRoot, inputs.report_db);
        const cliArgs = ["--mode", "gds-ctx", "--gds", gds, "--report-db", reportDb];
        if (inputs.edit_policy_path) cliArgs.push("--edit-policy", resolvePath(projectRoot, inputs.edit_policy_path));
        if (inputs.halo_um !== undefined) {
          cliArgs.push("--halo-um", String(inputs.halo_um));
        }

        return runPythonCli<GdsCtxOutputs>(projectRoot, cliArgs, inputs.profile_name);
      },
    })
  );

  // 5. klayout.load_knowledge
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.load_knowledge",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: knowledgeLoaderInputSchema,
      outputSchema: knowledgeLoaderOutputSchema,
      execute: async (rawInput: unknown): Promise<KnowledgeLoaderOutputs> => {
        const inputs = (rawInput || {}) as KnowledgeLoaderInputs;
        const kbDir = resolvePath(projectRoot, inputs.knowledge_dir, "knowledge");

        return runPythonCli<KnowledgeLoaderOutputs>(projectRoot, [
          "--mode",
          "load-knowledge",
          "--knowledge-dir",
          kbDir,
        ], inputs.profile_name);
      },
    })
  );

  // The declarative flow and standalone baseline use the same request contract.
  disposers.push(ctx.flows.registerOperation({
    id: "klayout.synthesize_candidate", version: "1.0.0", effect: "write",
    cancellation: "abort", recovery: "manual",
    inputSchema: { type: "object", properties: {
      violations: { type: "string" }, drc_rules: { type: "string" },
      gds_sections: { type: "string" }, knowledge: { type: "string" },
      profile_name: { type: "string" }, output_script_path: { type: "string" }
    }, required: ["violations", "drc_rules", "gds_sections", "knowledge", "profile_name", "output_script_path"], additionalProperties: false },
    outputSchema: { type: "object", properties: { python_script: { type: "string" }, rationale: { type: "string" }, returned_model: { oneOf: [{ type: "string" }, { type: "null" }] } },
      required: ["python_script", "rationale", "returned_model"], additionalProperties: false },
    execute: async (input: any) => {
      const { pathToFileURL } = await import("node:url");
      const { readFileSync, mkdirSync } = await import("node:fs");
      const { dirname } = await import("node:path");
      const contract = await import(pathToFileURL(resolve(projectRoot, "harness/scripts/baseline-contract.mjs")).href);
      const directory = dirname(resolvePath(projectRoot, input.output_script_path));
      mkdirSync(directory, { recursive: true });
      const instructions = readFileSync(resolve(projectRoot, "harness/profile/catalog/flows/generate_fix.md"), "utf8");
      return contract.generateCandidate(instructions, {
        violations: input.violations, drc_rules: input.drc_rules,
        gds_sections: input.gds_sections, knowledge: input.knowledge
      }, directory, input.profile_name);
    },
  }));

  // 6. klayout.save_script
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.save_script",
      version: "1.0.0",
      effect: "write",
      cancellation: "abort",
      recovery: "manual",
      inputSchema: saveScriptInputSchema,
      outputSchema: saveScriptOutputSchema,
      execute: async (rawInput: unknown): Promise<SaveScriptOutputs> => {
        const inputs = rawInput as SaveScriptInputs;
        const outPath = resolvePath(
          projectRoot,
          inputs.output_path,
          "reports/fix_layout.py"
        );

        return runPythonCli<SaveScriptOutputs>(projectRoot, [
          "--mode",
          "save-script",
          "--script-content",
          inputs.script_content,
          "--output-script",
          outPath,
        ], inputs.profile_name);
      },
    })
  );

  // 7. klayout.run_drc_and_report (composite operation)
  disposers.push(
    ctx.flows.registerOperation({
      id: "klayout.run_drc_and_report",
      version: "1.0.0",
      effect: "read",
      cancellation: "cooperative",
      recovery: "repeat",
      inputSchema: drcInputSchema,
      outputSchema: drcOutputSchema,
      execute: async (rawInput: unknown): Promise<DrcFlowOutputs> => {
        const inputs = rawInput as DrcFlowInputs;
        const gds = resolvePath(projectRoot, inputs.gds_path);
        const deck = resolvePath(projectRoot, inputs.drc_script_path);
        const reportDb = resolvePath(
          projectRoot,
          inputs.output_report_path,
          "reports/drc_violations.lyrdb"
        );
        const textReport = resolvePath(
          projectRoot,
          inputs.output_text_path,
          "reports/drc_report.txt"
        );

        return runPythonCli<DrcFlowOutputs>(projectRoot, [
          "--gds",
          gds,
          "--deck",
          deck,
          "--report-db",
          reportDb,
          "--text-report",
          textReport,
        ], inputs.profile_name);
      },
    })
  );

  return () => {
    for (const dispose of disposers) {
      dispose();
    }
  };
}
