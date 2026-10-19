/** Flow operations for executing KLayout DRC via the local Python engine. */
import { spawn } from "node:child_process";
import { resolve, isAbsolute } from "node:path";
import type { Context } from "@deepseek-ai/cordis";
import { drcInputSchema, drcOutputSchema, type DrcFlowInputs, type DrcFlowOutputs } from "./types.js";

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
 * Register the klayout.run_drc_and_report operation on ctx.flows.
 * 
 * @param ctx Cordis Context with flows service available.
 * @param projectRoot Absolute root path to the klayout-4-drc Python project.
 * @returns Registration disposer.
 */
export function registerDrcOperations(ctx: Context, projectRoot: string): () => void {
  const operation: FlowOperation = {
    id: "klayout.run_drc_and_report",
    version: "1.0.0",
    effect: "read",
    cancellation: "cooperative",
    recovery: "repeat",
    inputSchema: drcInputSchema,
    outputSchema: drcOutputSchema,
    execute: async (rawInput: unknown): Promise<DrcFlowOutputs> => {
      const inputs = rawInput as unknown as DrcFlowInputs;
      
      const gdsPath = isAbsolute(inputs.gds_path)
        ? inputs.gds_path
        : resolve(projectRoot, inputs.gds_path);

      const drcPath = isAbsolute(inputs.drc_script_path)
        ? inputs.drc_script_path
        : resolve(projectRoot, inputs.drc_script_path);

      const reportDbPath = inputs.output_report_path
        ? (isAbsolute(inputs.output_report_path)
            ? inputs.output_report_path
            : resolve(projectRoot, inputs.output_report_path))
        : resolve(projectRoot, "reports/drc_violations.lyrdb");

      const textReportPath = inputs.output_text_path
        ? (isAbsolute(inputs.output_text_path)
            ? inputs.output_text_path
            : resolve(projectRoot, inputs.output_text_path))
        : resolve(projectRoot, "reports/drc_report.txt");

      const args = [
        "run",
        "python",
        "-m",
        "klayout_drc.cli",
        "--gds",
        gdsPath,
        "--deck",
        drcPath,
        "--report-db",
        reportDbPath,
        "--text-report",
        textReportPath,
        "--json",
      ];

      return new Promise<DrcFlowOutputs>((resolvePromise, rejectPromise) => {
        const proc = spawn("uv", args, {
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
            rejectPromise(
              new Error(
                `DRC process exited with code ${code}.\nStderr: ${stderr}\nStdout: ${stdout}`
              )
            );
            return;
          }

          try {
            const parsed = JSON.parse(stdout);
            if (parsed.status !== "success") {
              rejectPromise(new Error(`DRC execution reported failure: ${parsed.message || stdout}`));
              return;
            }
            resolvePromise({
              status: parsed.status,
              input_gds: parsed.input_gds,
              drc_script: parsed.drc_script,
              report_db: parsed.report_db,
              text_report_file: parsed.text_report_file ?? null,
              total_violations: parsed.total_violations,
              rule_summary: parsed.rule_summary,
              textual_report: parsed.textual_report,
              details: parsed.details,
            });
          } catch (parseError: any) {
            rejectPromise(
              new Error(
                `Failed to parse JSON output from DRC script: ${parseError.message}\nOutput was: ${stdout}`
              )
            );
          }
        });
      });
    },
  };

  return ctx.flows.registerOperation(operation);
}
