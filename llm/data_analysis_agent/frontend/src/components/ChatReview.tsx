import { useEffect, useState } from 'react';
import type { ChatItem } from '../lib/projects';
import { request } from '../lib/projects';

export function ChatReview({ item, projectId, developer, disabled, issues, onAction, onUndo }: {
  item: ChatItem; projectId: string; developer: boolean; disabled: boolean; issues: string[];
  onAction: (id: string, action: 'apply' | 'discard' | 'run') => void; onUndo: () => void;
}) {
  const [details, setDetails] = useState<ChatItem>(item);
  useEffect(() => {
    setDetails(item);
    if (!developer || item.kind !== 'proposal') return;
    let disposed = false;
    request<ChatItem>(`/api/projects/${projectId}/chat/items/${item.id}`).then(value => {
      if (!disposed) setDetails({ ...value, stale: item.stale });
    }).catch(() => {});
    return () => { disposed = true; };
  }, [item.id, item.status, item.stale, projectId, developer]);
  const canRun = !item.stale && !issues.length && !item.job_id && !item.run_skipped && (item.status === 'applied' || item.kind === 'needs_run');
  const value = (data: unknown) => data == null ? 'Not present' : typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return <section className="chat-review" aria-label={item.kind === 'proposal' ? 'Review proposed changes' : 'Run required'}>
    <strong>{item.kind === 'proposal' ? `Changes · ${item.status}` : 'Results need a run'}</strong>
    {item.kind === 'proposal' && <>
      <p>{item.calculation_changed ? 'Calculations will need Run.' : 'Presentation only; saved results can be reused.'}</p>
      {!!item.issues?.length && <div className="review-warning"><strong>Incomplete draft</strong><ul>{item.issues.map(issue => <li key={issue}>{issue}</li>)}</ul></div>}
      <details><summary>{item.changes?.length || 0} changed {item.changes?.length === 1 ? 'field' : 'fields'} · review before applying</summary>
        {details.changes?.map((change, index) => <div className="review-change" key={index}>
          <strong>{change.title} · {change.field}</strong><small>{change.stage_id}</small>
          <span>Before</span><pre>{value(change.before)}</pre><span>After</span><pre>{value(change.after)}</pre>
          {item.linked_reasons?.[change.stage_id] && <p>Linked change: {item.linked_reasons[change.stage_id]}</p>}
        </div>)}
      </details>
      <details><summary>Affected stages and controls ({item.affected?.length || 0})</summary><ul>{item.affected?.map(id => <li key={id}><code>{id}</code></li>)}</ul></details>
    </>}
    {item.stale && item.status !== 'discarded' && <p className="review-warning">Workspace or CSV changed. Ask again for a fresh review.</p>}
    {item.status === 'pending' && !item.job_id && <div className="review-actions">
      {item.kind === 'proposal' ? <button className="primary" disabled={disabled || item.stale} onClick={() => onAction(item.id, 'apply')}>Apply</button>
        : <button className="primary" disabled={disabled || !canRun} onClick={() => onAction(item.id, 'run')}>Run and ask again</button>}
      <button disabled={disabled} onClick={() => onAction(item.id, 'discard')}>{item.kind === 'proposal' ? 'Discard' : 'Skip'}</button>
    </div>}
    {item.status === 'applied' && <div className="review-actions"><button disabled={disabled || !canRun} onClick={() => onAction(item.id, 'run')}>Run and ask again</button>
      <button disabled={disabled || item.stale || Boolean(item.job_id)} onClick={onUndo}>Undo</button>
      {!item.job_id && !item.run_skipped && <button disabled={disabled} onClick={() => onAction(item.id, 'discard')}>Skip run</button>}</div>}
    {!!issues.length && item.status !== 'discarded' && !item.job_id && <p className="muted">Complete the workspace before Run: {issues.join('; ')}</p>}
    {item.run_skipped && <p>Run skipped.</p>}
    {item.run_status && <p role="status">Run and follow-up: {item.run_status}{item.run_error ? ` · ${item.run_error}` : ''}</p>}
  </section>;
}
