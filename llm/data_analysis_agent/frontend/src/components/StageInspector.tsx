import { useEffect, useState } from 'react';
import { request } from '../lib/projects';

export function StageInspector({ projectId, stageId, version, runKey, onSelect }: {
  projectId: string; stageId: string | null; version: number; runKey: string; onSelect: (id: string) => void;
}) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    setData(null); setError(''); setNotice('');
    if (!stageId) return;
    const abort = new AbortController();
    request(`/api/projects/${projectId}/stages/${encodeURIComponent(stageId)}/inspect`, { signal: abort.signal })
      .then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => abort.abort();
  }, [projectId, stageId, version, runKey]);
  const serialized = data ? JSON.stringify(data, null, 2) : '';
  return <div className="stage-inspector"><p className="dock-description">Read-only developer inspection. Changes still go through chat review.</p>
    {!stageId && <p>Select a stage or widget to inspect it.</p>}{error && <p role="alert">{error}</p>}
    {stageId && !data && !error && <p role="status">Loading inspection…</p>}
    {data && <><h3>{data.context.label}</h3><p>Workspace v{data.workspace_version}</p>
      <div className="review-actions"><a className="button" href={`/api/projects/${projectId}/stages/${encodeURIComponent(stageId!)}/inspect.json`} download>Download JSON</a><button onClick={async () => {
        try { if (!navigator.clipboard) throw new Error(); await navigator.clipboard.writeText(serialized); setNotice('Inspection copied.'); }
        catch { setNotice('Clipboard unavailable. Use Download JSON or select text below.'); }
      }}>Copy inspection</button></div>{notice && <p role="status">{notice}</p>}
      <h4>Producer / dependencies</h4>{data.dependencies.length ? data.dependencies.map((id: string) => <button className="inspector-link" key={id} onClick={() => onSelect(id)}>{id}</button>) : <p>No upstream stage.</p>}
      <h4>Saved Python</h4>{data.source ? <pre>{data.source}</pre> : <p>This card has no Python source. Use its configuration and producer links.</p>}
      <details open><summary>Stage configuration</summary><pre>{JSON.stringify(data.configuration, null, 2)}</pre></details>
      <details><summary>Inputs, outputs and controls</summary><pre>{JSON.stringify({ inputs: data.inputs, outputs: data.outputs, controls: data.controls }, null, 2)}</pre></details>
      <details><summary>Last successful results and provenance</summary><pre>{JSON.stringify(data.saved_results, null, 2)}</pre></details>
      <details><summary>Recent run diagnostics</summary><pre>{JSON.stringify(data.diagnostics, null, 2)}</pre></details>
    </>}
  </div>;
}
