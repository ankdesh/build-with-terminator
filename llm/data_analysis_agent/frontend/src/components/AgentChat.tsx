import { useEffect, useState } from 'react';
import type { ChatItem, AnalysisArtifact, AnalysisRule } from '../lib/projects';
import { jsonBody, request } from '../lib/projects';
import { ChartViewer } from './ChartViewer';
import { DataTableViewer } from './DataTableViewer';

export function ChatText({ text }: {text: string}) {
  return <p>{text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part.startsWith('`') && part.endsWith('`') ? <code key={index}>{part.slice(1, -1)}</code> : part)}</p>;
}

export function ClarificationCard({ item, disabled, onAnswer }: {
  item: ChatItem; disabled: boolean;
  onAnswer: (id: string, answers: {question_id: string; text: string; save_as_rule: boolean}[], refresh: boolean) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [rules, setRules] = useState<Record<string, boolean>>({});
  const [refresh, setRefresh] = useState(false);
  const questions = item.questions || [];
  return <form className="chat-review" aria-label="Clarification required" onSubmit={event => {
    event.preventDefault(); onAnswer(item.id, questions.map(q => ({question_id: q.id, text: values[q.id] || '', save_as_rule: !!rules[q.id]})), refresh);
  }}><strong>Clarification · {item.status}</strong>
    {questions.map(q => <fieldset key={q.id} disabled={disabled || item.status !== 'pending'}>
      <legend>{q.question}</legend>{q.reason && <p className="muted">{q.reason}</p>}
      <div className="review-actions">{q.choices.map(choice => <button type="button" key={choice} aria-pressed={values[q.id] === choice} onClick={() => setValues({...values, [q.id]: choice})}>{choice}</button>)}</div>
      <label>Your answer<input aria-label={q.question} value={values[q.id] || ''} maxLength={4000} onChange={e => setValues({...values, [q.id]: e.target.value})} /></label>
      {q.saveable && <label className="checkbox-label"><input type="checkbox" checked={!!rules[q.id]} onChange={e => setRules({...rules, [q.id]: e.target.checked})} />Save as a project rule</label>}
    </fieldset>)}
    {item.stale && item.status === 'pending' && <label className="checkbox-label"><input type="checkbox" checked={refresh} onChange={e => setRefresh(e.target.checked)} />Recheck this request with the current workspace and CSV</label>}
    {item.status === 'pending' && <button className="primary" disabled={disabled || questions.some(q => !values[q.id]?.trim()) || (item.stale && !refresh)}>Continue request</button>}
    {item.answers?.map((answer, index) => <p key={index}>{answer.answer}</p>)}
  </form>;
}

export function AnalysisResult({ projectId, artifactId, onReady }: {projectId: string; artifactId: string; onReady?: () => void}) {
  const [artifact, setArtifact] = useState<AnalysisArtifact>();
  const [error, setError] = useState('');
  const [downloadError, setDownloadError] = useState('');
  useEffect(() => { let disposed = false; request<AnalysisArtifact>(`/api/projects/${projectId}/analysis/${artifactId}`).then(value => { if (!disposed) setArtifact(value); }).catch(e => { if (!disposed) setError(e.message); }); return () => { disposed = true; }; }, [projectId, artifactId]);
  useEffect(() => { if (artifact) onReady?.(); }, [artifact]);
  if (error) return <p role="alert">{error}</p>;
  if (!artifact) return <p>Loading temporary result…</p>;
  const result = artifact.result;
  const download = async () => {
    setDownloadError('');
    try {
      const response = await fetch(`/api/projects/${projectId}/analysis/${artifactId}/table.csv`);
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail || 'CSV download failed'); }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = 'analysis.csv'; link.click(); URL.revokeObjectURL(url);
    } catch (e: any) { setDownloadError(e.message); }
  };
  return <section className="chat-analysis" aria-label="Temporary analysis result">
    <small className="message-provenance">Temporary · {artifact.provenance.source} · Input {artifact.provenance.input_hash?.slice(0, 8)} · Workspace {artifact.provenance.workspace_version}</small>
    {result.kind === 'metric' && <strong>{String(result.value)}</strong>}
    {result.kind === 'text' && <p>{String(result.value)}</p>}
    {result.chart && <ChartViewer spec={result.chart} />}
    {result.kind === 'table' && <><DataTableViewer table={{columns: result.columns || [], rows: result.rows || [], total_rows: result.total_rows || 0}} onExportCsv={download} />
      <small>Preview: up to 100 rows and 20 columns. CSV contains the full result.</small></>}
    {artifact.expired && <p>Temporary files expired. Ask to calculate this result again.</p>}
    {downloadError && <p role="alert">{downloadError}</p>}
  </section>;
}

export function ProjectRules({ projectId, rules, onChange, disabled }: {projectId: string; rules: AnalysisRule[]; onChange: () => Promise<void>; disabled: boolean}) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  async function change(id?: string, value?: string) {
    setError('');
    try {
      await request(`/api/projects/${projectId}/analysis-rules${id ? `/${id}` : ''}`, value === undefined ? {method: 'DELETE'} : {...jsonBody({text: value}), method: id ? 'PUT' : 'POST'});
      setText(''); await onChange();
    } catch (e: any) { setError(e.message); }
  }
  return <details className="project-rules"><summary>Project analysis rules ({rules.length})</summary>
    <p>Rules guide future requests. Review them after the input columns change.</p>{error && <p role="alert">{error}</p>}
    {rules.map(rule => <div key={rule.id}><textarea aria-label="Project rule" defaultValue={rule.text} maxLength={4000} disabled={disabled} onBlur={e => { if (e.target.value.trim() && (e.target.value !== rule.text || rule.needs_review)) change(rule.id, e.target.value); }} />
      {rule.needs_review && <p>Input columns changed. Review and save this rule.</p>}
      <button type="button" disabled={disabled} onClick={() => change(rule.id)}>Delete rule</button>
      {rule.needs_review && <button type="button" disabled={disabled} onClick={() => change(rule.id, rule.text)}>Confirm rule</button>}</div>)}
    <form onSubmit={e => { e.preventDefault(); change(undefined, text); }}><input aria-label="New project rule" value={text} maxLength={4000} disabled={disabled} onChange={e => setText(e.target.value)} /><button disabled={disabled || !text.trim()}>Add rule</button></form>
  </details>;
}
