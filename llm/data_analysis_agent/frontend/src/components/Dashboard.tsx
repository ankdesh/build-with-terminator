import { ChartViewer } from './ChartViewer';
import { DataTableViewer } from './DataTableViewer';
import type { ChartSpec } from '../lib/types';
import type { Revision, Run, Scalar } from '../lib/projects';

interface Props {
  revision: Revision | null; run: Run | null; parameters: Record<string, Scalar>;
  onChange: (parameters: Record<string, Scalar>) => void; onApply: () => void;
  tableUrl: (output: string) => string; busy: boolean;
  emptyMessage?: string;
}

function metric(value: unknown, format?: string | null): string {
  if (value == null) return 'No value';
  if (typeof value !== 'number') return String(value);
  const digits = format?.match(/\.(\d)f/);
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: digits ? Number(digits[1]) : 3,
    minimumFractionDigits: digits ? Number(digits[1]) : 0,
    ...(format === 'percent' ? { style: 'percent' as const } : {}),
  }).format(value);
}

export function Dashboard({ revision, run, parameters, onChange, onApply, tableUrl, busy, emptyMessage }: Props) {
  if (!revision || !run?.result) return <div className="dashboard-empty">
    <div className="empty-mark">▥</div><h2>Your saved analysis system</h2>
    <p>{emptyMessage || 'Upload a CSV and describe the dashboard you need. Its preview will appear here after validation.'}</p>
  </div>;
  const setValue = (id: string, value: Scalar) => onChange({ ...parameters, [id]: value });
  return <section className="dashboard" aria-label="Data analysis dashboard">
    <div className="dashboard-heading"><h1>{revision.dashboard.title}</h1><p>{revision.dashboard.subtitle}</p>
      <small>Showing {run.dataset_name} · revision {run.revision_id.slice(0, 8)} · input {run.input_hash.slice(0, 8)}</small>
    </div>
    {revision.parameters.length > 0 && <form className="dashboard-controls" onSubmit={e => { e.preventDefault(); onApply(); }}>
      {revision.parameters.map(spec => <label key={spec.id}>{spec.label}
        {spec.kind === 'select' ? <select disabled={busy} value={JSON.stringify(parameters[spec.id] ?? null)}
          onChange={e => setValue(spec.id, JSON.parse(e.target.value))}>
          <option value="null">{spec.filter_column ? 'All' : 'No selection'}</option>
          {(run.result?.parameter_options[spec.id] || spec.choices).map((value, index) =>
            <option key={index} value={JSON.stringify(value)}>{String(value)}</option>)}
        </select> : spec.kind === 'boolean' ? <input type="checkbox" disabled={busy} checked={parameters[spec.id] === true}
          onChange={e => setValue(spec.id, e.target.checked)} /> : <input disabled={busy}
          type={['number', 'integer'].includes(spec.kind) ? 'number' : 'text'}
          min={spec.minimum ?? undefined} max={spec.maximum ?? undefined} step={spec.kind === 'integer' ? 1 : 'any'}
          value={parameters[spec.id] == null ? '' : String(parameters[spec.id])}
          onChange={e => setValue(spec.id, e.target.value === '' ? null : ['number', 'integer'].includes(spec.kind) ? Number(e.target.value) : e.target.value)} />}
      </label>)}
      <button disabled={busy} className="primary" type="submit">Apply controls</button>
      <button disabled={busy} type="button" onClick={() => onChange(Object.fromEntries(revision.parameters.map(p => [p.id, p.default])))}>Reset controls</button>
    </form>}
    <div className="dashboard-grid">
      {revision.dashboard.widgets.map(widget => {
        const output = run.result?.widgets?.[widget.id] || run.result?.outputs[widget.output];
        return <article key={widget.id} className={`dashboard-widget ${widget.width === 2 ? 'wide' : ''}`}>
          {widget.kind !== 'chart' && <h2>{widget.title}</h2>}
          {!output ? <p>Output unavailable</p> : widget.kind === 'metric' ? <div className="metric-value">{metric(output.value, widget.format)}</div>
            : widget.kind === 'chart' ? <ChartViewer spec={{ ...(output.value as ChartSpec), title: widget.title }} />
            : widget.kind === 'table' ? <><DataTableViewer key={`${run.run_id}-${widget.id}`} table={{ columns: output.columns || [], rows: output.rows || [], total_rows: output.total_rows || 0 }}
              onExportCsv={() => { window.location.href = tableUrl(widget.output); }} />
              {(output.total_rows || 0) > (output.rows?.length || 0) && <small>Preview limited to {output.rows?.length} rows. CSV export includes every row.</small>}</>
            : <p className="computed-text">{String(output.value ?? '')}</p>}
        </article>;
      })}
    </div>
  </section>;
}
