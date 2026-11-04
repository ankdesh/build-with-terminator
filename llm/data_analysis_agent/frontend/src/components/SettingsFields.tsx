import type { Run, WorkspaceDocument } from '../lib/projects';

export function SettingsField({ label, value, onCommit, type = 'text', min, max }: {
  label: string; value: string | number; onCommit: (value: string) => void; type?: string; min?: number; max?: number;
}) {
  return <label className="property-field">{label}<input key={String(value)} type={type} defaultValue={value} min={min} max={max}
    onBlur={event => { if (event.target.value !== String(value)) onCommit(event.target.value); }}
    onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); }} /></label>;
}

export function ControlSettings({ document, onChange, parameterIds, run }: {
  document: WorkspaceDocument; onChange: (document: WorkspaceDocument) => void; parameterIds?: string[]; run: Run | null;
}) {
  const parameters = document.parameters.filter(parameter => !parameterIds || parameterIds.includes(parameter.id));
  return <div className="control-settings-grid">{parameters.map(parameter => {
    const update = (change: Partial<typeof parameter>) => onChange({ ...document, parameters: document.parameters.map(p => p.id === parameter.id ? { ...p, ...change } : p) });
    const choices = run?.result?.parameter_options[parameter.id] || parameter.choices;
    return <section className="parameter-properties" key={parameter.id}><code>{parameter.id}</code>
      <SettingsField label="Label" value={parameter.label} onCommit={label => update({ label })} />
      {parameter.kind === 'boolean' ? <label className="checkbox-label"><input type="checkbox" checked={parameter.default === true} onChange={e => update({ default: e.target.checked })} /> Default value</label> :
        parameter.kind === 'select' ? <label className="property-field">Default value<select value={JSON.stringify(parameter.default)} onChange={e => update({ default: JSON.parse(e.target.value) })}>
          <option value="null">{parameter.filter_column ? 'All' : 'No selection'}</option>
          {choices.filter(value => value !== null).map((value, index) => <option key={index} value={JSON.stringify(value)}>{String(value)}</option>)}
        </select></label> : <SettingsField label="Default value" value={parameter.default == null ? '' : String(parameter.default)} type={['number', 'integer'].includes(parameter.kind) ? 'number' : 'text'} onCommit={value => update({ default: value === '' ? null : ['number', 'integer'].includes(parameter.kind) ? Number(value) : value })} />}
      {['number', 'integer'].includes(parameter.kind) && <div className="property-grid"><SettingsField label="Minimum" type="number" value={parameter.minimum ?? ''} onCommit={v => update({minimum: v === '' ? null : Number(v)})} /><SettingsField label="Maximum" type="number" value={parameter.maximum ?? ''} onCommit={v => update({maximum: v === '' ? null : Number(v)})} /></div>}
    </section>;
  })}</div>;
}
