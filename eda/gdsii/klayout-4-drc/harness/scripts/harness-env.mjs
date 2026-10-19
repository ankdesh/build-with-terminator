/** Keep the selected checkout in .env without rewriting other developer settings. */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { parseEnv } from "node:util";

export function updateHarnessSource(product, harness) {
  const value = [`'${harness}'`, `"${harness}"`, `\`${harness}\``, harness]
    .find(candidate => parseEnv(`HARNESS_SOURCE=${candidate}`).HARNESS_SOURCE === harness);
  if (value === undefined) throw new Error("The Harness path cannot be represented in a Node .env file.");

  const path = join(product, ".env");
  const source = existsSync(path) ? readFileSync(path, "utf8") : "";
  const newline = source.includes("\r\n") ? "\r\n" : "\n";
  let found = false;

  const assignments = /^([ \t]*)(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*('[^']*'|"[^"]*"|`[^`]*`|[^\r\n]*)([^\r\n]*)/gm;
  let updated = source.replace(assignments, (entry, indent, key, previous, tail) => {
    if (key !== "HARNESS_SOURCE") return entry;
    const comment = /^["'`]/.test(previous) ? tail : previous.match(/[ \t]*#[^\r\n]*$/)?.[0] || "";
    if (found) return comment ? `${indent}${comment.trimStart()}` : "";
    found = true;
    return `${indent}HARNESS_SOURCE=${value}${comment}`;
  });
  if (!found) {
    if (updated && !updated.endsWith("\n")) updated += newline;
    updated += `HARNESS_SOURCE=${value}${newline}`;
  }
  if (updated !== source) writeFileSync(path, updated, { mode: 0o600 });
}
