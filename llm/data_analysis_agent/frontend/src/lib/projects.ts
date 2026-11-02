import type { ChartSpec, DataProfile, TableData } from './types';

export type Scalar = string | number | boolean | null;
export interface Parameter {
  id: string; label: string; kind: 'number' | 'integer' | 'string' | 'boolean' | 'select';
  default: Scalar; minimum: number | null; maximum: number | null; choices: Scalar[];
  filter_column: string | null;
}
export interface Step {
  id: string; title: string; stage: string; code: string; rationale: string;
  inputs: string[]; outputs: string[];
}
export interface Revision {
  revision_id: string; title: string; summary: string; steps: Step[]; parameters: Parameter[];
  dashboard: { title: string; subtitle: string; widgets: { id: string; kind: string; title: string; output: string; width: number; format?: string | null }[] };
}
export interface Run {
  run_id: string; revision_id: string; dataset_name: string; input_hash: string;
  status: string; parameters: Record<string, Scalar>; error: string | null;
  result: {
    outputs: Record<string, { kind: string; value?: Scalar | ChartSpec; columns?: string[]; rows?: TableData['rows']; total_rows?: number }>;
    widgets?: Record<string, { kind: string; value?: Scalar | ChartSpec; columns?: string[]; rows?: TableData['rows']; total_rows?: number }>;
    cleanup_impacts: { step_id: string; title: string; rationale: string; before_rows: number; after_rows: number;
      removed_rows: number; before_missing_cells: number; after_missing_cells: number;
      changed_cells_in_matched_rows: number | null; requires_confirmation: boolean; columns_removed: string[]; columns_added: string[] }[];
    parameter_options: Record<string, Scalar[]>;
  } | null;
}
export interface ProjectSummary { id: string; title: string; dataset_name: string | null; accepted_id: string | null }
export interface ProjectView {
  project: ProjectSummary & { draft_id: string | null; description: string; profile: DataProfile | null; dataset_hash: string | null };
  draft: Revision | null; display_run: Run | null; display_revision: Revision | null;
  messages: { role: string; content: string; created_at: string }[];
  revisions: { id: string; summary: string; accepted: number }[];
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
