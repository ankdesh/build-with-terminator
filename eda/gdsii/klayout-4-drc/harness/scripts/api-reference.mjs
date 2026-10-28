/** Verify the package's fixed API examples in the candidate Python environment. */
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {existsSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const execute = promisify(execFile);
export function candidatePython() {
  const localPython = resolve(projectRoot, '.venv/bin/python');
  return process.env.KLAYOUT_DRC_PYTHON || (existsSync(localPython) ? localPython : 'python3');
}

export async function verifiedAPIContext(context, artifactDir) {
  try {
    const result = await execute(candidatePython(), ['-m', 'klayout_drc.api_reference'], {
      cwd: projectRoot, encoding: 'utf8', timeout: 15000, maxBuffer: 1024 * 1024,
    });
    let reference;
    try { reference = JSON.parse(result.stdout); }
    catch { throw new Error('KLayout API reference returned invalid output'); }
    if (reference.status !== 'success') {
      throw new Error(reference.message || 'KLayout API reference checks failed');
    }
    const {reference_text, status, ...metadata} = reference;
    const marker = '=== Verified KLayout Python API Reference ===';
    if (typeof reference_text !== 'string' || !reference_text.startsWith(marker)) {
      throw new Error('KLayout API reference text is missing');
    }
    // Refuse a stale reference instead of mixing guidance from different runtimes.
    if (context.knowledge.includes(marker) && !context.knowledge.includes(reference_text)) {
      throw new Error('Knowledge contains a stale or incompatible KLayout API reference');
    }
    const knowledge = context.knowledge.includes(reference_text)
      ? context.knowledge : `${reference_text}\n\n${context.knowledge}`;
    writeFileSync(resolve(artifactDir, 'api_reference_check.json'), JSON.stringify(metadata, null, 2));
    return {context: {...context, knowledge}, metadata};
  } catch (cause) {
    const error = new Error(`KLayout API reference configuration error: ${cause.message}`);
    error.stage = 'api_reference';
    writeFileSync(resolve(artifactDir, 'generation_error.json'),
      JSON.stringify({stage: error.stage, message: error.message}, null, 2));
    throw error;
  }
}
