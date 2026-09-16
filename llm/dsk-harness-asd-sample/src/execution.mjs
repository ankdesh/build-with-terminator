/** Executes one finite Bash or Python program and waits for its process group to stop. */
import { spawn } from 'node:child_process';

/** Run code with bounded output, an explicit working directory, and scrubbed credentials. */
export async function executeCode({ language, code }, { cwd, python, timeoutMs, maxOutputBytes, signal }) {
  if (!['bash', 'python'].includes(language)) throw new Error('Unsupported language');
  if (typeof code !== 'string' || !code.trim()) throw new Error('Code must be nonempty');
  if (signal?.aborted) throw signal.reason;
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/KEY|SECRET|TOKEN|PASSWORD/i.test(key)));
  // Python and Bash startup hooks must not import code from the host environment.
  for (const key of ['BASH_ENV', 'ENV', 'PYTHONPATH', 'PYTHONHOME', 'NODE_OPTIONS', 'LD_PRELOAD']) delete env[key];
  const child = spawn(language === 'python' ? python : '/bin/bash', language === 'python' ? ['-I', '-u', '-c', code] : ['--noprofile', '--norc', '-c', code], { cwd, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '', stderr = '', bytes = 0, truncated = false, timedOut = false, aborted = false;
  const kill = () => {
    if (!child.pid) return;
    try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  };
  const timer = setTimeout(() => { timedOut = true; kill(); }, timeoutMs);
  const abort = () => { aborted = true; kill(); };
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  const capture = (kind, chunk) => {
    const remaining = Math.max(0, maxOutputBytes - bytes);
    bytes += chunk.length;
    const value = chunk.subarray(0, remaining).toString('utf8');
    if (kind === 'stdout') stdout += value; else stderr += value;
    if (bytes > maxOutputBytes) { truncated = true; kill(); }
  };
  child.stdout.on('data', chunk => capture('stdout', chunk));
  child.stderr.on('data', chunk => capture('stderr', chunk));
  // A shell can leave children holding its pipes open. Kill the remaining group on leader exit.
  child.once('exit', kill);
  try {
    const outcome = await new Promise((resolve, reject) => {
      child.once('error', reject);
      child.once('close', (exitCode, exitSignal) => resolve({ exitCode, signal: exitSignal }));
    });
    return { language, stdout, stderr, ...outcome, timedOut, aborted, truncated };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}
