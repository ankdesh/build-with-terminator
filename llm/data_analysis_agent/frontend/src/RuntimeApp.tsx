import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, BarChart3, CheckCircle2, ChevronDown, Database, FileUp, Info, Loader2, RefreshCw, SlidersHorizontal, X } from 'lucide-react';
import { Dashboard, DashboardControls } from './components/Dashboard';
import { jsonBody, request } from './lib/projects';
import type { RuntimeState, Scalar } from './lib/projects';

export default function RuntimeApp() {
  const [state, setState] = useState<RuntimeState | null>(null);
  const [parameters, setParameters] = useState<Record<string, Scalar>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(true);
  const [filters, setFilters] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const initial = useRef(false);
  const signature = useRef('');
  const stateRef = useRef<RuntimeState | null>(null);
  const load = useCallback(async () => {
    const value = await request<RuntimeState>('/api/runtime/state');
    const previous = stateRef.current;
    if (previous && previous.instance_id === value.instance_id && previous.sequence > value.sequence) return previous;
    if (previous?.display_run?.run_id === value.display_run?.run_id) value.display_run = previous?.display_run || value.display_run;
    stateRef.current = value;
    setState(value);
    const nextSignature = `${value.revision?.revision_id}:${value.display_run?.run_id}`;
    if (signature.current !== nextSignature) {
      signature.current = nextSignature;
      setParameters(value.display_run?.parameters || Object.fromEntries((value.revision?.parameters || []).map(p => [p.id, p.default])));
    }
    return value;
  }, []);
  const perform = async (path: string, init: RequestInit = jsonBody({ parameters })) => {
    setBusy(true); setError('');
    try {
      await request(path, init);
      await load();
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); if (input.current) input.current.value = ''; }
  };
  useEffect(() => {
    let disposed = false;
    load().then(value => {
      if (!disposed && !initial.current && value.mode === 'runtime' && value.has_input && !value.display_run && !value.active_run) {
        initial.current = true;
        setBusy(true);
        request('/api/runtime/run', jsonBody({ parameters: {} })).then(load).catch(e => setError(e.message)).finally(() => setBusy(false));
      }
    }).catch(e => setError(e.message));
    const stream = new EventSource('/api/runtime/events');
    stream.onopen = () => { setConnected(true); load().catch(() => {}); };
    stream.onmessage = () => load().catch(() => setConnected(false));
    stream.onerror = () => setConnected(false);
    return () => { disposed = true; stream.close(); };
  }, [load]);
  const active = busy || Boolean(state?.active_run);
  const revision = state?.presentation ? {
    revision_id: state.revision?.revision_id || 'pending', title: state.presentation.title, summary: '', steps: [],
    parameters: state.revision?.parameters || [], dashboard: state.presentation.dashboard,
  } : state?.revision || null;
  const latest = state?.events[state.events.length - 1];
  const status = latest?.message || (latest?.title ? `${latest.title}: ${latest.status}` : 'Running saved analysis…');
  const summary = state?.revision?.parameters.filter(p => p.filter_column && state.display_run?.parameters[p.id] != null)
    .map(p => `${p.label}: ${state.display_run?.parameters[p.id]}`).join(' · ');
  return <div className="platform target-platform">
    <header className="target-header"><a href="/" className="brand" aria-label="Dashboard home"><span className="brand-mark"><BarChart3 size={22} /></span><div><strong>{revision?.title || 'Analysis dashboard'}</strong><span>{state?.mode === 'live' ? 'Development dashboard' : 'Saved analysis application'}</span></div></a>
      <div className="target-header-actions"><span className={`connection-label ${connected ? '' : 'disconnected'}`}><span />{connected ? 'Runs locally' : 'Connection lost'}</span>
        <button className="primary" disabled={active || !state?.revision} onClick={() => input.current?.click()}><FileUp size={16} /> Upload CSV</button></div>
      <input type="file" ref={input} hidden accept=".csv,text/csv" onChange={e => {
        const csv = e.target.files?.[0]; if (!csv) return;
        const data = new FormData(); data.append('csv_file', csv); perform('/api/runtime/upload', { method: 'POST', body: data });
      }} />
    </header>
    <main className="target-main">
      <div className="target-toolbar"><div className="dataset-summary"><Database size={16} /><strong>{state?.dataset_name || 'Waiting for input'}</strong>
        {state?.display_run?.finished_at && <span>Updated {new Date(state.display_run.finished_at).toLocaleString()}</span>}</div>
        <div className="button-row"><button disabled={active || !state?.has_input} onClick={() => perform('/api/runtime/run')}><RefreshCw size={15} /> Refresh</button>
          {!!state?.revision?.parameters.length && <button className={filters ? 'selected' : ''} onClick={() => setFilters(!filters)} aria-expanded={filters}><SlidersHorizontal size={15} /> Filters and scenarios<ChevronDown size={13} /></button>}</div>
      </div>
      {!connected && <div className="status-banner" role="status">The server connection is unavailable. The last loaded results remain visible.</div>}
      {state?.mode === 'live' && state.pending && <div className="pending-banner" role="status"><Activity size={17} /><div>
        <strong>{state.calculation_pending ? 'Calculation changes pending' : state.last_error ? 'Developer update waiting' : 'Applying developer update'}</strong>
        <p>{state.calculation_pending ? 'The developer must select Run to apply the latest calculations. Current results use the last successful revision.' :
          state.last_error ? 'The latest revision could not run on the current dashboard input. Upload a compatible CSV or return to the builder data.' : 'The validated revision is being applied. The last successful results stay visible.'}</p>
        {!state.calculation_pending && state.last_error && state.input_mode === 'replacement' && <button disabled={active} onClick={() => perform('/api/runtime/use-builder-data', jsonBody({}))}>Use builder data</button>}
      </div></div>}
      {(error || state?.last_error) && <div className="error-banner" role="alert"><strong>{error || state?.last_error}</strong>{state?.display_run && <p>The last successful dashboard is retained.</p>}</div>}
      {state?.control_notice && <div className="status-banner">{state.control_notice}</div>}
      {active && <div className="status-banner" role="status"><span className="button-row"><Loader2 className="spin" size={16} />{status}</span><button onClick={() => perform('/api/runtime/cancel', jsonBody({}))}>Cancel</button></div>}
      {filters && <aside className="target-filters" aria-label="Dashboard filters"><button className="icon-button filter-close" onClick={() => setFilters(false)} aria-label="Close filters"><X size={17} /></button>
        <DashboardControls revision={state?.revision || null} run={state?.display_run || null} parameters={parameters} onChange={setParameters}
          onApply={() => { perform('/api/runtime/run'); setFilters(false); }} busy={active} />
      </aside>}
      {summary && <div className="active-filter-summary"><SlidersHorizontal size={13} />{summary}<button disabled={active} onClick={() => {
        const cleared = { ...state?.display_run?.parameters };
        state?.revision?.parameters.filter(parameter => parameter.filter_column).forEach(parameter => { cleared[parameter.id] = parameter.default; });
        setParameters(cleared); perform('/api/runtime/run', jsonBody({ parameters: cleared }));
      }}>Clear filters</button></div>}
      {!state?.revision && <div className="target-waiting"><span className="type-tag">Live design</span><h2>The dashboard is taking shape</h2><p>Design changes appear here as the workspace is saved. The first calculation starts when the developer selects Run.</p></div>}
      <Dashboard revision={revision} run={state?.display_run || null} appliedRevision={state?.revision} parameters={parameters} onChange={setParameters}
        onApply={() => perform('/api/runtime/run')} busy={active} showControls={false}
        emptyMessage={state?.mode === 'live' ? 'The developer is designing this dashboard. Keep this window open to see changes.' : 'Upload a compatible CSV to run this analysis.'}
        tableUrl={output => `/api/runtime/tables/${output}`} />
      <footer className="target-footer"><span><CheckCircle2 size={14} />{state?.display_run ? 'Showing the last successful analysis' : 'Ready for a validated analysis'}</span>
        <details><summary><Info size={14} /> Data and revision</summary><div className="source-details"><p>Dataset: {state?.dataset_name || 'No dataset'}</p><p>Revision: {state?.revision?.revision_id || 'Not yet run'}</p><p>Input: {state?.display_run?.input_hash || 'Not yet run'}</p>
          <p>Data source: {state?.input_mode === 'replacement' ? 'Separate dashboard CSV' : state?.mode === 'live' ? 'Builder CSV' : 'Local application CSV'}</p>
          {state?.mode === 'live' && state.input_mode === 'replacement' && <button disabled={active} onClick={() => perform('/api/runtime/use-builder-data', jsonBody({}))}>Use builder data</button>}</div></details>
      </footer>
    </main>
  </div>;
}
