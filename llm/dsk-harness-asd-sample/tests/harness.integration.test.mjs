/** Exercises the real dsh launcher, pi-ai HTTP adapter, agent loop, tool dispatch, and persistence. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { createRequire } from 'node:module';
const root = fileURLToPath(new URL('..', import.meta.url));
const delay = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, message, timeout = 30000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn(); if (value) return value; await delay(100); }
  throw new Error(message);
}

test('real Harness executes Bash and Python, streams results, and resumes durable conversations', { timeout: 90000 }, async () => {
  const requests = [];
  const provider = createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    const request = JSON.parse(body); requests.push(request);
    assert.ok(req.url.endsWith('/chat/completions'));
    const user = [...request.messages].reverse().find(m => m.role === 'user');
    const isPython = JSON.stringify(user).includes('Python');
    const last = request.messages.at(-1);
    const content = last.role === 'tool' ? JSON.parse(last.content) : null;
    const delta = content
      ? { content: `Execution confirmed: ${content.stdout.trim()}` }
      : { tool_calls: [{ index: 0, id: `call_${requests.length}`, type: 'function', function: { name: 'execute_code', arguments: JSON.stringify({ language: isPython ? 'python' : 'bash', code: isPython ? 'print(sum(range(11)))' : 'printf "bash-ok"' }) } }] };
    res.writeHead(200, { 'Content-Type': 'text/event-stream' });
    for (const [index, part] of [{ role: 'assistant' }, delta, {}].entries()) res.write(`data: ${JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', created: 1, model: 'gpt-4o-mini', choices: [{ index: 0, delta: part, finish_reason: index === 2 ? content ? 'stop' : 'tool_calls' : null }] })}\n\n`);
    res.end('data: [DONE]\n\n');
  });
  provider.listen(0, '127.0.0.1'); await once(provider, 'listening');
  const state = await mkdtemp(join(tmpdir(), 'asd-harness-test-'));
  const reserve = createServer(); reserve.listen(0, '127.0.0.1'); await once(reserve, 'listening'); const port = reserve.address().port; await new Promise(r => reserve.close(r));
  let child, output = '';
  function start() {
    child = spawn(process.execPath, [process.env.SAMPLE_RELEASE ? resolve(process.env.SAMPLE_RELEASE, 'deployment/launch.mjs') : resolve(root, 'scripts/dev.mjs')], { cwd: root, env: { ...process.env, SAMPLE_STATE: state, SAMPLE_PORT: String(port), OPENAI_API_KEY: 'test-fixture-only', OPENAI_BASE_URL: `http://127.0.0.1:${provider.address().port}/v1` }, stdio: ['ignore', 'pipe', 'pipe'] });
    child.stdout.on('data', bytes => { output += bytes; }); child.stderr.on('data', bytes => { output += bytes; });
  }
  async function stop() { if (child && child.exitCode === null) { const done = once(child, 'exit'); child.kill('SIGTERM'); await done; } }
  const base = `http://127.0.0.1:${port}`;
  async function ready() { await until(async () => { if (child.exitCode !== null) throw new Error(output.replace(/token=[a-f0-9]+/g, 'token=[redacted]')); try { return (await fetch(`${base}/healthz`)).ok; } catch { return false; } }, 'Harness failed to become ready'); }
  let token;
  async function api(path, value) {
    const response = await fetch(`${base}/api${path}`, { method: value === undefined ? 'GET' : 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: value === undefined ? undefined : JSON.stringify(value) });
    const result = await response.json(); assert.ok(response.ok, JSON.stringify(result)); return result;
  }
  try {
  if (process.env.SAMPLE_RELEASE) execFileSync('sh', [resolve(process.env.SAMPLE_RELEASE, 'deployment/provision.sh')], { env: { ...process.env, SAMPLE_STATE: state } });
    start(); await ready(); token = (await readFile(join(state, 'access-token'), 'utf8')).trim();
    assert.equal((await fetch(`${base}/api/sessions`)).status, 401);
    const { id } = await api('/sessions', {});
    const streamAbort = new AbortController();
    const stream = await fetch(`${base}/api/sessions/${id}/events`, { headers: { Authorization: `Bearer ${token}` }, signal: streamAbort.signal });
    let streamed = '';
    const consume = (async () => { try { for await (const bytes of stream.body) streamed += Buffer.from(bytes).toString(); } catch (error) { if (error.name !== 'AbortError') throw error; } })();
    await api(`/sessions/${id}/messages`, { text: 'Run Bash and confirm the result.' });
    const first = await until(async () => { const s = await api(`/sessions/${id}`); return !s.running && s.events.some(e => e.type === 'turn/end') ? s : false; }, 'First turn did not finish');
    assert.ok(first.events.some(e => e.type === 'assistant/message' && e.text.includes('bash-ok')), JSON.stringify(first));
    await api(`/sessions/${id}/messages`, { text: 'Now use Python to sum zero through ten.' });
    const second = await until(async () => { const s = await api(`/sessions/${id}`); return !s.running && s.events.filter(e => e.type === 'turn/end').length === 2 ? s : false; }, 'Second turn did not finish');
    assert.ok(second.events.some(e => e.type === 'assistant/message' && e.text.includes('55')), JSON.stringify(second));
    assert.equal(second.events.filter(e => e.type === 'tool/result').length, 2);
    await until(() => streamed.includes('"kind":"delta"'), 'No streaming text delivered');
    streamAbort.abort(); await consume;
    await stop(); start(); await ready();
    const resumed = await api(`/sessions/${id}`);
    assert.deepEqual(resumed.events, second.events);
    assert.ok(requests[0].tools.some(tool => tool.function.name === 'execute_code'));
    assert.ok(requests[1].messages.some(message => message.role === 'tool' && message.content.includes('bash-ok')));
    if (process.env.SAMPLE_BROWSER === '1') {
      const harness = resolve(process.env.HARNESS_SOURCE || resolve(root, '../../../deepseek-harness'));
      const require = createRequire(resolve(harness, 'packages/experimental/inspector/package.json'));
      const { chromium } = require('playwright');
      const browser = await chromium.launch({ headless: true });
      try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });
        const errors = []; page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/#token=${token}`);
        await page.locator('#sessions button').first().click();
        await page.locator('.message.assistant').filter({ hasText: 'Execution confirmed: 55' }).waitFor();
        await page.locator('.tool-card summary').first().click();
        assert.ok((await page.locator('.tool-card').first().textContent()).includes('bash-ok'));
        await page.locator('#prompt').fill('Use Python once more and show the result.');
        await page.locator('#send').click();
        await page.waitForFunction(() => document.querySelectorAll('.tool-card').length === 3 && document.querySelector('#stop').hidden);
        await page.locator('.tool-card summary').last().click();
        assert.ok((await page.locator('.tool-card').last().textContent()).includes('55'));
        await page.screenshot({ path: process.env.SAMPLE_SCREENSHOT || '/tmp/asd-chat-verified.png', fullPage: true });
        await page.reload(); await page.locator('#sessions button').first().click();
        await page.waitForFunction(() => document.querySelectorAll('.tool-card').length === 3);
        assert.deepEqual(errors, []);
      } finally { await browser.close(); }
    }

  } finally { await stop(); await new Promise(r => provider.close(r)); await rm(state, { recursive: true, force: true }); }
});
