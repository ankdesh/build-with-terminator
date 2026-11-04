import { useMemo } from 'react';
import GridLayout, { useContainerWidth, verticalCompactor } from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import { GripVertical, SlidersHorizontal } from 'lucide-react';
import { ChartViewer } from './ChartViewer';
import { DataTableViewer } from './DataTableViewer';
import type { ChartSpec } from '../lib/types';
import type { Revision, Run, Scalar, Widget } from '../lib/projects';
import 'react-grid-layout/css/styles.css';

interface Props {
  revision: Revision | null; run: Run | null; parameters: Record<string, Scalar>;
  onChange: (parameters: Record<string, Scalar>) => void; onApply: () => void;
  tableUrl: (output: string) => string; busy: boolean; emptyMessage?: string;
  editing?: boolean; selected?: string | null; onSelect?: (id: string) => void;
  onLayoutChange?: (widgets: Widget[]) => void; appliedRevision?: Revision | null; showControls?: boolean;
}

export function metric(value: unknown, format?: string | null): string {
  if (value == null) return '—';
  if (typeof value !== 'number') return String(value);
  const fixed = format?.match(/\.(\d{1,2})f/);
  const decimalMask = format?.match(/^0\.(0{1,20})$/);
  const digits = fixed || (decimalMask ? [decimalMask[0], String(decimalMask[1].length)] : null);
  const precision = digits ? Math.min(20, Number(digits[1])) : format === 'integer' || format === '0' ? 0 : 3;
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: precision, minimumFractionDigits: digits ? precision : 0,
    ...(format === 'percent' ? { style: 'percent' as const } : {}),
  }).format(value);
}

export function widgetLayout(widgets: Widget[]): Layout {
  let x = 0, y = 0, rowHeight = 0;
  return widgets.map(widget => {
    if (widget.layout) return { i: widget.id, ...widget.layout, minW: 1, minH: widget.kind === 'chart' ? 9 : 3 };
    const w = widget.width === 2 ? 12 : 6;
    const h = widget.kind === 'metric' ? 5 : widget.kind === 'text' ? 6 : 13;
    if (x + w > 12) { y += rowHeight; x = 0; rowHeight = 0; }
    const result = { i: widget.id, x, y, w, h, minW: 1, minH: widget.kind === 'chart' ? 9 : 3 };
    x += w; rowHeight = Math.max(rowHeight, h);
    return result;
  });
}

export function DashboardControls({ revision, run, parameters, onChange, onApply, busy }: Pick<Props, 'revision' | 'run' | 'parameters' | 'onChange' | 'onApply' | 'busy'>) {
  if (!revision?.parameters.length) return null;
  const setValue = (id: string, value: Scalar) => onChange({ ...parameters, [id]: value });
  return <form className="dashboard-controls" onSubmit={e => { e.preventDefault(); onApply(); }}>
    <div className="section-caption"><SlidersHorizontal size={15} /> Filters and scenarios</div>
    <div className="control-fields">{revision.parameters.map(spec => <label key={spec.id}>{spec.label}
      {spec.kind === 'select' ? <select disabled={busy} value={JSON.stringify(parameters[spec.id] ?? null)} onChange={e => setValue(spec.id, JSON.parse(e.target.value))}>
        <option value="null">{spec.filter_column ? 'All' : 'No selection'}</option>
        {(run?.result?.parameter_options[spec.id] || spec.choices).filter(v => v !== null).map((value, index) => <option key={index} value={JSON.stringify(value)}>{String(value)}</option>)}
      </select> : spec.kind === 'boolean' ? <input type="checkbox" disabled={busy} checked={parameters[spec.id] === true} onChange={e => setValue(spec.id, e.target.checked)} /> :
        <input disabled={busy} type={['number', 'integer'].includes(spec.kind) ? 'number' : 'text'} min={spec.minimum ?? undefined} max={spec.maximum ?? undefined}
          step={spec.kind === 'integer' ? 1 : 'any'} value={parameters[spec.id] == null ? '' : String(parameters[spec.id])}
          onChange={e => setValue(spec.id, e.target.value === '' ? null : ['number', 'integer'].includes(spec.kind) ? Number(e.target.value) : e.target.value)} />}
    </label>)}</div>
    <div className="button-row"><button disabled={busy} className="primary" type="submit">Apply controls</button>
      <button disabled={busy} type="button" onClick={() => onChange(Object.fromEntries(revision.parameters.map(p => [p.id, p.default])))}>Reset</button></div>
  </form>;
}

export function Dashboard({ revision, run, parameters, onChange, onApply, tableUrl, busy, emptyMessage,
  editing = false, selected, onSelect, onLayoutChange, appliedRevision, showControls = true }: Props) {
  const { width, containerRef, mounted } = useContainerWidth();
  const widgets = revision?.dashboard.widgets || [];
  const layout = useMemo(() => widgetLayout(widgets), [widgets]);
  const saveLayout = (next: Layout) => {
    onLayoutChange?.(widgets.map(widget => {
      const item = next.find(i => i.i === widget.id);
      const original = layout.find(i => i.i === widget.id);
      if (!item || !original || ['x', 'y', 'w', 'h'].every(key => item[key as keyof typeof item] === original[key as keyof typeof original])) return widget;
      return { ...widget, layout: { x: item.x, y: item.y, w: item.w, h: item.h } };
    }));
  };
  const moveByKey = (widget: Widget, event: React.KeyboardEvent) => {
    if (!editing || !event.altKey || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const position = layout.find(item => item.i === widget.id)!;
    const x = Math.max(0, Math.min(12 - position.w, position.x + (event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0)));
    const y = Math.max(0, position.y + (event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0));
    onLayoutChange?.(widgets.map(w => w.id === widget.id ? { ...w, layout: { x, y, w: position.w, h: position.h } } : w));
  };
  return <section className={`dashboard ${editing ? 'is-designer' : ''}`} aria-label={editing ? 'Dashboard designer' : 'Data analysis dashboard'}>
    {revision && <div className="dashboard-heading"><h1>{revision.dashboard.title}</h1><p>{revision.dashboard.subtitle}</p></div>}
    {showControls && <DashboardControls revision={revision} run={run} parameters={parameters} onChange={onChange} onApply={onApply} busy={busy} />}
    {!widgets.length && <div className="dashboard-empty"><div className="empty-mark">▥</div><h2>Your analysis, ready to take shape</h2><p>{emptyMessage || 'Describe your dashboard in chat. The agent will create its stages and visualizations.'}</p></div>}
    <div ref={containerRef} className="dashboard-grid-shell">
      {mounted && widgets.length > 0 && <GridLayout width={width} layout={layout} gridConfig={{ cols: 12, rowHeight: 20, margin: [16, 16], containerPadding: [0, 0] }}
        dragConfig={{ enabled: editing && !busy, handle: '.widget-drag-handle' }} resizeConfig={{ enabled: editing && !busy, handles: ['se'] }}
        onDragStop={saveLayout} onResizeStop={saveLayout} compactor={verticalCompactor}>
        {widgets.map(widget => {
          const applied = appliedRevision?.dashboard.widgets.find(w => w.id === widget.id);
          const compatible = !appliedRevision || Boolean(applied && applied.output === widget.output && applied.kind === widget.kind && JSON.stringify(applied.chart_binding) === JSON.stringify(widget.chart_binding));
          const output = compatible ? (run?.result?.widgets?.[widget.id] || run?.result?.outputs[widget.output]) : undefined;
          return <article key={widget.id} data-widget-id={widget.id} className={`dashboard-widget widget-${widget.kind} ${selected === widget.id ? 'widget-selected' : ''}`}
            tabIndex={editing ? 0 : undefined} onClick={() => editing && onSelect?.(widget.id)} onFocus={() => editing && onSelect?.(widget.id)} onKeyDown={event => moveByKey(widget, event)}
            aria-label={editing ? `${widget.title}. Alt and arrow keys move this widget. Use Properties to resize.` : undefined}>
            {editing && <button className="widget-drag-handle" aria-label={`Move ${widget.title}`} title="Drag to move"><GripVertical size={16} /></button>}
            {widget.kind !== 'chart' && <div className="widget-heading"><h2>{widget.title}</h2>{widget.description && <p>{widget.description}</p>}</div>}
            {!output ? <div className="widget-pending"><span className="pending-dot" /><strong>Ready for a run</strong><p>This visualization will show data after its calculation succeeds.</p></div> : widget.kind === 'metric' ?
              <div className="metric-reading"><span className="metric-value">{metric(output.value, widget.format)}</span>{widget.unit && <span className="metric-unit">{widget.unit}</span>}</div> : widget.kind === 'chart' ?
                <ChartViewer embedded spec={{ ...(output.value as ChartSpec), title: widget.title, description: widget.description || undefined }} /> : widget.kind === 'table' ?
                  <><DataTableViewer embedded key={`${run?.run_id}-${widget.id}`} table={{ columns: output.columns || [], rows: output.rows || [], total_rows: output.total_rows || 0 }} onExportCsv={() => { window.location.href = tableUrl(widget.output); }} />
                    {(output.total_rows || 0) > (output.rows?.length || 0) && <small className="table-limit">Preview: {output.rows?.length} rows. CSV includes all {output.total_rows?.toLocaleString()} rows.</small>}</> :
                  <p className="computed-text">{String(output.value ?? '')}</p>}
          </article>;
        })}
      </GridLayout>}
    </div>
  </section>;
}
