import { useEffect, useRef, useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { jsonBody, request } from './lib/projects';
import type { Revision, Run, Scalar } from './lib/projects';

interface State { revision: Revision; display_run: Run | null; dataset_name: string | null; has_input: boolean;
  last_error: string | null; active_run: Run | null; events: { title: string; status: string }[] }

export default function RuntimeApp() {
  const [state, setState] = useState<State | null>(null);
  const [parameters, setParameters] = useState<Record<string, Scalar>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const initial = useRef(false);
  const load = async () => {
    const value = await request<State>('/api/runtime/state'); setState(value); return value;
  };
  const apply = async (body: Record<string, Scalar> = parameters) => {
    setBusy(true); setError('');
    try { const response = await request<{ state: State }>('/api/runtime/run', jsonBody({ parameters: body }));
      setState(response.state); setParameters(response.state.display_run?.parameters || body); setError(response.state.last_error || '');
    } catch (e: any) { setError(e.message); await load(); }
    finally { setBusy(false); setStatus(''); }
  };
  useEffect(() => {
    load().then(value => {
      setParameters(value.display_run?.parameters || Object.fromEntries(value.revision.parameters.map(p => [p.id, p.default])));
      if (!initial.current && value.has_input && !value.display_run && !value.active_run) { initial.current = true; apply({}); }
    }).catch(e => setError(e.message));
  }, []);
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => request<State>('/api/runtime/state').then(value => {
      const last = value.events[value.events.length - 1]; setStatus(last ? `${last.title}: ${last.status}` : 'Running saved pipeline…');
    }).catch(() => {}), 500);
    return () => clearInterval(timer);
  }, [busy]);
  const upload = async (file: File) => {
    setBusy(true); setError('');
    const data = new FormData(); data.append('csv_file', file);
    try { const response = await request<{ state: State }>('/api/runtime/upload', { method: 'POST', body: data });
      setState(response.state); setParameters(response.state.display_run?.parameters || {}); setError(response.state.last_error || '');
    } catch (e: any) { setError(e.message); await load(); }
    finally { setBusy(false); setStatus(''); if (input.current) input.current.value = ''; }
  };
  return <div className="platform">
    <header className="platform-header"><div><strong>{state?.revision.title || 'Saved analysis dashboard'}</strong><span>Offline application</span></div>
      <input type="file" ref={input} hidden accept=".csv,text/csv" onChange={e => { if (e.target.files?.[0]) upload(e.target.files[0]); }} />
      <button className="primary" disabled={busy} onClick={() => input.current?.click()}>Upload replacement CSV</button>
    </header>
    <main className="runtime-area">
      {(error || state?.last_error) && <div className="error-banner" role="alert">{error || state?.last_error} {state?.display_run && 'The last successful dashboard is retained.'}</div>}
      {busy && <div className="status-banner" role="status">{status || 'Running saved pipeline…'} <button onClick={() => request('/api/runtime/cancel', jsonBody({})).catch(e => setError(e.message))}>Cancel</button></div>}
      {!state?.has_input && <div className="status-banner">Upload a compatible CSV to run this application.</div>}
      {state?.has_input && <button disabled={busy} onClick={() => apply()}>Refresh dashboard</button>}
      <Dashboard revision={state?.revision || null} run={state?.display_run || null} parameters={parameters} onChange={setParameters} onApply={() => apply()} busy={busy}
        emptyMessage="Upload a compatible CSV to run the saved analysis."
        tableUrl={output => `/api/runtime/tables/${output}`} />
    </main>
  </div>;
}
