import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Code2,
  Trash2,
  HelpCircle,
  Check,
  Clock,
  ArrowRight,
  Database,
  Table as TableIcon,
  AlertTriangle,
  Download,
  Copy,
  ChevronDown,
  ChevronUp,
  FileCode,
  Layers,
  Wand2,
} from 'lucide-react';
import type { Job, Run, Stage, Step, WorkspaceDocument, Output } from '../lib/projects';
import { DataTableViewer } from './DataTableViewer';

interface StageInternalsCardProps {
  step: Step;
  stage: Stage;
  document: WorkspaceDocument;
  run: Run | null;
  job?: Job;
  isPending: boolean;
  onSave: (doc: WorkspaceDocument) => void;
  onDelete: (stage: Stage) => void;
  onRefineWithAI: (stepId: string, initialPrompt?: string) => void;
  onExplainWithAI: (stepId: string) => void;
  onFixWithAI?: (stepId: string, error: string) => void;
  disabled: boolean;
  projectId: string;
}

export const StageInternalsCard: React.FC<StageInternalsCardProps> = ({
  step,
  stage,
  document,
  run,
  job,
  isPending,
  onSave,
  onDelete,
  onRefineWithAI,
  onExplainWithAI,
  onFixWithAI,
  disabled,
  projectId,
}) => {
  const [codeOpen, setCodeOpen] = useState(true);
  const [isEditingCode, setIsEditingCode] = useState(false);
  const [codeDraft, setCodeDraft] = useState(step.code);
  const [copiedCode, setCopiedCode] = useState(false);
  const [rationaleDraft, setRationaleDraft] = useState(step.rationale);
  const [titleDraft, setTitleDraft] = useState(step.title);

  useEffect(() => {
    setCodeDraft(step.code);
  }, [step.code]);

  useEffect(() => {
    setRationaleDraft(step.rationale);
  }, [step.rationale]);

  useEffect(() => {
    setTitleDraft(step.title);
  }, [step.title]);

  // Compute status
  const getStatus = (): { label: string; kind: string; duration?: number } => {
    const stepId = step.id;
    const event = [...(job?.events || [])].reverse().find((e) => e.step_id === stepId);
    if (job?.status === 'failed' && event?.status === 'running') {
      return { label: 'Failed', kind: 'failed' };
    }
    if (job && ['queued', 'running'].includes(job.status) && event) {
      if (event.status === 'running') return { label: 'Running', kind: 'running' };
      if (event.cached) return { label: 'Reused', kind: 'reused' };
      return { label: 'Succeeded', kind: 'succeeded' };
    }
    if (event?.status === 'blocked') {
      return { label: 'Blocked', kind: 'blocked' };
    }
    const saved = [...(run?.result?.steps || [])].reverse().find((e) => e.step_id === stepId);
    if (isPending && !saved) {
      return { label: 'Pending', kind: 'pending' };
    }
    if (saved) {
      return {
        label: saved.cached ? 'Reused' : saved.status === 'failed' ? 'Failed' : 'Succeeded',
        kind: saved.cached ? 'reused' : saved.status === 'failed' ? 'failed' : 'succeeded',
        duration: saved.duration_ms,
      };
    }
    return { label: isPending ? 'Pending' : 'Ready', kind: isPending ? 'pending' : 'ready' };
  };

  const statusInfo = getStatus();

  // Find step error if failed
  const latestEvent = [...(job?.events || [])].reverse().find((e) => e.step_id === step.id);
  const stepError =
    statusInfo.kind === 'failed'
      ? latestEvent?.message || job?.error || run?.error || 'Step failed during execution'
      : null;

  // Cleanup impact if cleanup stage
  const cleanupImpact = run?.result?.cleanup_impacts?.find((i) => i.step_id === step.id);

  // Find downstream consumers
  const consumingWidgets = document.dashboard.widgets.filter((w) => step.outputs.includes(w.output));
  const consumingSteps = document.steps.filter(
    (s) => s.id !== step.id && s.inputs.some((i) => step.outputs.includes(i))
  );

  const handleSaveCode = () => {
    if (codeDraft === step.code) {
      setIsEditingCode(false);
      return;
    }
    const updatedSteps = document.steps.map((s) => (s.id === step.id ? { ...s, code: codeDraft } : s));
    onSave({ ...document, steps: updatedSteps });
    setIsEditingCode(false);
  };

  const handleSaveTitle = (newTitle: string) => {
    if (newTitle === step.title || !newTitle.trim()) return;
    const updatedSteps = document.steps.map((s) => (s.id === step.id ? { ...s, title: newTitle.trim() } : s));
    onSave({ ...document, steps: updatedSteps });
  };

  const handleSaveRationale = (newRationale: string) => {
    if (newRationale === step.rationale) return;
    const updatedSteps = document.steps.map((s) => (s.id === step.id ? { ...s, rationale: newRationale.trim() } : s));
    onSave({ ...document, steps: updatedSteps });
  };

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(step.code);
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <article className="stage-internals-card" aria-label={`Stage ${step.title}`}>
      {/* Stage Header */}
      <header className="stage-internals-header">
        <div className="stage-header-title-row">
          <span className={`state-badge state-${statusInfo.kind}`}>
            <span />
            {statusInfo.label}
          </span>
          <span className="type-tag">{step.stage === 'cleanup' ? 'Data cleaning' : 'Analysis'}</span>
          <code className="step-id-badge">step:{step.id}</code>
          {statusInfo.duration != null && (
            <span className="stage-duration">
              <Clock size={11} />
              {statusInfo.duration} ms
            </span>
          )}
        </div>

        <div className="stage-internals-actions">
          <button
            type="button"
            className="ai-action-btn"
            disabled={disabled}
            onClick={() => onRefineWithAI(`step:${step.id}`)}
            title="Refine this stage with AI"
          >
            <Sparkles size={14} />
            <span>Refine with AI</span>
          </button>
          <button
            type="button"
            className="icon-button"
            disabled={disabled}
            onClick={() => onExplainWithAI(`step:${step.id}`)}
            title="Explain this stage"
            aria-label="Explain stage"
          >
            <HelpCircle size={15} />
          </button>
          <button
            type="button"
            className="icon-button stage-delete-btn"
            disabled={disabled}
            onClick={() => onDelete(stage)}
            title="Delete this stage"
            aria-label="Delete stage"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </header>

      <div className="stage-internals-body">
        {/* Title & Purpose Row */}
        <div className="stage-meta-section">
          <div className="stage-title-field">
            <label htmlFor={`title-${step.id}`}>Stage title</label>
            <input
              id={`title-${step.id}`}
              type="text"
              value={titleDraft}
              disabled={disabled}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={() => handleSaveTitle(titleDraft)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') e.currentTarget.blur();
              }}
              placeholder="Stage title"
            />
          </div>

          <div className="stage-rationale-field">
            <label htmlFor={`rationale-${step.id}`}>Purpose & rationale</label>
            <textarea
              id={`rationale-${step.id}`}
              rows={2}
              value={rationaleDraft}
              disabled={disabled}
              onChange={(e) => setRationaleDraft(e.target.value)}
              onBlur={() => handleSaveRationale(rationaleDraft)}
              placeholder="Explain why this stage is needed and how it transforms the data..."
            />
          </div>
        </div>

        {/* Configuration Flow (Inputs, Outputs, Parameters) */}
        <div className="stage-flow-section">
          <div className="flow-column">
            <span className="flow-label">
              <Database size={12} />
              Inputs:
            </span>
            <div className="flow-chips">
              {step.inputs.map((inp) => (
                <code key={inp} className="flow-chip input-chip">
                  {inp}
                </code>
              ))}
            </div>
          </div>

          <ArrowRight size={14} className="flow-arrow" />

          <div className="flow-column">
            <span className="flow-label">
              <Layers size={12} />
              Outputs:
            </span>
            <div className="flow-chips">
              {step.outputs.map((out) => (
                <code key={out} className="flow-chip output-chip">
                  {out}
                </code>
              ))}
            </div>
          </div>

          {step.parameters_used && step.parameters_used.length > 0 && (
            <div className="flow-column flow-parameters">
              <span className="flow-label">Parameters used:</span>
              <div className="flow-chips">
                {step.parameters_used.map((param) => (
                  <span key={param} className="flow-chip param-chip">
                    {param}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Python Code Section */}
        <div className="stage-code-section">
          <div className="code-box-header">
            <div className="code-box-title">
              <FileCode size={14} />
              <strong>Python Implementation</strong>
              <span className="code-lang-tag">Python 3</span>
              <span className="code-lines">
                {(isEditingCode ? codeDraft : step.code).split('\n').length} lines
              </span>
            </div>
            <div className="code-box-actions">
              <button
                type="button"
                className="code-action-btn"
                onClick={handleCopyCode}
                title="Copy Python code"
              >
                {copiedCode ? <Check size={12} /> : <Copy size={12} />}
                <span>{copiedCode ? 'Copied' : 'Copy'}</span>
              </button>
              {isEditingCode ? (
                <>
                  <button
                    type="button"
                    className="code-action-btn primary"
                    disabled={disabled}
                    onClick={handleSaveCode}
                  >
                    <Check size={12} />
                    <span>Save Code</span>
                  </button>
                  <button
                    type="button"
                    className="code-action-btn"
                    onClick={() => {
                      setCodeDraft(step.code);
                      setIsEditingCode(false);
                    }}
                  >
                    <span>Cancel</span>
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="code-action-btn"
                  disabled={disabled}
                  onClick={() => setIsEditingCode(true)}
                >
                  <Code2 size={12} />
                  <span>Edit Code</span>
                </button>
              )}
              <button
                type="button"
                className="icon-button"
                onClick={() => setCodeOpen(!codeOpen)}
                aria-label={codeOpen ? 'Collapse code' : 'Expand code'}
              >
                {codeOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>
          </div>

          {codeOpen && (
            <div className="code-container">
              {isEditingCode ? (
                <textarea
                  className="code-editor"
                  value={codeDraft}
                  disabled={disabled}
                  onChange={(e) => setCodeDraft(e.target.value)}
                  rows={Math.max(6, Math.min(22, codeDraft.split('\n').length + 2))}
                  spellCheck={false}
                  autoCapitalize="off"
                  autoComplete="off"
                />
              ) : (
                <pre className="code-viewer">
                  <code>{step.code}</code>
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Cleanup Impact Statistics (if cleanup stage) */}
        {cleanupImpact && (
          <div className="stage-cleanup-impact">
            <h4>Cleanup Impact & Verification</h4>
            <div className="impact-grid">
              <div className="impact-stat">
                <span className="impact-label">Rows</span>
                <span className="impact-value">
                  {cleanupImpact.before_rows.toLocaleString()} →{' '}
                  <strong>{cleanupImpact.after_rows.toLocaleString()}</strong>
                </span>
                {cleanupImpact.removed_rows > 0 && (
                  <span className="impact-delta negative">
                    -{cleanupImpact.removed_rows.toLocaleString()} rows
                  </span>
                )}
              </div>
              <div className="impact-stat">
                <span className="impact-label">Missing Cells</span>
                <span className="impact-value">
                  {cleanupImpact.before_missing_cells.toLocaleString()} →{' '}
                  <strong>{cleanupImpact.after_missing_cells.toLocaleString()}</strong>
                </span>
                {cleanupImpact.before_missing_cells > cleanupImpact.after_missing_cells && (
                  <span className="impact-delta positive">
                    -{cleanupImpact.before_missing_cells - cleanupImpact.after_missing_cells} missing
                  </span>
                )}
              </div>
              {cleanupImpact.columns_removed.length > 0 && (
                <div className="impact-stat">
                  <span className="impact-label">Columns Removed</span>
                  <span className="impact-value">{cleanupImpact.columns_removed.join(', ')}</span>
                </div>
              )}
              {cleanupImpact.columns_added.length > 0 && (
                <div className="impact-stat">
                  <span className="impact-label">Columns Added</span>
                  <span className="impact-value">{cleanupImpact.columns_added.join(', ')}</span>
                </div>
              )}
            </div>
            {cleanupImpact.rationale && <p className="impact-rationale">{cleanupImpact.rationale}</p>}
            {cleanupImpact.requires_confirmation && (
              <div className="impact-warning">
                <AlertTriangle size={14} />
                <span>Requires user confirmation before accepting release</span>
              </div>
            )}
          </div>
        )}

        {/* Error Diagnostics (if failed) */}
        {stepError && (
          <div className="stage-error-banner" role="alert">
            <div className="error-icon">
              <AlertTriangle size={16} />
            </div>
            <div className="error-content">
              <strong>Execution Error in {step.title}</strong>
              <pre className="error-traceback">{stepError}</pre>
            </div>
            {onFixWithAI && (
              <button
                type="button"
                className="primary fix-ai-btn"
                onClick={() => onFixWithAI(`step:${step.id}`, stepError)}
              >
                <Wand2 size={13} />
                <span>Fix with AI</span>
              </button>
            )}
          </div>
        )}

        {/* Output Previews */}
        {run?.result?.outputs && (
          <div className="stage-outputs-section">
            <h4>Stage Outputs & Verification</h4>
            {step.outputs.map((outName) => {
              const output = run.result?.outputs[outName];
              if (!output) {
                return (
                  <div key={outName} className="output-pending-note">
                    <code>{outName}</code>: Not yet calculated. Run workspace to inspect results.
                  </div>
                );
              }

              if (output.kind === 'table' && output.columns && output.rows) {
                return (
                  <div key={outName} className="table-output-card">
                    <div className="table-output-header">
                      <div className="table-output-title">
                        <TableIcon size={14} />
                        <strong>Table: {outName}</strong>
                        <span className="type-tag">
                          {output.total_rows != null ? `${output.total_rows.toLocaleString()} rows` : ''} ·{' '}
                          {output.columns.length} columns
                        </span>
                      </div>
                      <a
                        className="button table-download-btn"
                        href={`/api/projects/${projectId}/runs/${run.run_id}/tables/${outName}`}
                        download={`${outName}.csv`}
                        title="Download complete table as CSV"
                      >
                        <Download size={13} />
                        <span>Download CSV</span>
                      </a>
                    </div>
                    <div className="table-viewer-wrapper">
                      <DataTableViewer
                        table={{
                          columns: output.columns,
                          rows: output.rows,
                          total_rows: output.total_rows || output.rows.length,
                        }}
                        embedded={true}
                      />
                    </div>
                  </div>
                );
              }

              if (output.kind === 'metric' || output.kind === 'text') {
                return (
                  <div key={outName} className="metric-output-card">
                    <span className="metric-output-label">Metric: {outName}</span>
                    <strong className="metric-output-value">{String(output.value ?? 'null')}</strong>
                  </div>
                );
              }

              return (
                <div key={outName} className="generic-output-card">
                  <code>{outName}</code>: {output.kind} artifact
                </div>
              );
            })}
          </div>
        )}

        {/* Downstream Consumers info */}
        {(consumingWidgets.length > 0 || consumingSteps.length > 0) && (
          <div className="stage-consumers-footer">
            <span className="consumers-label">Downstream consumers:</span>
            {consumingSteps.map((s) => (
              <span key={s.id} className="consumer-tag step-tag" title={`Step ${s.title}`}>
                {s.title}
              </span>
            ))}
            {consumingWidgets.map((w) => (
              <span key={w.id} className="consumer-tag widget-tag" title={`Dashboard widget ${w.title}`}>
                Widget: {w.title}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
};
