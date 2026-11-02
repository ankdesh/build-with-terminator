import {
  ChatMessage,
  ExecutionResult,
  SessionDetail,
  SessionMetadata,
} from './types';

const API_BASE = '/api';

export async function listSessions(): Promise<SessionMetadata[]> {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(`Failed to list sessions: ${res.statusText}`);
  return res.json();
}

export async function createSession(title?: string): Promise<SessionMetadata> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.statusText}`);
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.statusText}`);
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete session: ${res.statusText}`);
}

export async function uploadDataset(
  sessionId: string,
  csvFile: File,
  descFile?: File | null,
  descText?: string
): Promise<SessionDetail> {
  const formData = new FormData();
  formData.append('csv_file', csvFile);
  if (descFile) {
    formData.append('desc_file', descFile);
  }
  if (descText) {
    formData.append('description_text', descText);
  }

  const res = await fetch(`${API_BASE}/sessions/${sessionId}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed: ${res.statusText}`);
  }
  return res.json();
}

export async function getMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error(`Failed to get messages: ${res.statusText}`);
  return res.json();
}

export async function exportCsv(
  sessionId: string,
  columns: string[],
  rows: Record<string, any>[],
  filename?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/export-csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ columns, rows, filename }),
  });
  if (!res.ok) throw new Error('Failed to export CSV');

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'export.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export interface StreamCallbacks {
  onStatus?: (status: string) => void;
  onPlan?: (plan: string) => void;
  onCode?: (code: string) => void;
  onLog?: (log: string) => void;
  onToken?: (token: string) => void;
  onResult?: (result: ExecutionResult) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
}

export async function streamChat(
  sessionId: string,
  query: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Chat request failed with ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body stream');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = 'message';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith('event:')) {
        currentEvent = trimmed.substring(6).trim();
      } else if (trimmed.startsWith('data:')) {
        const rawData = trimmed.substring(5).trim();
        let parsedData: any = rawData;
        try {
          parsedData = JSON.parse(rawData);
        } catch {
          parsedData = rawData;
        }

        switch (currentEvent) {
          case 'status':
            callbacks.onStatus?.(typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData));
            break;
          case 'plan':
            callbacks.onPlan?.(typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData));
            break;
          case 'code':
            callbacks.onCode?.(typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData));
            break;
          case 'log':
            callbacks.onLog?.(typeof parsedData === 'string' ? parsedData : JSON.stringify(parsedData));
            break;
          case 'token':
            callbacks.onToken?.(typeof parsedData === 'string' ? parsedData : '');
            break;
          case 'execution_result':
            callbacks.onResult?.(parsedData as ExecutionResult);
            break;
          case 'error':
            callbacks.onError?.(typeof parsedData === 'string' ? parsedData : parsedData.error || 'Unknown error');
            break;
          case 'done':
            callbacks.onDone?.();
            break;
        }
      }
    }
  }
}
