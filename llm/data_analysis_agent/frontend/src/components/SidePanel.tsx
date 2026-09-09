import React, { useState } from 'react';
import {
  Check,
  Code2,
  Copy,
  FileTerminal,
  ListOrdered,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react';
import { ChatMessage, ExecutionResult } from '../lib/types';

interface SidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  selectedMessage: ChatMessage | null;
  activePlan: string | null;
  activeLogs?: string[];
  activeResult: ExecutionResult | null;
  isStreaming?: boolean;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  isOpen,
  onClose,
  selectedMessage,
  activePlan,
  activeLogs,
  activeResult,
  isStreaming,
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'plan' | 'code' | 'logs'>('plan');

  if (!isOpen) return null;

  // Use either the streaming live plan/result or the selected message's artifacts
  const plan = activePlan || selectedMessage?.plan || selectedMessage?.execution_result?.plan || '';
  const result = activeResult || selectedMessage?.execution_result;
  const code = result?.code || '';
  const stdout = result?.stdout || '';
  const logs = (activeLogs && activeLogs.length > 0)
    ? activeLogs
    : (result?.step_logs || []);

  const handleCopyCode = () => {
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <aside className="w-80 md:w-96 border-l border-slate-200 bg-white flex flex-col shrink-0 h-full select-none z-10">
      {/* Panel Header */}
      <div className="p-3 border-b border-slate-200 flex items-center justify-between bg-slate-50/60">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-blue-600" />
          <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
            Analysis Reasoning & Steps
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors"
          title="Close reasoning panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs Header */}
      <div className="flex border-b border-slate-200 px-4 bg-slate-50/40 text-xs">
        <button
          onClick={() => setActiveTab('plan')}
          className={`py-2 px-3 border-b-2 font-medium flex items-center space-x-1.5 transition-colors ${
            activeTab === 'plan'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Plan</span>
        </button>

        <button
          onClick={() => setActiveTab('code')}
          className={`py-2 px-3 border-b-2 font-medium flex items-center space-x-1.5 transition-colors ${
            activeTab === 'code'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>Code</span>
        </button>

        <button
          onClick={() => setActiveTab('logs')}
          className={`py-2 px-3 border-b-2 font-medium flex items-center space-x-1.5 transition-colors ${
            activeTab === 'logs'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <FileTerminal className="w-3.5 h-3.5" />
          <span>Logs</span>
          {logs.length > 0 && (
            <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[9px] font-mono ${
              activeTab === 'logs' ? 'bg-blue-100 text-blue-700 font-bold' : 'bg-slate-100 text-slate-600'
            }`}>
              {logs.length}
            </span>
          )}
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {/* TAB 1: PLAN */}
        {activeTab === 'plan' && (
          <div className="space-y-3">
            <div className="p-3 bg-blue-50/50 border border-blue-100 rounded-lg">
              <span className="text-[10px] uppercase font-bold text-blue-600 block mb-1">
                Plain-English Execution Plan
              </span>
              {plan ? (
                <div className="text-slate-700 leading-relaxed whitespace-pre-line text-xs font-normal">
                  {plan}
                </div>
              ) : (
                <p className="text-slate-400 italic">No plan recorded for this turn.</p>
              )}
            </div>

            {result?.explanation && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">
                  How It Was Calculated
                </span>
                <p className="text-slate-700 leading-relaxed text-xs">
                  {result.explanation}
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: CODE */}
        {activeTab === 'code' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 font-mono text-[11px]">pandas / numpy script</span>
              <button
                onClick={handleCopyCode}
                disabled={!code}
                className="flex items-center space-x-1 px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px] transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-600" />
                    <span className="text-emerald-600 font-medium">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            {code ? (
              <pre className="p-3 bg-slate-900 text-slate-100 rounded-lg font-mono text-[11px] overflow-x-auto leading-relaxed select-text border border-slate-800">
                <code>{code}</code>
              </pre>
            ) : (
              <div className="p-8 text-center text-slate-400 border border-dashed border-slate-200 rounded-lg">
                No code generated yet.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: LOGS */}
        {activeTab === 'logs' && (
          <div className="space-y-4">
            {/* Step-by-Step Diagnostic Stream */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center space-x-1">
                  <FileTerminal className="w-3.5 h-3.5" />
                  <span>Step Execution & LLM Output</span>
                </span>
                {isStreaming && (
                  <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] bg-blue-50 text-blue-600 font-medium animate-pulse">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                    <span>Streaming</span>
                  </span>
                )}
              </div>

              {logs && logs.length > 0 ? (
                <div className="p-3 bg-slate-950 text-slate-200 rounded-lg font-mono text-[11px] overflow-x-auto max-h-[260px] border border-slate-800 space-y-1.5 select-text">
                  {logs.map((logEntry, idx) => {
                    const isError = logEntry.includes('[ERROR]') || logEntry.includes('[FATAL]');
                    const isWarning = logEntry.includes('[WARNING]') || logEntry.includes('[Self-Correction]');
                    const isSuccess = logEntry.includes('succeeded') || logEntry.includes('complete');
                    const colorClass = isError
                      ? 'text-red-400 font-semibold'
                      : isWarning
                      ? 'text-amber-400'
                      : isSuccess
                      ? 'text-emerald-400'
                      : 'text-slate-300';
                    return (
                      <div key={idx} className={`leading-relaxed whitespace-pre-wrap ${colorClass}`}>
                        {logEntry}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-4 bg-slate-900 text-slate-400 rounded-lg font-mono text-[11px] border border-slate-800 text-center italic">
                  {isStreaming ? 'Waiting for first execution step...' : '// No step logs recorded.'}
                </div>
              )}
            </div>

            {/* Standard Output Console */}
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1.5 flex items-center space-x-1">
                <Terminal className="w-3.5 h-3.5" />
                <span>Captured stdout</span>
              </span>
              <pre className="p-3 bg-slate-950 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto min-h-[80px] max-h-[180px] border border-slate-800 select-text">
                {stdout || '// No standard output printed.'}
              </pre>
            </div>

            {/* Error Traceback (if failed) */}
            {result?.error_traceback && (
              <div>
                <span className="text-[10px] uppercase font-bold text-red-600 block mb-1">
                  Traceback
                </span>
                <pre className="p-3 bg-red-950/40 text-red-300 rounded-lg font-mono text-[10px] overflow-x-auto border border-red-900 select-text">
                  {result.error_traceback}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
