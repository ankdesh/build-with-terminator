const $ = id => document.getElementById(id);
const token = new URLSearchParams(location.hash.slice(1)).get('token');
if (token) { sessionStorage.setItem('asd-token', token); history.replaceState(null, '', location.pathname); }
const access = sessionStorage.getItem('asd-token');
let current = null, streaming = null, streamController = null, busy = false;
let events = [], liveText = '', titles = JSON.parse(localStorage.getItem('asd-titles') || '{}');
async function api(path, data) {
  const response = await fetch(`/api${path}`, { method: data === undefined ? 'GET' : 'POST', headers: { Authorization: `Bearer ${access}`, ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: data === undefined ? undefined : JSON.stringify(data) });
  const result = await response.json(); if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`); return result;
}
function notice(text = '') { $('notice').textContent = text; $('notice').hidden = !text; }
function status(value) { busy = value; $('stop').hidden = !value; $('send').disabled = value; }
function element(tag, className, text) { const value = document.createElement(tag); if (className) value.className = className; if (text !== undefined) value.textContent = text; return value; }
function render() {
  const area = $('transcript'); area.replaceChildren();
  $('welcome').hidden = events.some(e => e.type === 'user/message'); area.hidden = !$('welcome').hidden;
  const calls = new Map();
  for (const event of events) {
    if (event.type === 'user/message' || event.type === 'assistant/message') {
      if (!event.text) continue;
      const role = event.type === 'user/message' ? 'user' : 'assistant';
      const row = element('div', `message ${role}`); row.append(element('span', 'role', role === 'user' ? 'YOU' : 'ASD')); row.append(document.createTextNode(event.text)); area.append(row);
    } else if (event.type === 'tool/call') {
      let args; try { args = JSON.parse(event.arguments); } catch { args = { code: event.arguments }; }
      const card = element('details', 'tool-card'); const summary = element('summary', '', `${args.language === 'python' ? '⌘ Python' : '›_ Bash'} · ${event.name}`); summary.append(element('span', '', 'Running')); card.append(summary, element('pre', '', args.code || event.arguments)); calls.set(event.callId, card); area.append(card);
    } else if (event.type === 'tool/result') {
      const blocks = event.message.content || [];
      for (const block of blocks) {
        if (block.type !== 'tool-result') continue;
        const card = calls.get(block.toolCallId || block.callId || event.message.source?.callId);
        const text = (block.content || []).map(part => part.text || '').join('\n');
        if (card) {
          let result; try { result = JSON.parse(text); } catch { result = null; }
          card.querySelector('summary span').textContent = result ? (result.timedOut ? 'Timed out' : result.aborted ? 'Stopped' : result.exitCode === 0 ? 'Completed' : 'Failed') : block.isError ? 'Failed' : 'Completed';
          card.append(element('pre', 'result', result ? [result.stdout, result.stderr, `Exit ${result.exitCode ?? result.signal}${result.truncated ? ' · Output truncated' : ''}`].filter(Boolean).join('\n') : text));
        }
      }
    } else if (event.type === 'turn/end' && event.data.reason?.kind === 'error') area.append(element('p', 'error', event.data.reason.error?.message || 'The model request failed. Check the model configuration and try again.'));
  }
  if (liveText) { const row = element('div', 'message assistant streaming'); row.append(element('span', 'role', 'ASD'), document.createTextNode(liveText)); area.append(row); }
}
async function list() {
  const sessions = await api('/sessions'); $('sessions').replaceChildren();
  for (const session of sessions) { const button = element('button', session.id === current ? 'active' : '', titles[session.id] || 'Untitled conversation'); button.onclick = () => select(session.id).catch(error => notice(error.message)); $('sessions').append(button); }
}
async function select(id) {
  streamController?.abort(); current = id; liveText = ''; events = []; status(false);
  $('conversation-label').textContent = titles[id] || 'New conversation';
  const controller = new AbortController(); streamController = controller;
  streaming = connect(id, controller.signal).catch(error => { if (error.name !== 'AbortError') notice(error.message); });
  await list();
}
async function connect(id, signal) {
  while (!signal.aborted) {
    const response = await fetch(`/api/sessions/${id}/events`, { headers: { Authorization: `Bearer ${access}` }, signal });
    if (!response.ok) throw new Error((await response.json()).error);
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader(); let buffer = '';
    while (true) {
      const { value, done } = await reader.read(); if (done) break; buffer += value;
      let end;
      while ((end = buffer.indexOf('\n\n')) >= 0) {
        const line = buffer.slice(0, end); buffer = buffer.slice(end + 2); if (!line.startsWith('data: ')) continue;
        const packet = JSON.parse(line.slice(6));
        if (packet.kind === 'snapshot') { events = packet.events; liveText = ''; status(packet.running); render(); }
        if (packet.kind === 'event') { if (!events.some(event => event.seq === packet.event.seq)) events.push(packet.event); if (packet.event.type === 'assistant/message') liveText = ''; render(); }
        if (packet.kind === 'stream-start') liveText = '';
        if (packet.kind === 'delta') { liveText += packet.text; render(); }
        if (packet.kind === 'status') status(packet.running);
        if (packet.kind === 'error') notice(packet.error);
      }
    }
    if (!signal.aborted) await new Promise(resolve => setTimeout(resolve, 1500));
  }
}
async function send(text) {
  if (!text.trim() || busy) return; notice();
  if (!current) { const { id } = await api('/sessions', {}); await select(id); }
  if (!titles[current]) { titles[current] = text.slice(0, 42); localStorage.setItem('asd-titles', JSON.stringify(titles)); $('conversation-label').textContent = titles[current]; await list(); }
  status(true);
  try { await api(`/sessions/${current}/messages`, { text }); $('prompt').value = ''; } catch (error) { status(false); throw error; }
}
$('composer').onsubmit = event => { event.preventDefault(); send($('prompt').value).catch(error => notice(error.message)); };
$('prompt').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('composer').requestSubmit(); } };
$('new-chat').onclick = () => { streamController?.abort(); current = null; events = []; liveText = ''; status(false); render(); $('conversation-label').textContent = 'New conversation'; $('prompt').focus(); list().catch(error => notice(error.message)); };
$('stop').onclick = () => api(`/sessions/${current}/cancel`, {}).catch(error => notice(error.message));
for (const button of document.querySelectorAll('[data-prompt]')) button.onclick = () => { $('prompt').value = button.dataset.prompt; $('prompt').focus(); };
if (!access) { notice('Open the access link printed by the launcher to connect to this workspace.'); $('model').textContent = 'Disconnected'; }
else { api('/config').then(config => { $('model').textContent = config.model; return list(); }).catch(error => notice(error.message)); }
