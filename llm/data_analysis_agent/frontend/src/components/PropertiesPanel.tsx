import type { ReactNode } from 'react';
import { Settings2, Trash2 } from 'lucide-react';
import type { Run, Stage, Widget, WorkspaceDocument } from '../lib/projects';
import { widgetLayout } from './Dashboard';
import { SettingsField as Field, ControlSettings } from './SettingsFields';

function Group({ title, children }: { title: string; children: ReactNode }) { return <section className="property-group"><h3>{title}</h3>{children}</section>; }

export function PropertiesPanel({ document, stage, run, onChange, onDelete, onOpenData, disabled }: {
  document: WorkspaceDocument; stage?: Stage; run: Run | null; onChange: (document: WorkspaceDocument) => void;
  onDelete: (stage: Stage) => void; onOpenData: () => void; disabled: boolean;
}) {
  const widget = stage?.id.startsWith('widget:') ? document.dashboard.widgets.find(w => `widget:${w.id}` === stage.id) : undefined;
  const step = stage?.id.startsWith('step:') ? document.steps.find(s => `step:${s.id}` === stage.id) : undefined;
  // Older stages may not declare control dependencies. Keep global controls in Dashboard.
  const stageParameters = step?.parameters_used || [];
  const updateWidget = (change: Partial<Widget>) => widget && onChange({ ...document, dashboard: { ...document.dashboard, widgets: document.dashboard.widgets.map(w => w.id === widget.id ? { ...w, ...change } : w) } });
  const geometry = widget ? widgetLayout(document.dashboard.widgets).find(item => item.i === widget.id)! : null;
  const updateGeometry = (key: 'x' | 'y' | 'w' | 'h', value: string) => {
    if (!geometry || !Number.isFinite(Number(value))) return;
    const layout = { x: geometry.x, y: geometry.y, w: geometry.w, h: geometry.h, [key]: Math.round(Number(value)) };
    layout.x = Math.max(0, Math.min(11, layout.x)); layout.w = Math.max(1, Math.min(12 - layout.x, layout.w));
    layout.y = Math.max(0, layout.y); layout.h = Math.max(3, Math.min(100, layout.h));
    updateWidget({ layout });
  };
  const output = widget && run?.result?.outputs[widget.output];
  const frameColumns = output?.columns || [];
  const binding = widget?.chart_binding;
  return <fieldset className="properties-panel" disabled={disabled}>
    <div className="dock-description"><Settings2 size={17} /><p>{stage ? 'Edit the selected stage. Changes save when you leave a field.' : 'Select a stage or widget to edit its properties.'}</p></div>
    {stage && <Group title={stage.title}><span className="type-tag">{stage.type === 'input' ? 'Data input' : stage.type === 'cleaning' ? 'Data cleaning' : stage.type === 'analysis' ? 'Analysis' : 'Visualization'}</span>
      {stage.type === 'input' && <><p className="muted">{document.input_contract?.columns.length || 0} columns. Manage the CSV, column types, and business context in Data.</p><button type="button" onClick={onOpenData}>Open data settings</button></>}
      {step && <><Field label="Stage title" value={step.title} onCommit={title => onChange({ ...document, steps: document.steps.map(s => s.id === step.id ? { ...s, title } : s) })} />
        <Field label="Purpose" value={step.rationale} onCommit={rationale => onChange({ ...document, steps: document.steps.map(s => s.id === step.id ? { ...s, rationale } : s) })} /></>}
      {widget && <><Field label="Widget title" value={widget.title} onCommit={title => updateWidget({ title })} />
        <Field label="Description" value={widget.description || ''} onCommit={description => updateWidget({ description })} />
        <label className="property-field">Output<select value={widget.output} onChange={e => updateWidget({ output: e.target.value })}>
          {document.steps.flatMap(s => s.outputs).map(name => <option key={name}>{name}</option>)}
        </select></label></>}
      {!!stage.inputs.length && <div className="property-info"><span>Inputs</span><strong>{stage.inputs.join(', ')}</strong></div>}
      {!!stage.outputs.length && <div className="property-info"><span>Outputs</span><strong>{stage.outputs.join(', ')}</strong></div>}
    </Group>}
    {widget?.kind === 'metric' && <Group title="Number display"><label className="property-field">Format<select value={widget.format || ''} onChange={e => updateWidget({ format: e.target.value || null })}>
      <option value="">Automatic</option><option value="integer">Whole number</option><option value=".1f">One decimal</option><option value=".2f">Two decimals</option><option value="percent">Percentage</option>
    </select></label><Field label="Unit" value={widget.unit || ''} onCommit={unit => updateWidget({ unit })} /></Group>}
    {widget?.kind === 'chart' && <Group title="Chart binding">{frameColumns.length > 0 ? <>
      <label className="property-field">Chart type<select value={binding?.kind || 'bar'} onChange={e => updateWidget({ chart_binding: { x: binding?.x || frameColumns[0], y: binding?.y || [frameColumns[1] || frameColumns[0]], ...binding, kind: e.target.value as 'bar' | 'line' | 'scatter' | 'pie' } })}>
        {['bar', 'line', 'scatter', 'pie'].map(kind => <option key={kind}>{kind}</option>)}</select></label>
      <label className="property-field">Category / X<select value={binding?.x || ''} onChange={e => updateWidget({ chart_binding: { kind: 'bar', y: [frameColumns[1] || frameColumns[0]], ...binding, x: e.target.value } })}>
        <option value="" disabled>Select a column</option>{frameColumns.map(c => <option key={c}>{c}</option>)}</select></label>
      <Field label="Value / Y columns (comma separated)" value={binding?.y.join(', ') || ''} onCommit={value => updateWidget({ chart_binding: { kind: 'bar', x: frameColumns[0], ...binding, y: value.split(',').map(s => s.trim()).filter(Boolean) } })} />
    </> : <p className="muted">This chart is produced by an analysis stage. Describe chart changes in chat.</p>}</Group>}
    {geometry && <Group title="Grid position"><p className="muted">Desktop uses a 12-column grid. Use Alt + arrow keys on a widget to move it.</p><div className="property-grid">
      {(['x', 'y', 'w', 'h'] as const).map(key => <Field key={key} label={{x: 'Column', y: 'Row', w: 'Width', h: 'Height'}[key]} type="number" min={key === 'h' ? 3 : key === 'w' ? 1 : 0} max={key === 'x' ? 11 : key === 'w' ? 12 : undefined} value={geometry[key]} onCommit={value => updateGeometry(key, value)} />)}
    </div></Group>}
    {document.parameters.some(parameter => stageParameters.includes(parameter.id)) && <Group title="Stage controls"><ControlSettings document={document} onChange={onChange} parameterIds={stageParameters} run={run} /></Group>}
    {stage && <button className="danger-text" onClick={() => onDelete(stage)}><Trash2 size={15} /> Delete stage</button>}
  </fieldset>;
}
