import { useLayoutEffect, useRef, useState, useId } from 'react';
import { ArrowRight, BarChart3, Database, ExternalLink, Sigma, Sparkles, Trash2 } from 'lucide-react';
import type { Job, Run, Stage, Workspace } from '../lib/projects';

const columns = [
  { type: 'input', page: 'data', title: 'Data input', icon: Database, description: 'Source and business context' },
  { type: 'cleaning', page: 'cleaning', title: 'Data cleaning', icon: Sparkles, description: 'Prepare and review the data' },
  { type: 'analysis', page: 'analysis', title: 'Analysis', icon: Sigma, description: 'Calculate, compare, and forecast' },
  { type: 'visualization', page: 'dashboard', title: 'Visualization', icon: BarChart3, description: 'Present the results' },
] as const;

export function StageCanvas({ workspace, selected, onSelect, onDelete, onNavigatePage, run, job, pending }: {
  workspace: Workspace; selected: string | null; onSelect: (id: string) => void; onDelete: (stage: Stage) => void;
  onNavigatePage?: (page: 'data' | 'cleaning' | 'analysis' | 'dashboard') => void;
  run: Run | null; job?: Job; pending: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const nodes = useRef(new Map<string, HTMLDivElement>());
  const marker = useId().replace(/:/g, '');
  const [paths, setPaths] = useState<string[]>([]);
  const active = workspace.stages.find(stage => stage.id === selected);
  const related = new Set([...(active?.dependencies || []), ...workspace.stages.filter(s => s.dependencies.includes(selected || '')).map(s => s.id)]);
  useLayoutEffect(() => {
    const measure = () => {
      if (!root.current) return;
      const bounds = root.current.getBoundingClientRect();
      const lines: string[] = [];
      for (const stage of workspace.stages) for (const dependency of stage.dependencies) {
        if (stage.id !== selected && dependency !== selected) continue;
        const from = nodes.current.get(dependency)?.getBoundingClientRect();
        const to = nodes.current.get(stage.id)?.getBoundingClientRect();
        if (!from || !to) continue;
        const x1 = from.right - bounds.left, y1 = from.top + from.height / 2 - bounds.top;
        const x2 = to.left - bounds.left, y2 = to.top + to.height / 2 - bounds.top;
        lines.push(`M ${x1} ${y1} C ${x1 + 25} ${y1}, ${x2 - 25} ${y2}, ${x2} ${y2}`);
      }
      setPaths(lines);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (root.current) observer.observe(root.current);
    return () => observer.disconnect();
  }, [workspace.stages, selected]);
  const status = (stage: Stage) => {
    if (stage.type === 'input') return 'Ready';
    const stepId = stage.id.replace('step:', '');
    const event = [...(job?.events || [])].reverse().find(e => e.step_id === stepId);
    if (job?.status === 'failed' && job.workspace_version === workspace.version && event?.status === 'running') return 'Failed';
    if (job && ['queued', 'running'].includes(job.status) && event) return event.status === 'running' ? 'Running' : event.cached ? 'Reused' : 'Succeeded';
    if (job?.workspace_version === workspace.version && event?.status === 'blocked') return 'Blocked';
    const saved = [...(run?.result?.steps || [])].reverse().find(e => e.step_id === stepId);
    if (pending && (run?.workspace_version !== workspace.version || !saved && stage.type !== 'visualization')) return 'Pending';
    return saved?.cached ? 'Reused' : saved || (stage.type === 'visualization' && stage.inputs.some(name => run?.result?.outputs[name])) ? 'Succeeded' : pending ? 'Pending' : 'Ready';
  };
  return <div className="pipeline-scroll"><div className="pipeline-canvas" ref={root}>
    <svg className="stage-connections" aria-hidden="true"><defs><marker id={marker} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="#4079df" /></marker></defs>
      {paths.map((path, i) => <path key={i} d={path} fill="none" stroke="#4079df" strokeWidth="1.7" markerEnd={`url(#${marker})`} />)}</svg>
    {columns.map(({ type, page, title, icon: Icon, description }, index) => <section className={`stage-column stage-${type}`} key={type} aria-label={title}>
      <div className="stage-column-top">
        <button type="button" className="stage-column-heading" onClick={() => onSelect(`category:${type}`)} aria-pressed={selected === `category:${type}`} title={`Select ${title} chat context`}>
          <span className="stage-type-icon"><Icon size={18} /></span>
          <div><span className="eyebrow">Stage {index + 1}</span><h3>{title}</h3></div>
          <span className="stage-count">{workspace.stages.filter(s => s.type === type).length}</span>
        </button>
        {onNavigatePage && (
          <button
            type="button"
            className="column-page-jump-btn"
            onClick={(e) => { e.stopPropagation(); onNavigatePage(page); }}
            title={`Open dedicated ${title} page`}
          >
            <span>Open page</span>
            <ArrowRight size={11} />
          </button>
        )}
      </div>
      <p className="stage-column-description">{description}</p>
      <div className="stage-stack">{workspace.stages.filter(stage => stage.type === type).map(stage => <div key={stage.id} ref={node => { if (node) nodes.current.set(stage.id, node); else nodes.current.delete(stage.id); }}
        className={`stage-node ${selected === stage.id ? 'selected' : ''} ${related.has(stage.id) ? 'related' : ''}`}>
        <button className="stage-node-main" onClick={() => onSelect(stage.id)} aria-pressed={selected === stage.id}>
          <span className={`state-badge state-${status(stage).toLowerCase()}`}><span />{status(stage)}</span>
          <strong>{stage.title}</strong>
          {stage.rationale && <p>{stage.rationale}</p>}
          {!!stage.inputs.length && <span className="stage-ports"><ArrowRight size={12} /> {stage.inputs.join(', ')}</span>}
          {!!stage.outputs.length && <span className="output-chips">{stage.outputs.map(output => <code key={output}>{output}</code>)}</span>}
        </button>
        <button className="icon-button stage-delete" onClick={() => onDelete(stage)} aria-label={`Delete ${stage.title}`}><Trash2 size={14} /></button>
      </div>)}
      {!workspace.stages.some(stage => stage.type === type) && <button type="button" className="stage-empty" onClick={() => { onSelect(`category:${type}`); if (type !== 'input' && onNavigatePage) onNavigatePage(page); }}>{type === 'input' ? 'Upload a CSV in Data to begin.' : 'Select this stage and describe it in chat.'}</button>}</div>
    </section>)}
  </div></div>;
}
