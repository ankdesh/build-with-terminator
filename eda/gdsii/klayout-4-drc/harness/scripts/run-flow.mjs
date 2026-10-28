#!/usr/bin/env node
/** Canonical single-request baseline runner. No repair execution or retries. */
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { Context } from '@deepseek-ai/cordis';
import { registerDrcOperations } from '../lib/drc-operations.js';
import { generateCandidate } from './baseline-contract.mjs';
const productRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const projectRoot = resolve(productRoot, '..');
const args = process.argv.slice(2);
function option(flag, fallback) {
  const i = args.indexOf(flag);
  return i >= 0 ? args[i+1] : fallback;
}
const profile = option('--profile');
const editPolicy = option('--edit-policy');
if (!profile) throw new Error('--profile is required');
const gds = resolve(option('--gds'));
const deck = resolve(option('--deck'));
const report = resolve(option('--report-db'));
const output = resolve(option('--output-script'));
const artifactDir = resolve(option('--artifact-dir', dirname(output)));
const textReport = resolve(option('--text-report', resolve(artifactDir, 'violations.txt')));
const knowledgeDir = resolve(option('--knowledge-dir', resolve(projectRoot, 'knowledge')));
const hash = value => createHash('sha256').update(value).digest('hex');
mkdirSync(artifactDir, {recursive: true});
const save = (name, data) => writeFileSync(resolve(artifactDir, name), JSON.stringify(data, null, 2));
async function main() {
  if (args.includes('--heuristic')) throw new Error('Use the Python heuristic baseline; this runner is agent-only.');
  const ctx = new Context();
  const operations = new Map();
  ctx.provide('flows', {
    registerOperation(op) { operations.set(op.id, op); return () => operations.delete(op.id); },
    registerDefinition() { return () => {}; }, catalog() { return []; }, compile() {}, start() {}, settled() {},
  });
  registerDrcOperations(ctx, projectRoot);
  const call = (id, input) => operations.get(`klayout.${id}`).execute({...input, profile_name: profile});
  if (!args.includes('--reuse-report')) {
    await call('run_drc', {gds_path:gds, drc_script_path:deck, output_report_path:report});
  } else if (!existsSync(report)) {
    throw new Error('Verified baseline report is missing');
  }
  const beforeHash = hash(readFileSync(report));
  const violations = await call('process_violation_context', {report_db:report, output_text_path:textReport, ...(editPolicy ? {edit_policy_path:resolve(editPolicy)} : {})});
  const rules = await call('process_drc_context', {drc_script_path:deck, report_db:report, ...(editPolicy ? {edit_policy_path:resolve(editPolicy)} : {})});
  const geometry = await call('process_gds_context', {gds_path:gds, report_db:report, ...(editPolicy ? {edit_policy_path:resolve(editPolicy)} : {})});
  const knowledge = await call('load_knowledge', {knowledge_dir:knowledgeDir});
  const context = {violations:violations.violations_text, drc_rules:rules.drc_rules_text,
                   gds_sections:geometry.gds_sections_text, knowledge:knowledge.knowledge_text};
  const instructions = readFileSync(resolve(productRoot,'profile/catalog/flows/generate_fix.md'),'utf8');
  const candidate = await generateCandidate(instructions, context, artifactDir, profile);
  await call('save_script',{script_content:candidate.python_script,output_path:output});
  if (beforeHash !== hash(readFileSync(report))) throw new Error('Baseline report changed during synthesis');
  console.log(JSON.stringify({status:'candidate_saved', model:candidate.returned_model, output}));
}
main().catch(error => {
  save('generation_error.json', {stage:error.stage || 'synthesis',message:error.message});
  console.error(error.message); process.exitCode=1;
});
