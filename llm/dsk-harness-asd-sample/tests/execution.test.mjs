import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { executeCode } from '../src/execution.mjs';

const cwd = await mkdtemp(join(tmpdir(), 'dsk-execution-'));
const options = { cwd, python: process.env.SAMPLE_PYTHON || 'python3', timeoutMs: 2000, maxOutputBytes: 4096 };
test.after(() => rm(cwd, { recursive: true, force: true }));
test('Bash and Python execute real programs', async () => {
  assert.equal((await executeCode({ language: 'bash', code: 'printf "%s" "$((6*7))"' }, options)).stdout, '42');
  assert.equal((await executeCode({ language: 'python', code: 'print(sum(range(11)))' }, options)).stdout, '55\n');
});
test('credentials are absent from child environment', async () => {
  process.env.SAMPLE_TEST_API_KEY = 'must-not-reach-child';
  try { assert.equal((await executeCode({ language: 'bash', code: 'printf "%s" "${SAMPLE_TEST_API_KEY-unset}"' }, options)).stdout, 'unset'); }
  finally { delete process.env.SAMPLE_TEST_API_KEY; }
});
test('failure preserves stderr and exit code', async () => {
  const result = await executeCode({ language: 'bash', code: 'echo failed >&2; exit 7' }, options);
  assert.equal(result.exitCode, 7); assert.equal(result.stderr, 'failed\n');
});
test('timeout stops child and reports timeout separately', async () => {
  const result = await executeCode({ language: 'bash', code: 'sleep 60' }, { ...options, timeoutMs: 80 });
  assert.equal(result.timedOut, true); assert.equal(result.signal, 'SIGKILL');
});
test('cancellation stops Python', async () => {
  const controller = new AbortController();
  const running = executeCode({ language: 'python', code: 'import time; time.sleep(60)' }, { ...options, signal: controller.signal });
  setTimeout(() => controller.abort(), 80);
  assert.equal((await running).aborted, true);
});
test('output limit bounds returned output', async () => {
  const result = await executeCode({ language: 'python', code: 'print("x" * 100000)' }, options);
  assert.equal(result.truncated, true); assert.ok(Buffer.byteLength(result.stdout) <= 4096);
});
