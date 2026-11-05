import type { ChartSpec, DataProfile, TableData } from './types';

export type Scalar = string | number | boolean | null;
export interface Parameter {
  id: string; label: string; kind: 'number' | 'integer' | 'string' | 'boolean' | 'select';
  default: Scalar; minimum: number | null; maximum: number | null; choices: Scalar[];
  filter_column: string | null; filter_artifact?: string;
}
export interface Step {
  id: string; title: string; stage: 'cleanup' | 'analysis'; code: string; rationale: string;
  inputs: string[]; outputs: string[]; parameters_used: string[] | null;
}
export interface GridPosition { x: number; y: number; w: number; h: number }
export interface Widget {
  id: string; kind: 'metric' | 'chart' | 'table' | 'text'; title: string; output: string; width: number;
  format?: string | null; unit?: string; description?: string; layout?: GridPosition | null;
  chart_binding?: {kind: 'bar' | 'line' | 'scatter' | 'pie'; x: string; y: string[]; x_label?: string | null; y_label?: string | null} | null;
}
export interface DashboardSpec { title: string; subtitle: string; widgets: Widget[] }
export interface Column { name: string; dtype: string; nullable: boolean; description: string; date_format?: string | null }
export interface WorkspaceDocument {
  title: string; summary: string; input_enabled: boolean; input_contract: {columns: Column[]; encoding: string; delimiter: string} | null;
  steps: Step[]; parameters: Parameter[]; dashboard: DashboardSpec; dependencies: string[]; seed: number;
}
export interface Revision {
  schema_version?: number; revision_id: string; title: string; summary: string; steps: Step[]; parameters: Parameter[];
  dashboard: DashboardSpec;
}
export interface Stage {
  id: string; type: 'input' | 'cleaning' | 'analysis' | 'visualization'; title: string; rationale?: string;
  inputs: string[]; outputs: string[]; dependencies: string[];
}
export interface Workspace {
  version: number; document: WorkspaceDocument; issues: string[]; stages: Stage[]; can_undo: boolean; can_redo: boolean;
  validated_run_id: string | null; calculation_pending: boolean;
}
export interface Output {
  kind: string; value?: Scalar | ChartSpec; columns?: string[]; rows?: TableData['rows']; total_rows?: number;
}
export interface Run {
  run_id: string; revision_id: string; dataset_name: string; input_hash: string;
  status: string; parameters: Record<string, Scalar>; error: string | null; finished_at?: string | null;
  validation_mode?: string; workspace_version?: number; source_run_id?: string | null;
  result: {
    outputs: Record<string, Output>; widgets?: Record<string, Output>;
    steps?: {step_id: string; title: string; status: string; cached?: boolean; duration_ms?: number}[];
    cleanup_impacts: { step_id: string; title: string; rationale: string; before_rows: number; after_rows: number;
      removed_rows: number; before_missing_cells: number; after_missing_cells: number;
      changed_cells_in_matched_rows: number | null; requires_confirmation: boolean; columns_removed: string[]; columns_added: string[] }[];
    parameter_options: Record<string, Scalar[]>;
  } | null;
}
export interface Job {
  partial?: boolean;
  id: string; revision_id: string; workspace_version: number; status: string; run_id: string | null; error: string | null;
  events: {event: string; message?: string; step_id?: string; title?: string; status?: string; cached?: boolean}[];
}
export interface Target {
  status: 'running' | 'stopped' | 'failed'; url: string | null; port: number | null; error: string | null;
  applied_revision?: string | null; pending?: boolean; input_mode?: string; last_error?: string | null; active_run?: boolean;
}
export interface RuntimeState {
  mode: 'live' | 'runtime'; revision: Revision | null; presentation: {title: string; dashboard: DashboardSpec} | null;
  pending: boolean; calculation_pending: boolean; display_run: Run | null; dataset_name: string | null; has_input: boolean; input_mode: string;
  last_error: string | null; active_run: Run | null; events: {title?: string; status?: string; message?: string}[];
  sequence: number; instance_id: string; control_notice?: string | null;
}
export interface ProjectSummary { id: string; title: string; dataset_name: string | null; accepted_id: string | null }
export interface ChatContext { stage_id: string | null; label: string }
export interface ChatItem {
  id: string; kind: 'proposal' | 'needs_run'; status: 'pending' | 'applied' | 'discarded'; message: string;
  context: ChatContext; version: number; input_hash: string | null; applied_version?: number; stale?: boolean;
  changes?: {stage_id: string; title: string; field: string; before: unknown; after: unknown}[];
  affected?: string[]; linked_reasons?: Record<string, string>; calculation_changed?: boolean; issues?: string[];
  job_id?: string; run_status?: string; run_error?: string; run_skipped?: boolean;
}
export interface ChatMessage {
  id?: number; role: string; content: string; created_at: string;
  metadata?: {context?: ChatContext; kind?: string; item_id?: string; run_id?: string | null; revision_id?: string | null; input_hash?: string | null; workspace_version?: number};
}
export interface ProjectView {
  partial_run?: Run | null;
  project: ProjectSummary & { draft_id: string | null; description: string; profile: DataProfile | null; dataset_hash: string | null; accepted_run_id?: string | null };
  workspace: Workspace; draft: Revision | null; display_run: Run | null; display_revision: Revision | null;
  messages: ChatMessage[]; chat_items: ChatItem[];
  revisions: { id: string; summary: string; accepted: number; created_at?: string }[];
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail || error.error || response.statusText));
  }
  return response.json();
}
export const jsonBody = (value: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value),
});

export async function streamProject(path: string, body: unknown, onEvent: (event: any) => void, signal: AbortSignal): Promise<void> {
  const response = await fetch(path, { ...jsonBody(body), signal });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail || response.statusText));
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error('The server did not return an event stream');
  const decoder = new TextDecoder();
  let buffer = '';
  const dispatch = (frame: string) => {
    const lines = frame.split('\n');
    const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
    if (data) onEvent(JSON.parse(data));
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        dispatch(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
      }
      if (done) { if (buffer.trim()) dispatch(buffer); break; }
    }
  } finally { reader.releaseLock(); }
}
