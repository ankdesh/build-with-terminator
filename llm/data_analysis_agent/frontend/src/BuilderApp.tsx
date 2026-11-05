import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity, ArrowDownToLine, ArrowRight, BarChart3, Check, CheckCircle2, ChevronDown, ChevronUp, CircleHelp, Copy,
  Database, ExternalLink, FileUp, History, LayoutDashboard, ListTree, Loader2, MessageSquare,
  PanelRightClose, PanelRightOpen, Pencil, Play, Plus, Power, Redo2, Rocket, RotateCcw, Send, Settings2,
  Sparkles, Square, Trash2, Undo2, X,
} from 'lucide-react';
import { Dashboard } from './components/Dashboard';
import { DataProfileCard } from './components/DataProfileCard';
import { StageCanvas } from './components/StageCanvas';
import { ChatReview } from './components/ChatReview';
import { StageInspector } from './components/StageInspector';
import { PropertiesPanel } from './components/PropertiesPanel';
import { SettingsField, ControlSettings } from './components/SettingsFields';
import { jsonBody, request, streamProject } from './lib/projects';
import type { Job, ProjectSummary, ProjectView, Stage, Target, WorkspaceDocument } from './lib/projects';

type Page = 'data' | 'pipeline' | 'dashboard' | 'history';
const navigation = [{ id: 'data', title: 'Data', icon: Database }, { id: 'pipeline', title: 'Pipeline', icon: ListTree },
  { id: 'dashboard', title: 'Dashboard', icon: LayoutDashboard }, { id: 'history', title: 'History', icon: History }] as const;
const stopped: Target = { status: 'stopped', url: null, port: null, error: null };

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="studio-dialog" onCancel={event => { event.preventDefault(); onClose(); }} aria-label={title}>
    <header><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button></header>{children}
  </dialog>;
}

export default function BuilderApp() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [view, setView] = useState<ProjectView | null>(null);
  const [page, setPage] = useState<Page>('pipeline');
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [description, setDescription] = useState('');
  const [dock, setDock] = useState<'chat' | 'properties' | 'inspect'>('chat');
  const [developer, setDeveloper] = useState(false);
  const [dockOpen, setDockOpen] = useState(true);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [target, setTarget] = useState<Target>(stopped);
  const [targetBusy, setTargetBusy] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [status, setStatus] = useState('');
  const [connected, setConnected] = useState(true);
  const [logsOpen, setLogsOpen] = useState(false);
  const [includeData, setIncludeData] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [projectSettings, setProjectSettings] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [deletion, setDeletion] = useState<{stage: Stage; affected: Stage[]; version: number} | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const chatEnd = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);
  const current = useRef<string | null>(null);
  const viewRef = useRef<ProjectView | null>(null);
  const savingRef = useRef(false);
  const initialized = useRef(false);
  const updateView = useCallback((value: ProjectView) => {
    if (viewRef.current?.project.id === value.project.id && viewRef.current.display_run?.run_id === value.display_run?.run_id) {
      value.display_run = viewRef.current.display_run;
    }
    viewRef.current = value; setView(value);
  }, []);
  const list = useCallback(async () => { const values = await request<ProjectSummary[]>('/api/projects'); setProjects(values); return values; }, []);
  const refresh = useCallback(async (id: string) => {
    if (savingRef.current) return;
    const [value, records, runtime] = await Promise.all([
      request<ProjectView>(`/api/projects/${id}`), request<Job[]>(`/api/projects/${id}/jobs`), request<Target>(`/api/projects/${id}/target`),
    ]);
    if (current.current !== id || savingRef.current) return;
    updateView(value); setJobs(records); setTarget(runtime);
  }, [updateView]);
  const chooseProject = useCallback((id: string) => {
    current.current = id; setProjectId(id); setSelected(null); setQuery(''); setError(''); setNotice(''); setJobs([]); setTarget(stopped);
    localStorage.setItem('wps:studio:project', id);
    const url = new URL(window.location.href); url.searchParams.set('project', id); window.history.replaceState(null, '', url);
  }, []);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    request<{developer_mode: boolean}>('/api/capabilities').then(value => setDeveloper(value.developer_mode)).catch(() => {});
    const url = new URL(window.location.href);
    const initialPage = url.searchParams.get('view');
    if (navigation.some(p => p.id === initialPage)) setPage(initialPage as Page);
    list().then(values => {
      const preferred = url.searchParams.get('project') || localStorage.getItem('wps:studio:project');
      const initial = values.find(p => p.id === preferred) || values[0];
      if (initial) chooseProject(initial.id);
    }).catch(e => setError(e.message));
  }, [list, chooseProject]);
  useEffect(() => {
    if (!projectId) return;
    let disposed = false;
    current.current = projectId;
    refresh(projectId).then(() => { if (!disposed && viewRef.current?.project.id === projectId) setDescription(viewRef.current.project.description); }).catch(e => setError(e.message));
    setTargetBusy(true);
    request<Target>(`/api/projects/${projectId}/target/start`, jsonBody({})).then(value => { if (!disposed) setTarget(value); })
      .catch(e => { if (!disposed) setError(e.message); }).finally(() => { if (!disposed) setTargetBusy(false); });
    const stream = new EventSource(`/api/projects/${projectId}/events`);
    let timer: number | undefined;
    const update = () => { clearTimeout(timer); timer = window.setTimeout(() => refresh(projectId).catch(() => {}), 60); };
    stream.onmessage = update;
    stream.onopen = () => { setConnected(true); update(); };
    stream.onerror = () => setConnected(false);
    const poll = window.setInterval(() => request<Target>(`/api/projects/${projectId}/target`).then(value => { if (!disposed) setTarget(value); }).catch(() => {}), 2500);
    return () => { disposed = true; stream.close(); clearTimeout(timer); clearInterval(poll); };
  }, [projectId, refresh]);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [view?.messages.length, chatBusy]);
  useEffect(() => () => abort.current?.abort(), []);
  const activeJob = jobs.find(job => ['queued', 'running'].includes(job.status));
  const latestJob = jobs[0];
  const working = chatBusy || saving;
  const document = view?.workspace.document;
  const workspace = view?.workspace;
  const lastEvent = activeJob?.events[activeJob.events.length - 1];
  const progress = status || lastEvent?.message || (lastEvent?.title ? `${lastEvent.title}: ${lastEvent.status}` : activeJob ? 'Waiting for the execution slot' : '');
  const needsConfirmation = view?.display_run?.result?.cleanup_impacts.some(impact => impact.requires_confirmation);
  const stage = workspace?.stages.find(s => s.id === selected);
  const categoryLabel = ({'category:input': 'Data input', 'category:cleaning': 'Data cleaning', 'category:analysis': 'Analysis', 'category:visualization': 'Visualization'} as Record<string, string>)[selected || ''];
  const context = categoryLabel ? { stage_id: selected, label: `${categoryLabel} · Create or edit stages` } : stage ? { stage_id: stage.id, label: `${{input: 'Data input', cleaning: 'Data cleaning', analysis: 'Analysis', visualization: 'Visualization'}[stage.type]} · ${stage.title}` } : { stage_id: null, label: 'Project' };
  useEffect(() => { if (selected && !categoryLabel && workspace && !workspace.stages.some(s => s.id === selected)) setSelected(null); }, [selected, workspace, categoryLabel]);

  const navigate = (next: Page) => {
    setPage(next);
    const url = new URL(window.location.href); url.searchParams.set('view', next); window.history.replaceState(null, '', url);
  };
  const create = async (example = false) => {
    setSaving(true); setError('');
    try {
      const result = example ? await request<ProjectView>('/api/projects/examples/energy', jsonBody({})) : null;
      const project = result?.project || await request<ProjectSummary>('/api/projects', jsonBody({}));
      await list(); chooseProject(project.id); setDescription('');
      if (result) updateView(result);
      navigate(example ? 'pipeline' : 'data');
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };
  const save = async (next: WorkspaceDocument, action: 'edit' | 'undo' | 'redo' = 'edit') => {
    const base = viewRef.current;
    if (!base || savingRef.current) return;
    savingRef.current = true; setSaving(true); setError(''); setNotice('');
    try {
      const result = await request<ProjectView>(`/api/projects/${base.project.id}/workspace`, {
        ...jsonBody({ expected_version: base.workspace.version, document: action === 'edit' ? next : undefined, action }), method: 'PATCH',
      });
      if (current.current === base.project.id) updateView(result);
      await list();
    } catch (e: any) { setError(e.message); }
    finally { savingRef.current = false; setSaving(false); await refresh(base.project.id).catch(() => {}); }
  };
  const upload = async (csv: File) => {
    if (!projectId) return;
    setSaving(true); setError('');
    const data = new FormData(); data.append('csv_file', csv); data.append('description', description);
    try { await request(`/api/projects/${projectId}/dataset`, { method: 'POST', body: data }); await refresh(projectId); await list(); setNotice('CSV saved. Describe the system in chat, then select Run.'); }
    catch (e: any) { setError(e.message); }
    finally { setSaving(false); if (file.current) file.current.value = ''; }
  };
  const send = async () => {
    if (!view || !query.trim()) return;
    const id = view.project.id, text = query.trim();
    setQuery(''); setChatBusy(true); setError(''); setNotice(''); setStatus('Reading your question');
    abort.current = new AbortController();
    updateView({ ...view, messages: [...view.messages, { role: 'user', content: text, created_at: new Date().toISOString(), metadata: { context } }] });
    try {
      await streamProject(`/api/projects/${id}/chat`, { query: text, stage_id: context.stage_id, expected_version: view.workspace.version }, event => {
        if (event.event === 'status') setStatus(event.message);
        if (event.event === 'error') setError(event.message);
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== 'AbortError') setError(e.message); }
    finally { abort.current = null; setChatBusy(false); setStatus(''); await refresh(id); await list(); }
  };
  const run = async () => {
    if (!view) return;
    setError(''); setNotice(''); setLogsOpen(true);
    try {
      const job = await request<Job>(`/api/projects/${view.project.id}/run`, jsonBody({ expected_version: view.workspace.version, parameters: {} }));
      setJobs(values => [job, ...values]);
    } catch (e: any) { setError(e.message); }
  };
  const cancel = async () => {
    if (abort.current) { abort.current.abort(); return; }
    if (activeJob && projectId) await request(`/api/projects/${projectId}/jobs/${activeJob.id}/cancel`, jsonBody({})).catch(e => setError(e.message));
  };
  const deleteStage = async (item: Stage) => {
    if (!view) return;
    try {
      const result = await request<{ affected: Stage[]; version: number }>(`/api/projects/${view.project.id}/stages/${encodeURIComponent(item.id)}/delete`, jsonBody({ expected_version: view.workspace.version }));
      setDeletion({ stage: item, ...result });
    } catch (e: any) { setError(e.message); }
  };
  const confirmDelete = async () => {
    if (!deletion || !view) return;
    setSaving(true); setError('');
    try {
      const result = await request<ProjectView>(`/api/projects/${view.project.id}/stages/${encodeURIComponent(deletion.stage.id)}/delete`, jsonBody({ expected_version: deletion.version, confirmed: true }));
      updateView(result); setSelected(null); setDeletion(null); setNotice('Stages removed. Use Undo to restore them.');
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };
  const accept = async () => {
    if (!view?.workspace.validated_run_id) return;
    setSaving(true); setError('');
    try {
      await request(`/api/projects/${view.project.id}/accept`, jsonBody({ run_id: view.workspace.validated_run_id, cleanup_confirmed: confirmed }));
      setAccepting(false); setConfirmed(false); setNotice('Revision accepted. Download this version from History.'); await refresh(view.project.id); await list();
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };
  const download = async (revision = view?.project.accepted_id) => {
    if (!view || !revision) return;
    setSaving(true); setError('');
    try {
      const response = await fetch(`/api/projects/${view.project.id}/export?include_data=${includeData}&revision_id=${revision}`);
      if (!response.ok) throw new Error((await response.json()).detail || 'Download failed');
      const url = URL.createObjectURL(await response.blob());
      const link = window.document.createElement('a'); link.href = url; link.download = `analysis-${revision.slice(0, 8)}-windows.zip`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: any) { setError(e.message); }
    finally { setSaving(false); }
  };
  const controlTarget = async (action: 'start' | 'stop' | 'restart') => {
    if (!projectId) return;
    setTargetBusy(true); setError('');
    try { setTarget(await request<Target>(`/api/projects/${projectId}/target/${action}`, jsonBody({}))); }
    catch (e: any) { setError(e.message); }
    finally { setTargetBusy(false); }
  };
  const selectStage = (id: string) => { setSelected(id); setDock('chat'); setDockOpen(true); };
  const chatAction = async (id: string, action: 'apply' | 'discard' | 'run') => {
    if (!projectId) return;
    const project = projectId;
    setSaving(true); setError('');
    try {
      const result = await request<any>(`/api/projects/${project}/chat/items/${id}/${action}`, jsonBody({}));
      if (current.current === project && action === 'run') { setJobs(values => [result, ...values.filter(value => value.id !== result.id)]); setLogsOpen(true); }
      await refresh(project); await list();
    } catch (e: any) { setError(e.message); await refresh(project).catch(() => {}); }
    finally { setSaving(false); }
  };
  const restore = async (id: string) => {
    if (!projectId) return;
    setSaving(true); setError('');
    try { await request(`/api/projects/${projectId}/revisions/${id}/rollback`, jsonBody({})); await refresh(projectId); setNotice('Revision restored to the workspace. Select Run if calculations are pending.'); }
    catch (e: any) { setError(e.message); } finally { setSaving(false); }
  };

  return <div className="platform studio-platform">
    <header className="studio-header"><a href="/" className="brand"><span className="brand-mark"><BarChart3 size={23} /></span><div><strong>WPS-AI <span>Studio</span></strong><small>Analysis application builder</small></div></a>
      <div className="project-title"><button className="project-name-button" aria-label="Project settings" disabled={!document || working} onClick={() => setProjectSettings(true)}><strong>{document?.title || 'Your analysis workspace'}</strong><Pencil size={12} /></button><span>{saving ? <><Loader2 className="spin" size={12} /> Saving…</> : <><Check size={12} />{workspace ? `Saved · v${workspace.version}` : 'Local workspace'}</>}</span></div>
      <div className="header-actions">{(activeJob || chatBusy) ? <button onClick={cancel}><Square size={14} /> Cancel</button> : <button className="primary" disabled={!view || working || !document?.input_enabled || !document?.input_contract || !view?.project.dataset_name} onClick={run}><Play size={15} fill="currentColor" /> Run</button>}
        <button disabled={working || !workspace?.validated_run_id || Boolean(activeJob)} aria-label="Accept revision" onClick={() => { setConfirmed(false); setAccepting(true); }}><CheckCircle2 size={16} /><span>Accept revision</span></button>
        <button disabled={working || !view?.project.accepted_id} aria-label="Download accepted application" onClick={() => download()}><ArrowDownToLine size={16} /><span>Download</span></button>
        <button className="icon-button" onClick={() => setDockOpen(!dockOpen)} aria-label={dockOpen ? 'Close side panel' : 'Open side panel'}>{dockOpen ? <PanelRightClose size={19} /> : <PanelRightOpen size={19} />}</button>
      </div>
    </header>
    <div className={`studio-shell ${dockOpen ? '' : 'dock-closed'}`}>
      <aside className="studio-navigation"><div className="project-switcher"><label htmlFor="project-select">Workspace</label><div className="project-select-row"><select id="project-select" value={projectId || ''} disabled={working} onChange={e => chooseProject(e.target.value)}><option value="" disabled>Select a project</option>{projects.map(p => <option value={p.id} key={p.id}>{p.title}</option>)}</select><button className="icon-button" disabled={working} onClick={() => create()} aria-label="New project"><Plus size={17} /></button></div></div>
        <nav aria-label="Development views">{navigation.map(({ id, title, icon: Icon }) => <button key={id} className={page === id ? 'active' : ''} onClick={() => navigate(id)} aria-current={page === id ? 'page' : undefined}><Icon size={17} />{title}{id === 'pipeline' && workspace && <span>{workspace.stages.length}</span>}</button>)}</nav>
        <div className="navigation-help"><span className="eyebrow">A reusable system</span><p>Describe it. Review the stages. Make it yours.</p><button disabled={working} onClick={() => create(true)}><Sparkles size={15} />Load energy example</button></div>
        <div className="target-card"><span className="eyebrow">Project dashboard</span><div className="target-card-status"><span className={`connection-dot ${target.status}`} /><strong>{targetBusy ? 'Starting…' : target.status === 'running' ? 'Running locally' : target.status === 'failed' ? 'Needs attention' : 'Stopped'}</strong></div>
          {target.url && <button className="target-address" title="Copy dashboard URL" onClick={() => navigator.clipboard.writeText(target.url!).then(() => setNotice('Dashboard URL copied.')).catch(() => setNotice(`Dashboard: ${target.url}`))}>{target.url.replace('http://', '')}<Copy size={12} /></button>}
          <div className="button-row">{target.url ? <a className="button primary" href={target.url} target="_blank" rel="noreferrer"><ExternalLink size={14} />Open dashboard</a> : <button disabled={!projectId || targetBusy} onClick={() => controlTarget('start')}><Play size={14} />Start target</button>}</div>
          <div className="target-service-actions"><button disabled={!projectId || targetBusy} onClick={() => controlTarget('restart')}><RotateCcw size={12} />Restart</button><button disabled={target.status !== 'running' || targetBusy} onClick={() => controlTarget('stop')}><Power size={12} />Stop</button></div>
          {target.last_error && <p className="target-error">{target.last_error}</p>}{target.error && <p className="target-error">{target.error}</p>}
        </div>
        <div className="navigation-footer"><span className={`connection-label ${connected ? '' : 'disconnected'}`}><span />{connected ? 'Local development' : 'Reconnecting…'}</span></div>
      </aside>
      <main className="studio-main">
        <div className="workspace-toolbar"><div className="breadcrumb">Workspace <ArrowRight size={12} /><strong>{navigation.find(p => p.id === page)?.title}</strong></div><div className="button-row">
          <button className="icon-button" disabled={working || !workspace?.can_undo} onClick={() => document && save(document, 'undo')} aria-label="Undo"><Undo2 size={17} /></button><button className="icon-button" disabled={working || !workspace?.can_redo} onClick={() => document && save(document, 'redo')} aria-label="Redo"><Redo2 size={17} /></button>
          {workspace && <span className={`state-badge ${workspace.calculation_pending ? 'state-pending' : 'state-succeeded'}`}><span />{workspace.calculation_pending ? 'Changes pending' : 'Calculations up to date'}</span>}</div></div>
        <div className="workspace-content">
          {error && <div className="error-banner" role="alert"><span>{error}</span><button className="icon-button" onClick={() => setError('')} aria-label="Dismiss error"><X size={15} /></button></div>}
          {notice && <div className="success-banner" role="status"><CheckCircle2 size={16} /><span>{notice}</span><button className="icon-button" onClick={() => setNotice('')} aria-label="Dismiss notification"><X size={15} /></button></div>}
          {!view || !document || !workspace ? <div className="studio-welcome"><span className="welcome-icon"><Rocket size={30} /></span><span className="eyebrow">From a question to an application</span><h1>Build your next<br />analysis workspace.</h1><p>Turn a CSV and your business knowledge into a reusable dashboard. Design with chat, review each stage, and run it locally.</p><div className="button-row"><button className="primary" disabled={working} onClick={() => create()}><Plus size={16} />Create a project</button><button disabled={working} onClick={() => create(true)}><Sparkles size={16} />Explore the energy example</button></div></div> : <>
            {page === 'data' && <>
              <div className="page-heading"><span className="eyebrow">01 / Data</span><h1>Start with the source.</h1><p>Give the system its data and the context to understand it.</p></div>
              <div className="data-upload-panel"><span className="data-file-icon"><Database size={27} /></span><div><h2>{view.project.dataset_name || 'Add your CSV file'}</h2><p>{view.project.profile ? `${view.project.profile.row_count.toLocaleString()} rows · ${view.project.profile.column_count} columns · Original data stays unchanged` : 'One CSV file, up to 100 MB. Data stays on this workstation.'}</p></div><button className="primary" disabled={working} onClick={() => file.current?.click()}><FileUp size={16} />{view.project.dataset_name ? 'Replace CSV' : 'Upload CSV'}</button></div>
              <section className="studio-section"><div className="section-title"><div><h2>Business context</h2><p>Explain the units, dates, and what the columns mean.</p></div></div><textarea className="business-context" value={description} disabled={working} placeholder="For example: each row is an hourly energy reading. kWh is consumption; zone identifies the building area."
                onChange={e => setDescription(e.target.value)} onBlur={() => { if (description !== view.project.description) request<ProjectView>(`/api/projects/${view.project.id}/context`, { ...jsonBody({ description }), method: 'PATCH' }).then(updateView).catch(e => setError(e.message)); }} /></section>
              {document.input_contract && <section className="studio-section"><div className="section-title"><div><h2>Input contract</h2><p>Column types used by the saved calculations.</p></div><span className="type-tag">{document.input_contract.encoding}</span></div><div className="input-contract-table"><table><thead><tr><th>Column</th><th>Type</th><th>Description</th></tr></thead><tbody>{document.input_contract.columns.map((column, index) => <tr key={column.name}><td><code>{column.name}</code></td><td><select aria-label={`Type for ${column.name}`} disabled={working} value={column.dtype} onChange={e => save({ ...document, input_contract: { ...document.input_contract!, columns: document.input_contract!.columns.map((c, i) => i === index ? { ...c, dtype: e.target.value } : c) } })}>{['string', 'number', 'integer', 'boolean', 'datetime'].map(type => <option key={type}>{type}</option>)}</select></td><td><input aria-label={`Description for ${column.name}`} key={column.description} defaultValue={column.description} disabled={working} onBlur={e => { if (e.target.value !== column.description) save({ ...document, input_contract: { ...document.input_contract!, columns: document.input_contract!.columns.map((c, i) => i === index ? { ...c, description: e.target.value } : c) } }); }} /></td></tr>)}</tbody></table></div></section>}
              {view.project.profile && <details className="studio-section profile-details"><summary>Explore the input profile<ChevronDown size={15} /></summary><DataProfileCard profile={view.project.profile} /></details>}
            </>}
            {page === 'pipeline' && <>
              <div className="page-heading heading-with-action"><div><span className="eyebrow">02 / Pipeline</span><h1>A clear path from data to insight.</h1><p>Chat creates the stages. Select a stage to review it or change its properties.</p></div><button onClick={() => { setDock('chat'); setDockOpen(true); }}><MessageSquare size={16} />Design with chat</button></div>
              <StageCanvas workspace={workspace} selected={selected} onSelect={selectStage} onDelete={deleteStage} run={view.partial_run?.workspace_version === workspace.version ? view.partial_run : view.display_run} job={latestJob} pending={workspace.calculation_pending} />
              {workspace.issues.length > 0 && <div className="workspace-issues"><CircleHelp size={18} /><div><h3>Before accepting a complete dashboard</h3><p>Run can execute the available stages now.</p><ul>{workspace.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></div></div>}
              <div className="pipeline-note"><Sparkles size={16} /><p>Need another calculation or chart? Describe it in chat. The agent updates the connected stages for you.</p></div>
            </>}
            {page === 'dashboard' && <>
              <div className="page-heading"><span className="eyebrow">03 / Dashboard</span><h1>Make the results easy to read.</h1><p>Drag a handle to move a widget. Select one to edit its properties.</p></div>
              <details className="studio-section dashboard-settings"><summary><Settings2 size={16} />Dashboard settings<ChevronDown size={15} /></summary><fieldset className="settings-fields" disabled={working}>
                <div className="settings-grid"><SettingsField label="Dashboard title" value={document.dashboard.title} onCommit={title => save({ ...document, dashboard: { ...document.dashboard, title } })} />
                  <SettingsField label="Subtitle" value={document.dashboard.subtitle} onCommit={subtitle => save({ ...document, dashboard: { ...document.dashboard, subtitle } })} /></div>
              </fieldset></details>
              {document.parameters.length > 0 && <details className="studio-section dashboard-settings"><summary><Settings2 size={16} />Filters and scenario defaults<span className="type-tag">{document.parameters.length}</span><ChevronDown size={15} /></summary>
                <p className="muted settings-help">Choose the labels, starting values, and ranges for dashboard controls. Select Run after changing calculation defaults.</p><fieldset className="settings-fields" disabled={working}><ControlSettings document={document} onChange={save} run={view.display_run} /></fieldset>
              </details>}
              <div className="designer-ruler"><span>Desktop · 12 columns</span><span>Live design · saved to target</span></div>
              <div className="designer-scroll"><div className="designer-frame"><Dashboard revision={{ ...document, revision_id: view.draft?.revision_id || 'workspace' }} run={view.display_run} appliedRevision={view.display_revision}
                parameters={{}} onChange={() => {}} onApply={() => {}} busy={working} editing selected={selected?.replace('widget:', '')} onSelect={id => selectStage(`widget:${id}`)} showControls={false}
                onLayoutChange={widgets => save({ ...document, dashboard: { ...document.dashboard, widgets } })} tableUrl={output => `/api/projects/${projectId}/runs/${view.display_run?.run_id}/tables/${output}`} /></div></div>
            </>}
            {page === 'history' && <>
              <div className="page-heading"><span className="eyebrow">04 / History</span><h1>Build with a way back.</h1><p>Accepted revisions remain available while you continue to refine the workspace.</p></div>
              <section className="release-panel"><span className="release-icon"><CheckCircle2 size={23} /></span><div><h2>{view.project.accepted_id ? 'Accepted application' : 'Your first release starts here'}</h2><p>{view.project.accepted_id ? `Revision ${view.project.accepted_id.slice(0, 8)}${view.project.accepted_id !== view.draft?.revision_id || (view.project.accepted_run_id && view.project.accepted_run_id !== workspace.validated_run_id) ? ' · Newer workspace or data changes are not in this download.' : ' · Matches the current validated revision.'}` : 'Run the workspace, review cleanup, and accept the revision to download a Windows application.'}</p><label className="checkbox-label"><input type="checkbox" checked={includeData} onChange={e => setIncludeData(e.target.checked)} />Include the accepted CSV in downloads</label></div><button className="primary" disabled={working || !view.project.accepted_id} onClick={() => download()}><ArrowDownToLine size={16} />Download Windows app</button></section>
              <div className="revision-list">{view.revisions.map(revision => <article className="revision-row" key={revision.id}><span className={`revision-dot ${revision.accepted ? 'accepted' : ''}`} /><div><div className="revision-row-title"><code>{revision.id.slice(0, 8)}</code><span className={`state-badge ${revision.accepted ? 'state-succeeded' : 'state-ready'}`}>{revision.accepted ? 'Accepted' : 'Draft'}</span>{view.draft?.revision_id === revision.id && <span className="muted">Current</span>}</div><p>{revision.summary || 'Saved analysis revision'}</p>{revision.created_at && <small>{new Date(revision.created_at).toLocaleString()}</small>}</div>{Boolean(revision.accepted) && <div className="button-row"><button disabled={working || Boolean(activeJob)} onClick={() => restore(revision.id)}><RotateCcw size={14} />Restore</button><button className="icon-button" disabled={working} onClick={() => download(revision.id)} aria-label={`Download revision ${revision.id.slice(0, 8)}`}><ArrowDownToLine size={16} /></button></div>}</article>)}</div>
              {!view.revisions.length && <div className="stage-empty">Saved revisions will appear after the agent creates your pipeline.</div>}
            </>}
          </>}
        </div>
        <section className={`run-drawer ${logsOpen ? 'expanded' : ''}`}><button className="run-drawer-toggle" onClick={() => setLogsOpen(!logsOpen)} aria-expanded={logsOpen}><span className="button-row">{activeJob || chatBusy ? <Loader2 size={15} className="spin" /> : <Activity size={15} />}<strong>{progress || 'Run output'}</strong>{latestJob && !activeJob && <span className={`state-badge state-${latestJob.status}`}>{latestJob.status}</span>}</span>{logsOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</button>
          {logsOpen && <div className="run-drawer-content" aria-live="polite">{view?.partial_run?.result && <details><summary>Partial results · Run {view.partial_run.run_id.slice(0, 8)} · Workspace v{view.partial_run.workspace_version}</summary>{Object.entries(view.partial_run.result.outputs).map(([name, output]) => <div key={name}><strong>{name}</strong>{output.kind === 'table' && <a href={`/api/projects/${view.project.id}/runs/${view.partial_run!.run_id}/tables/${name}`}>Download complete CSV ({output.total_rows} rows)</a>}<pre>{JSON.stringify(output.kind === 'table' ? output.rows : output.value, null, 2)}</pre></div>)}</details>}{latestJob?.partial && <p>Partial run: results stay in the builder. Blocked stages did not run.</p>}{view && <button disabled={Boolean(activeJob) || working} onClick={async () => { try { updateView(await request<ProjectView>(`/api/projects/${view.project.id}/temporary-results`, { method: 'DELETE' })); setNotice('Temporary results cleared. Saved dashboard results and history remain available.'); } catch (e) { setError((e as Error).message); } }}>Clear partial results</button>}{latestJob?.error && <div className="error-banner">{latestJob.error}</div>}{latestJob?.events.filter(event => event.event === 'step' || event.event === 'status').map((event, index) => <div className="log-row" key={index}><span>{String(index + 1).padStart(2, '0')}</span><strong>{event.title || event.message}</strong><span>{event.cached ? 'Reused' : event.status}{event.status === 'blocked' && event.message ? ` · ${event.message}` : ''}</span></div>)}
            {!latestJob && <p className="muted">Select Run to validate the saved workspace and update the target dashboard.</p>}
            {(view?.partial_run?.workspace_version === workspace?.version ? view?.partial_run : view?.display_run)?.result?.cleanup_impacts.map(impact => <div className="cleanup-summary" key={impact.step_id}><strong>{impact.title}</strong><p>{impact.before_rows.toLocaleString()} → {impact.after_rows.toLocaleString()} rows · {impact.before_missing_cells} → {impact.after_missing_cells} missing cells</p><p>{impact.rationale}</p></div>)}
          </div>}
        </section>
      </main>
      {dockOpen && <aside className="studio-dock"><div className="dock-tabs"><button className={dock === 'chat' ? 'active' : ''} onClick={() => setDock('chat')}><MessageSquare size={15} />Chat</button><button className={dock === 'properties' ? 'active' : ''} onClick={() => setDock('properties')}><Settings2 size={15} />Properties</button>{developer && <button className={dock === 'inspect' ? 'active' : ''} onClick={() => setDock('inspect')}>Inspect</button>}</div>
        {dock === 'chat' ? <><div className="chat-intro"><span className="assistant-mark"><Sparkles size={17} /></span><div><strong>Your development partner</strong><p>Ask questions or propose changes. Edits need your approval.</p></div></div><div className="studio-messages" aria-live="polite">{!view?.messages.length && <div className="chat-empty"><h3>Start with the question.</h3><p>Tell the agent what to calculate, which filters to offer, and how to present the results.</p><button disabled={!view?.project.dataset_name || working} onClick={() => setQuery('Create an overview with key metrics, a comparison chart, a trend chart where the data supports it, and a detailed table. Explain the cleaning steps and add useful filters.')}>Create an overview dashboard<ArrowRight size={14} /></button><button disabled={!view?.project.dataset_name || working} onClick={() => setQuery('Review the input columns and propose data cleaning, analysis, and visualization stages for this dataset.')}>Help me choose the stages<ArrowRight size={14} /></button></div>}
          {view?.messages.map((message, index) => {
            const item = view.chat_items?.find(value => value.id === message.metadata?.item_id);
            return <article className={`studio-message ${message.role}`} key={`${message.created_at}-${index}`}>
              <span>{message.role === 'user' ? 'You' : 'WPS-AI'} · {message.metadata?.context?.label || 'Project'}</span>
              <p>{message.content}</p>
              {message.metadata?.run_id && <small className="message-provenance">Run {message.metadata.run_id.slice(0, 8)} · Revision {message.metadata.revision_id?.slice(0, 8)} · Input {message.metadata.input_hash?.slice(0, 8)}</small>}
              {item && ['proposal', 'needs_run'].includes(message.metadata?.kind || '') && <ChatReview item={item} projectId={view.project.id} developer={developer} disabled={working || Boolean(activeJob)} issues={workspace?.issues || []}
                onAction={chatAction} onUndo={() => document && save(document, 'undo')} />}
            </article>;
          })}{chatBusy && <div className="chat-thinking"><Loader2 size={14} className="spin" />{status}</div>}<div ref={chatEnd} /></div>
          <form className="chat-composer" onSubmit={event => { event.preventDefault(); send(); }}>
            <div className="chat-context" aria-label="Chat context"><span>{context.label}</span>{selected && <button type="button" onClick={() => setSelected(null)} aria-label="Clear chat context"><X size={13} />Clear</button>}</div>
            <div className="chat-shortcuts">{[
              ['Explain', 'Explain this stage: its purpose, inputs, outputs, and assumptions. Do not change anything.'],
              ['Inputs / outputs', 'Explain how the inputs and outputs connect in this context. Do not change anything.'],
              ['Fix latest error', 'Review the latest relevant failed run and propose the smallest repair for this context. Explain any linked changes.'],
              ['Next steps', 'Suggest useful next steps for this context. Explain them without changing the pipeline.'],
            ].map(([label, text]) => <button type="button" disabled={working || !view} key={label} onClick={() => setQuery(text)}>{label}</button>)}</div>
            <textarea aria-label="Ask about the selected context or request changes" placeholder={categoryLabel ? `Describe the ${categoryLabel.toLowerCase()} stages to create…` : stage ? `Ask about ${stage.title} or request a change…` : 'Ask a question or describe a pipeline change…'} value={query} disabled={working || !view} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } }} />
            <div><span>Answers do not edit. Review and Apply changes.</span><button className="primary icon-button" disabled={working || !query.trim() || !view} aria-label="Send chat message"><Send size={16} /></button></div>
          </form>
        </> : dock === 'inspect' && developer && view ? <StageInspector projectId={view.project.id} stageId={stage?.id || null} version={view.workspace.version} runKey={`${view.display_run?.run_id || ""}:${latestJob?.id || ""}:${latestJob?.status || ""}`} onSelect={id => setSelected(id)} />
          : document ? <PropertiesPanel document={document} stage={stage} run={(view?.partial_run?.workspace_version === workspace?.version ? view?.partial_run : view?.display_run) || null} onChange={save} onDelete={deleteStage} onOpenData={() => navigate('data')} disabled={working} /> : <p className="dock-description">Create a project to edit properties.</p>}
      </aside>}
    </div>
    <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={event => { if (event.target.files?.[0]) upload(event.target.files[0]); }} />
    {projectSettings && document && <Modal title="Project settings" onClose={() => setProjectSettings(false)}><div className="dialog-body">{error && <div className="error-banner" role="alert">{error}</div>}<p className="muted">Changes save when you leave a field.</p><fieldset className="settings-fields" disabled={working}><SettingsField label="Project name" value={document.title} onCommit={title => save({ ...document, title })} /></fieldset><p className="muted settings-help">Manage the CSV and business context in Data. Manage titles and control defaults in Dashboard.</p></div><footer><button className="primary" disabled={working} onClick={() => setProjectSettings(false)}>Done</button></footer></Modal>}
    {deletion && <Modal title="Delete this stage?" onClose={() => setDeletion(null)}><div className="dialog-body">{error && <div className="error-banner" role="alert">{error}</div>}<p>Remove <strong>{deletion.stage.title}</strong> and its dependent stages from this workspace.</p><ul className="deletion-list">{deletion.affected.map(item => <li key={item.id}><Trash2 size={14} />{item.title}</li>)}</ul><p className="muted">Earlier revisions and source files stay in history. Undo restores this change.</p></div><footer><button onClick={() => setDeletion(null)}>Keep stages</button><button className="danger" disabled={working} onClick={confirmDelete}>Delete {deletion.affected.length} {deletion.affected.length === 1 ? 'stage' : 'stages'}</button></footer></Modal>}
    {accepting && <Modal title="Accept this revision" onClose={() => setAccepting(false)}><div className="dialog-body">{error && <div className="error-banner" role="alert">{error}</div>}<p>Approve the current validated calculations and dashboard design for download.</p>{(view?.partial_run?.workspace_version === workspace?.version ? view?.partial_run : view?.display_run)?.result?.cleanup_impacts.map(impact => <div className="cleanup-summary" key={impact.step_id}><strong>{impact.title}</strong><p>{impact.before_rows} → {impact.after_rows} rows · {impact.before_missing_cells} → {impact.after_missing_cells} missing cells</p><p>{impact.rationale}</p></div>)}{needsConfirmation && <label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I reviewed and approve the cleanup rules and their impact.</label>}</div><footer><button onClick={() => setAccepting(false)}>Back to workspace</button><button className="primary" disabled={working || (needsConfirmation && !confirmed)} onClick={accept}>Accept revision</button></footer></Modal>}
  </div>;
}
