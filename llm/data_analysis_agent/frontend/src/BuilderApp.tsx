import { useEffect, useRef, useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { DataProfileCard } from './components/DataProfileCard';
import { jsonBody, request, streamProject } from './lib/projects';
import type { ProjectSummary, ProjectView, Scalar } from './lib/projects';

export default function BuilderApp() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [view, setView] = useState<ProjectView | null>(null);
  const [query, setQuery] = useState('');
  const [description, setDescription] = useState('');
  const [parameters, setParameters] = useState<Record<string, Scalar>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [inspector, setInspector] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [includeData, setIncludeData] = useState(true);
  const abort = useRef<AbortController | null>(null);
  const runId = useRef<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const selected = useRef<string | null>(null);

  const list = async () => setProjects(await request('/api/projects'));
  const load = async (id: string) => {
    selected.current = id;
    const result = await request<ProjectView>(`/api/projects/${id}`);
    if (selected.current !== id) return;
    setView(result); setDescription(result.project.description); setConfirmed(false);
    setParameters(result.display_run?.parameters || {});
  };
  useEffect(() => { list().catch(e => setError(e.message)); }, []);
  useEffect(() => () => { abort.current?.abort(); }, []);

  const create = async () => {
    try { const project = await request<ProjectSummary>('/api/projects', jsonBody({})); await list(); await load(project.id); setError(''); }
    catch (e: any) { setError(e.message); }
  };
  const upload = async (csv: File) => {
    if (!view) return;
    setBusy(true); setError(''); setStatus('Profiling CSV');
    const data = new FormData(); data.append('csv_file', csv); data.append('description', description);
    try { await request(`/api/projects/${view.project.id}/dataset`, { method: 'POST', body: data }); await load(view.project.id); await list(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); setStatus(''); if (file.current) file.current.value = ''; }
  };
  const operation = async (path: string, body: unknown) => {
    if (!view) return;
    setBusy(true); setError(''); setConfirmed(false); runId.current = null;
    abort.current = new AbortController();
    const id = view.project.id;
    try {
      await streamProject(path, body, event => {
        if (event.event === 'status') setStatus(event.message);
        if (event.event === 'step') setStatus(`${event.title}: ${event.status}${event.cached ? ' (reused)' : ''}`);
        if (event.event === 'run_started') runId.current = event.run_id;
        if (event.event === 'revision') setStatus('Validating project draft');
        if (event.event === 'run' && event.run.status !== 'succeeded') setError(event.run.error || 'Run failed');
        if (event.event === 'run' && event.run.status === 'succeeded') setError('');
        if (event.event === 'error') setError(event.message);
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== 'AbortError') setError(e.message); }
    finally { abort.current = null; setBusy(false); setStatus(''); await load(id); await list(); }
  };
  const cancel = async () => {
    if (view && runId.current) await request(`/api/projects/${view.project.id}/runs/${runId.current}/cancel`, jsonBody({})).catch(() => {});
    abort.current?.abort();
  };
  const accept = async () => {
    if (!view?.display_run) return;
    try { await request(`/api/projects/${view.project.id}/accept`, jsonBody({ run_id: view.display_run.run_id, cleanup_confirmed: confirmed })); await load(view.project.id); await list(); setError(''); }
    catch (e: any) { setError(e.message); }
  };
  const exportApplication = async () => {
    if (!view) return;
    try {
      const response = await fetch(`/api/projects/${view.project.id}/export?include_data=${includeData}`);
      if (!response.ok) { const failure = await response.json(); throw new Error(failure.detail); }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = 'saved-analysis-windows.zip'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000); setError('');
    } catch (e: any) { setError(e.message); }
  };
  const canAccept = view?.display_run?.revision_id === view?.draft?.revision_id && view?.display_run?.input_hash === view?.project.dataset_hash;
  const needsConfirmation = view?.display_run?.result?.cleanup_impacts.some(i => i.requires_confirmation);

  return <div className="platform">
    <header className="platform-header"><div><strong>Data Analysis Studio</strong><span>Linux builder</span></div>
      <button disabled={busy} onClick={() => setInspector(!inspector)}>{inspector ? 'Hide' : 'Show'} pipeline</button></header>
    <div className="builder-layout">
      <aside className="project-list"><button className="primary" disabled={busy} onClick={create}>New project</button>
        <button disabled={busy} onClick={async () => { setBusy(true); setError(''); setStatus('Validating the energy example');
          try { const example = await request<ProjectView>('/api/projects/examples/energy', jsonBody({})); await list(); await load(example.project.id); }
          catch (e: any) { setError(e.message); } finally { setBusy(false); setStatus(''); } }}>Load example system</button>
        {projects.map(p => <button key={p.id} disabled={busy} className={view?.project.id === p.id ? 'selected' : ''} onClick={() => load(p.id).catch(e => setError(e.message))}>
          <strong>{p.title}</strong><small>{p.dataset_name || 'No CSV'}{p.accepted_id ? ' · accepted' : ''}</small></button>)}
      </aside>
      <aside className="builder-chat">
        <h2>Build with chat</h2>
        {!view ? <p>Create or select a project to begin.</p> : <>
          <label>Column descriptions and business context<textarea value={description} disabled={busy} onChange={e => setDescription(e.target.value)} placeholder="Units, date format, and what each column means" /></label>
          <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={e => { if (e.target.files?.[0]) upload(e.target.files[0]); }} />
          <button disabled={busy} onClick={() => file.current?.click()}>{view.project.dataset_name ? 'Replace CSV' : 'Upload CSV'}</button>
          <small>{view.project.dataset_name || 'One CSV, up to 100 MB'}</small>
          <div className="project-messages" aria-live="polite">{view.messages.map((m, i) => <div key={i} className={`project-message ${m.role}`}><strong>{m.role === 'user' ? 'You' : 'Builder'}</strong><p>{m.content}</p></div>)}</div>
          <form onSubmit={e => { e.preventDefault(); const text = query.trim(); if (text) { setQuery(''); operation(`/api/projects/${view.project.id}/chat`, { query: text, description }); } }}>
            <textarea aria-label="Describe your dashboard" value={query} disabled={busy || !view.project.dataset_name} onChange={e => setQuery(e.target.value)} placeholder="Create an energy dashboard with zone filters and a monthly forecast…" />
            <button className="primary" disabled={busy || !query.trim() || !view.project.dataset_name}>Build or refine</button>
          </form>
        </>}
      </aside>
      <main className="preview-area">
        {error && <div className="error-banner" role="alert">{error}</div>}
        {busy && <div className="status-banner" role="status">{status || 'Working…'} {abort.current && <button onClick={cancel}>Cancel</button>}</div>}
        {view?.project.profile && <details className="profile-details"><summary>Input profile · {view.project.profile.row_count.toLocaleString()} rows · {view.project.profile.column_count} columns</summary><DataProfileCard profile={view.project.profile} /></details>}
        {view?.display_run && view.display_run.input_hash !== view.project.dataset_hash && <div className="status-banner">This preview shows the previous CSV. Validate the current input before acceptance.</div>}
        {view?.draft && <div className="revision-actions">
          <button disabled={busy} onClick={() => operation(`/api/projects/${view.project.id}/revisions/${view.draft!.revision_id}/run`, { parameters })}>Validate draft</button>
          {needsConfirmation && <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} /> I reviewed and approve the cleanup rules and their impact</label>}
          <button className="primary" disabled={busy || !canAccept || (needsConfirmation && !confirmed)} onClick={accept}>Accept revision</button>
          <label><input type="checkbox" checked={includeData} onChange={e => setIncludeData(e.target.checked)} /> Include CSV</label>
          <button disabled={busy || !view.project.accepted_id} onClick={exportApplication}>Export Windows app</button>
        </div>}
        <Dashboard revision={view?.display_revision || null} run={view?.display_run || null} parameters={parameters} onChange={setParameters} busy={busy}
          onApply={() => { if (view?.display_revision) operation(`/api/projects/${view.project.id}/revisions/${view.display_revision.revision_id}/run`, { parameters }); }}
          tableUrl={output => `/api/projects/${view?.project.id}/runs/${view?.display_run?.run_id}/tables/${output}`} />
      </main>
      {inspector && view && <aside className="pipeline-inspector"><h2>Pipeline and revisions</h2>
        {view.display_run?.result?.cleanup_impacts.map((impact, i) => <section key={i}><h3>{impact.title}</h3><p>{impact.rationale}</p>
          <p>Rows: {impact.before_rows} → {impact.after_rows}. Missing cells: {impact.before_missing_cells} → {impact.after_missing_cells}.</p>
          <p>Changed cells in matched rows: {impact.changed_cells_in_matched_rows ?? 'Row matching unavailable'}.</p>
          {!!impact.columns_removed.length && <p>Removed columns: {impact.columns_removed.join(', ')}</p>}</section>)}
        {view.draft?.steps.map(step => <details key={step.id}><summary>{step.title} · {step.stage}</summary><p>{step.rationale}</p><small>{step.inputs.join(', ')} → {step.outputs.join(', ')}</small><pre>{step.code}</pre></details>)}
        <h3>Saved revisions</h3>{view.revisions.map(r => <section key={r.id}><small>{r.id.slice(0, 8)}{r.accepted ? ' · accepted' : ' · draft'}</small><p>{r.summary}</p>
          {!!r.accepted && <button disabled={busy} onClick={async () => { try { await request(`/api/projects/${view.project.id}/revisions/${r.id}/rollback`, jsonBody({})); await load(view.project.id); setError(''); } catch (e: any) { setError(e.message); } }}>Restore revision</button>}</section>)}
      </aside>}
    </div>
  </div>;
}
