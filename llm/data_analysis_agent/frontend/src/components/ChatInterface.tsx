import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Code2,
  FileSpreadsheet,
  Loader2,
  Send,
  Sparkles,
  Square,
  User,
} from 'lucide-react';
import { ChatMessage, ExecutionResult } from '../lib/types';
import { ChartViewer } from './ChartViewer';
import { DataTableViewer } from './DataTableViewer';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  streamingStatus: string | null;
  streamingPlan: string | null;
  streamingToken: string;
  streamingResult: ExecutionResult | null;
  isStreaming: boolean;
  onSendMessage: (query: string) => void;
  onSelectMessageForSidePanel: (msg: ChatMessage) => void;
  hasDataset: boolean;
  onOpenUpload: () => void;
  onExportCsv?: (columns: string[], rows: any[]) => void;
  onCancelOperation?: () => void;
}

const QUICK_PROMPTS = [
  'Show average energy consumption by building zone',
  'What was the highest peak demand hour and temperature?',
  'Plot hourly energy usage trend over time',
  'Check for any unusual energy consumption spikes or outliers',
];

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  streamingStatus,
  streamingPlan,
  streamingToken,
  streamingResult,
  isStreaming,
  onSendMessage,
  onSelectMessageForSidePanel,
  hasDataset,
  onOpenUpload,
  onExportCsv,
  onCancelOperation,
}) => {
  const [inputQuery, setInputQuery] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingToken, streamingStatus, streamingPlan]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isStreaming) return;
    onSendMessage(inputQuery.trim());
    setInputQuery('');
  };

  const handleQuickPrompt = (prompt: string) => {
    if (isStreaming) return;
    onSendMessage(prompt);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/30">
      {/* Messages Thread Container */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6">
        {/* Welcome Empty State if no messages */}
        {messages.length === 0 && !isStreaming && (
          <div className="max-w-xl mx-auto py-12 text-center space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-600 text-white flex items-center justify-center mx-auto shadow-md">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Welcome to WPS-AI</h2>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                Ask questions in plain English. WPS-AI will formulate a plan, run Python pandas code,
                and present clean explanations with interactive charts and tables.
              </p>
            </div>

            {!hasDataset ? (
              <div className="pt-4">
                <button
                  onClick={onOpenUpload}
                  className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
                >
                  <FileSpreadsheet className="w-4 h-4" />
                  <span>Upload CSV to Begin</span>
                </button>
              </div>
            ) : (
              <div className="pt-4 text-left">
                <span className="text-[11px] uppercase font-semibold text-slate-400 block mb-2 text-center">
                  Suggested Queries
                </span>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {QUICK_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleQuickPrompt(prompt)}
                      className="p-2.5 bg-white hover:bg-blue-50/60 border border-slate-200 hover:border-blue-200 rounded-lg text-xs text-slate-700 text-left transition-colors flex items-center justify-between group shadow-2xs"
                    >
                      <span className="pr-2">{prompt}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Rendered Past Messages */}
        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const exec = msg.execution_result;

          return (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 w-full max-w-3xl ${
                isUser ? 'ml-auto flex-row-reverse space-x-reverse max-w-xl' : 'mr-auto'
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-white text-xs shadow-xs ${
                  isUser ? 'bg-slate-800' : 'bg-blue-600'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Content Bubble */}
              <div
                className={`flex-1 min-w-0 overflow-hidden ${
                  isUser
                    ? 'bg-blue-600 text-white rounded-2xl rounded-tr-xs px-4 py-2.5 text-xs shadow-xs'
                    : 'bg-white border border-slate-200/90 rounded-2xl rounded-tl-xs p-4 text-xs shadow-xs text-slate-800'
                }`}
              >
                {/* Assistant Plan Pill */}
                {!isUser && msg.plan && (
                  <div className="mb-2.5 p-2 bg-blue-50/60 border border-blue-100 rounded-lg text-[11px] text-blue-900">
                    <span className="font-semibold text-blue-700 block mb-0.5">Plan of Action:</span>
                    <p className="leading-relaxed">{msg.plan}</p>
                  </div>
                )}

                {/* Main Content / Explanation */}
                <div className="leading-relaxed whitespace-pre-wrap">{msg.content}</div>

                {/* Inline Chart */}
                {!isUser && exec?.chart && (
                  <div className="mt-3">
                    <ChartViewer spec={exec.chart} />
                  </div>
                )}

                {/* Inline Data Table */}
                {!isUser && exec?.table && (
                  <div className="mt-3">
                    <DataTableViewer
                      table={exec.table}
                      onExportCsv={() => onExportCsv?.(exec.table!.columns, exec.table!.rows)}
                    />
                  </div>
                )}

                {/* Inspect Reasoning Footer */}
                {!isUser && exec && (
                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                    <button
                      onClick={() => onSelectMessageForSidePanel(msg)}
                      className="flex items-center space-x-1.5 text-blue-600 hover:text-blue-800 font-medium transition-colors"
                    >
                      <Code2 className="w-3.5 h-3.5" />
                      <span>Inspect Plan & Code ({exec.execution_time_ms} ms)</span>
                    </button>

                    {exec.retries_attempted > 0 && (
                      <span className="text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-100 text-[10px]">
                        Self-corrected ({exec.retries_attempted} retries)
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Live Streaming Assistant Message */}
        {isStreaming && (
          <div className="flex items-start space-x-3 w-full max-w-3xl mr-auto">
            <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-blue-600 text-white text-xs shadow-xs">
              <Bot className="w-4 h-4" />
            </div>

            <div className="flex-1 min-w-0 bg-white border border-slate-200 rounded-2xl rounded-tl-xs p-4 text-xs shadow-xs text-slate-800 space-y-3">
              {/* Streaming Status Indicator & Cancel Button */}
              {streamingStatus && (
                <div className="flex items-center justify-between text-blue-600 font-medium bg-blue-50/70 p-2.5 rounded-lg border border-blue-100">
                  <div className="flex items-center space-x-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                    <span>{streamingStatus}</span>
                  </div>
                  {onCancelOperation && (
                    <button
                      type="button"
                      onClick={onCancelOperation}
                      className="px-2.5 py-1 text-[11px] font-semibold text-red-600 hover:text-red-700 bg-white hover:bg-red-50 border border-red-200 rounded-md transition-colors shadow-2xs flex items-center space-x-1"
                      title="Cancel current operation"
                    >
                      <Square className="w-3 h-3 fill-current" />
                      <span>Cancel</span>
                    </button>
                  )}
                </div>
              )}

              {/* Streaming Plan */}
              {streamingPlan && (
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-700">
                  <span className="font-semibold text-slate-800 block mb-0.5">Plan of Action:</span>
                  <p className="leading-relaxed whitespace-pre-wrap">{streamingPlan}</p>
                </div>
              )}

              {/* Streaming Execution Visuals */}
              {streamingResult?.chart && (
                <div>
                  <ChartViewer spec={streamingResult.chart} />
                </div>
              )}

              {streamingResult?.table && (
                <div>
                  <DataTableViewer
                    table={streamingResult.table}
                    onExportCsv={() =>
                      onExportCsv?.(streamingResult.table!.columns, streamingResult.table!.rows)
                    }
                  />
                </div>
              )}

              {/* Streaming Explanation Text */}
              {streamingToken && (
                <div className="leading-relaxed whitespace-pre-wrap text-slate-800">
                  {streamingToken}
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Composer */}
      <div className="p-4 bg-white border-t border-slate-200 shrink-0">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative flex items-center">
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={!hasDataset || isStreaming}
            placeholder={
              hasDataset
                ? 'Ask a question in plain English (e.g. "What was the average energy usage by zone?")...'
                : 'Please upload a CSV dataset to begin asking questions...'
            }
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:bg-slate-100 disabled:cursor-not-allowed shadow-2xs"
          />

          {isStreaming ? (
            <button
              type="button"
              onClick={onCancelOperation}
              className="absolute right-2 p-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors shadow-2xs flex items-center justify-center"
              title="Stop current operation"
            >
              <Square className="w-4 h-4 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputQuery.trim() || !hasDataset}
              className="absolute right-2 p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition-colors shadow-2xs"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </form>
        <p className="text-[10px] text-slate-400 text-center mt-2">
          Air-gapped Python execution engine with automated self-correcting retries.
        </p>
      </div>
    </div>
  );
};
