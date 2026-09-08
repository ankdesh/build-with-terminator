import React from 'react';
import {
  Clock,
  FileSpreadsheet,
  MessageSquare,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import { SessionMetadata } from '../lib/types';

interface SessionSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: SessionMetadata[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
}

export const SessionSidebar: React.FC<SessionSidebarProps> = ({
  isOpen,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}) => {
  if (!isOpen) return null;

  return (
    <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0 h-full select-none z-10">
      {/* Sidebar Header */}
      <div className="p-3 border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Sessions
        </span>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100"
          title="Close sidebar"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* New Session Button */}
      <div className="p-3">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center space-x-1.5 py-2 px-3 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-md transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>New Session</span>
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {sessions.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            No past sessions.
          </div>
        ) : (
          sessions.map((s) => {
            const isActive = s.session_id === activeSessionId;
            return (
              <div
                key={s.session_id}
                onClick={() => onSelectSession(s.session_id)}
                className={`group relative flex flex-col p-2.5 rounded-lg text-left cursor-pointer transition-all border ${
                  isActive
                    ? 'bg-blue-50/70 border-blue-200 text-blue-950 shadow-xs'
                    : 'border-transparent hover:bg-slate-50 hover:border-slate-200 text-slate-700'
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-xs font-medium truncate pr-4 text-slate-800">
                    {s.title}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm('Delete this session and all its stored files?')) {
                        onDeleteSession(s.session_id);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 p-1 rounded transition-opacity"
                    title="Delete session"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="mt-1 flex items-center space-x-2 text-[11px] text-slate-500">
                  {s.csv_filename ? (
                    <span className="flex items-center space-x-1 truncate max-w-[130px]">
                      <FileSpreadsheet className="w-3 h-3 text-blue-500 shrink-0" />
                      <span className="truncate">{s.csv_filename}</span>
                    </span>
                  ) : (
                    <span className="flex items-center space-x-1">
                      <MessageSquare className="w-3 h-3 text-slate-400" />
                      <span>Empty</span>
                    </span>
                  )}
                  <span>•</span>
                  <span className="flex items-center space-x-1 shrink-0">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span>{new Date(s.updated_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
