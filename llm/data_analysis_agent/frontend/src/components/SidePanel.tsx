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
  activeResult: ExecutionResult | null;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  isOpen,
  onClose,
  selectedMessage,
  activePlan,
  activeResult,
}) => {
  const [copied, setCopied] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'plan' | 'code' | 'logs'>('plan');

  if (!isOpen) return null;

  // Use either the streaming live plan/result or the selected message's artifacts
  const plan = activePlan || selectedMessage?.plan || selectedMessage?.execution_result?.plan || '';
  const result = activeResult || selectedMessage?.execution_result;
  const code = result?.code || '';
  const stdout = result?.stdout || '';

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

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 px-3 bg-white text-xs">
        <button
          onClick={() => setActiveTab('plan')}
          className={`py-2 px-3 border-b-2 font-medium flex items-center space-x-1.5 transition-colors ${
            activeTab === 'plan'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <ListOrdered className="w-3.5 h-3.5" />
          <span>Plan & Steps</span>
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
          <span>Python Code</span>
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
          <div className="space-y-3">
            {/* Standard Output Console */}
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1.5 flex items-center space-x-1">
                <Terminal className="w-3.5 h-3.5" />
                <span>Captured stdout</span>
              </span>
              <pre className="p-3 bg-slate-950 text-emerald-400 rounded-lg font-mono text-[11px] overflow-x-auto min-h-[140px] border border-slate-800 select-text">
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
