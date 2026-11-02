export interface ChartSpec {
  title: string;
  description?: string;
  option: Record<string, any>;
}

export interface TableData {
  columns: string[];
  rows: Record<string, any>[];
  total_rows: number;
}

export interface ExecutionResult {
  success: boolean;
  plan: string;
  explanation: string;
  code: string;
  stdout: string;
  chart?: ChartSpec | null;
  table?: TableData | null;
  error_traceback?: string | null;
  execution_time_ms: number;
  retries_attempted: number;
  step_logs?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  plan?: string | null;
  execution_result?: ExecutionResult | null;
  created_at?: string;
}

export interface ColumnSummary {
  name: string;
  data_type: string;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  sample_values: any[];
  min_value?: any;
  max_value?: any;
  mean_value?: number;
  median_value?: number;
  column_description: string;
}

export interface QualityFlag {
  category: string;
  severity: 'info' | 'warning' | 'critical';
  column?: string | null;
  message: string;
}

export interface DataQualityReport {
  duplicate_rows_count: number;
  total_missing_cells: number;
  missing_cells_percentage: number;
  flags: QualityFlag[];
}

export interface DataProfile {
  session_id: string;
  dataset_name: string;
  row_count: number;
  column_count: number;
  columns: ColumnSummary[];
  preview_rows: Record<string, any>[];
  quality_report: DataQualityReport;
}

export interface SessionMetadata {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  csv_filename?: string | null;
  desc_filename?: string | null;
  row_count: number;
  column_count: number;
  dataset_description?: string;
}

export interface SessionDetail {
  metadata: SessionMetadata;
  profile?: DataProfile | null;
  message_count: number;
}
