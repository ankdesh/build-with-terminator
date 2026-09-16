/** Product-owned Harness plugin: chat HTTP API, streamed transcript, and scoped execution tools. */
import { randomUUID, timingSafeEqual } from 'node:crypto';
import { mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import { SessionId } from '@deepseek-ai/dsh-session';
import { executeCode } from './execution.mjs';

export const name = 'asd-sample';
export const inject = ['webServer', 'agentLoop', 'agents', 'sessions', 'sessionPersistence', 'tools'];
export const Config = z.object({
  token: z.string().min(24).required(),
  model: z.string().min(1).required(),
  provider: z.string().min(1).required(),
  workspaceRoot: z.string().min(1).required(),
  python: z.string().min(1).required(),
  timeoutMs: z.number().min(1).max(600000).required(),
  maxOutputBytes: z.number().min(1024).max(1048576).required(),
  maxSessions: z.number().min(1).max(100).required(),
});

function project(event) {
  const { type, seq, data } = event;
  if (type === 'user/message') return { type, seq, text: data.content.filter(b => b.type === 'text').map(b => b.text).join('\n') };
  if (type === 'assistant/message') return { type, seq, text: data.message.content.filter(b => b.type === 'text').map(b => b.text).join('\n'), interrupted: !!data.interrupted };
  if (type === 'tool/call') return { type, seq, callId: data.callId, name: data.name, arguments: data.arguments };
  if (type === 'tool/result') return { type, seq, message: data.message };
  if (type === 'turn/end') return { type, seq, data };
  return null;
}
function json(res, status, data) { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(data)); }
async function body(req) {
  if (!req.headers['content-type']?.startsWith('application/json')) throw new Error('Expected application/json');
  let size = 0; const chunks = [];
  for await (const chunk of req) { size += chunk.length; if (size > 65536) throw new Error('Request exceeds 64 KiB'); chunks.push(chunk); }
  return JSON.parse(Buffer.concat(chunks).toString());
}
function authorized(req, token) {
  const got = Buffer.from(req.headers.authorization || ''); const expected = Buffer.from(`Bearer ${token}`);
  return got.length === expected.length && timingSafeEqual(got, expected);
}

/** Mount the product API as effects owned by the normal dsh profile lifecycle. */
export function apply(ctx, config) {
  const handles = new Map(), pending = new Map(), running = new Map(), subscribers = new Map();
  let closing = false;
  const options = { provider: config.provider, model: config.model };
  const publish = (id, packet) => {
    for (const res of subscribers.get(id) || []) {
      if (res.samplePending) res.samplePending.push(packet);
      else if (!res.write(`data: ${JSON.stringify(packet)}\n\n`)) res.destroy();
    }
  };
  const setup = cwd => agentCtx => {
    agentCtx.effect(() => agentCtx.tools.register(defineTool({
      name: 'execute_code',
      description: 'Run Bash or Python code in this conversation workspace. Use it for computations, file processing, and commands requested by the user. Inspect stdout, stderr and exit status before reporting success. Python uses the configured virtual environment. Execution has local service-user filesystem and network access.',
      parameters: {
        language: { type: 'string', enum: ['bash', 'python'], required: true },
        code: { type: 'string', required: true, description: 'Complete executable program.' },
      },
      output: { schema: { type: 'json' }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
      execute: (args, exec) => executeCode(args, { ...config, cwd, signal: exec.signal }),
    })));
  };
  async function getHandle(id, create = false) {
    if (closing) throw new Error('Service is shutting down');
    if (!/^[a-f0-9-]{36}$/.test(id)) throw new Error('Invalid session identifier');
    if (handles.has(id)) return handles.get(id);
    if (pending.has(id)) return pending.get(id);
    if (handles.size + pending.size >= config.maxSessions) throw new Error('Active conversation limit reached; restart to unload idle conversations');
    const task = (async () => {
      const cwd = join(config.workspaceRoot, id); await mkdir(cwd, { recursive: true, mode: 0o700 });
      const handle = create
        ? await ctx.agents.create({ sessionId: SessionId(id), meta: { cwd }, agentOptions: options, setup: setup(cwd) })
        : await ctx.agents.resume({ resumeSessionId: SessionId(id), agentOptions: options, setup: setup(cwd) });
      if (closing) { await handle.dispose(); throw new Error('Service is shutting down'); }
      handles.set(id, handle); return handle;
    })();
    pending.set(id, task);
    try { return await task; } finally { pending.delete(id); }
  }
  const snapshot = async handle => {
    await ctx.sessions.flush(handle.agent.session);
    const reader = await ctx.sessionPersistence.open(handle.agent.session.id, 'read');
    try { return (await reader.read(0, 2000)).events.map(project).filter(Boolean); }
    finally { await reader.close(); }
  };
  ctx.on('session/event', (session, event) => {
    const value = project(event); if (value) publish(session.id, { kind: 'event', event: value });
  });
  ctx.on('agent/assistant-stream', ({ agent, frame }) => {
    if (frame.type === 'start') publish(agent.session.id, { kind: 'stream-start' });
    if (frame.type === 'chunk' && frame.chunk.type === 'text-delta') publish(agent.session.id, { kind: 'delta', text: frame.chunk.text });
  });
  ctx.effect(() => ctx.webServer.register({ kind: 'prefix', path: '/api', handler: async (req, res) => {
    try {
      if (!authorized(req, config.token)) return json(res, 401, { error: 'Connect using the access link printed by the launcher.' });
      if (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`) return json(res, 403, { error: 'Origin refused' });
      const path = new URL(req.url, 'http://localhost').pathname;
      if (path === '/api/config' && req.method === 'GET') return json(res, 200, { model: config.model, provider: config.provider });
      if (path === '/api/sessions' && req.method === 'GET') {
        const stored = await ctx.sessionPersistence.list();
        return json(res, 200, stored.map(({ header }) => ({ id: header.id, createdAt: header.createdAt })).reverse());
      }
      if (path === '/api/sessions' && req.method === 'POST') {
        await body(req); const id = randomUUID(); await getHandle(id, true); await ctx.sessionPersistence.flush(); return json(res, 201, { id });
      }
      const match = path.match(/^\/api\/sessions\/([a-f0-9-]{36})(?:\/(events|messages|cancel))?$/);
      if (!match) return json(res, 404, { error: 'Unknown endpoint' });
      const [, id, action] = match; const handle = await getHandle(id);
      if (!action && req.method === 'GET') return json(res, 200, { id, events: await snapshot(handle), running: running.has(id) });
      if (action === 'events' && req.method === 'GET') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' });
        const clients = subscribers.get(id) || new Set(); subscribers.set(id, clients); clients.add(res); res.samplePending = [];
        res.write(`data: ${JSON.stringify({ kind: 'snapshot', events: await snapshot(handle), running: running.has(id) })}\n\n`);
        const queued = res.samplePending; res.samplePending = null;
        for (const packet of queued) res.write(`data: ${JSON.stringify(packet)}\n\n`);
        const heartbeat = setInterval(() => res.write(': keepalive\n\n'), 15000);
        res.on('close', () => { clearInterval(heartbeat); clients.delete(res); if (!clients.size) subscribers.delete(id); });
        return;
      }
      if (action === 'cancel' && req.method === 'POST') {
        await body(req); handle.agent.cancel({ kind: 'user' }); await running.get(id); return json(res, 200, { cancelled: true });
      }
      if (action === 'messages' && req.method === 'POST') {
        const input = await body(req);
        if (typeof input.text !== 'string' || !input.text.trim() || input.text.length > 24000) return json(res, 400, { error: 'Enter between 1 and 24,000 characters.' });
        if (running.has(id)) return json(res, 409, { error: 'This conversation already has an active request.' });
        // This API admits one message per idle interval, so whenIdle covers the interval we own.
        const task = Promise.resolve().then(async () => {
          publish(id, { kind: 'status', running: true });
          handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: input.text }], source: { kind: 'user' } }));
          await handle.agent.whenIdle(); await ctx.sessionPersistence.flush();
        }).catch(error => publish(id, { kind: 'error', error: error.message })).finally(() => {
          running.delete(id); publish(id, { kind: 'status', running: false });
        });
        running.set(id, task);
        return json(res, 202, { accepted: true });
      }
      return json(res, 405, { error: 'Method not allowed' });
    } catch (error) { if (!res.headersSent) json(res, 400, { error: error.message }); else res.destroy(); }
  } }));
  ctx.effect(() => ctx.webServer.register({ kind: 'exact', path: '/healthz', handler: (_req, res) => json(res, 200, { status: 'ready' }) }));
  const assets = new Map([['/', ['index.html', 'text/html']], ['/app.js', ['app.js', 'text/javascript']], ['/style.css', ['style.css', 'text/css']]]);
  for (const [path, [file, mime]] of assets) ctx.effect(() => ctx.webServer.register({ kind: 'exact', path, handler: async (_req, res) => {
    const content = await readFile(fileURLToPath(new URL(`../web/${file}`, import.meta.url)));
    res.writeHead(200, { 'Content-Type': `${mime}; charset=utf-8`, 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'" }); res.end(content);
  } }));
  ctx.on('dispose', async () => {
    closing = true;
    for (const clients of subscribers.values()) for (const res of clients) res.end();
    subscribers.clear();
    await Promise.allSettled(pending.values());
    await Promise.all([...handles.values()].map(handle => handle.dispose()));
    await Promise.all(running.values());
    handles.clear();
  });
}
