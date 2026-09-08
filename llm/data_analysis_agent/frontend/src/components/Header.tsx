import React from 'react';
import {
  BarChart3,
  Database,
  FileSpreadsheet,
  PlusCircle,
  SidebarClose,
  SidebarOpen,
  Upload,
} from 'lucide-react';
import { SessionMetadata } from '../lib/types';

interface HeaderProps {
  session: SessionMetadata | null;
  sidePanelOpen: boolean;
  onToggleSidePanel: () => void;
  onOpenUpload: () => void;
  onNewSession: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  session,
  sidePanelOpen,
  onToggleSidePanel,
  onOpenUpload,
  onNewSession,
}) => {
  const hasData = session && session.row_count > 0 && session.csv_filename;

  return (
    <header className="h-14 border-b border-slate-200 bg-white px-4 flex items-center justify-between shrink-0 select-none">
      {/* Brand & Identity */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 text-white shadow-sm">
          <BarChart3 className="w-5 h-5" />
        </div>
        <div className="flex items-center space-x-2">
          <span className="font-bold text-lg text-slate-800 tracking-tight">WPS-AI</span>
          <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-medium border border-slate-200">
            Air-Gapped Edition
          </span>
        </div>
      </div>

      {/* Dataset Info Indicator */}
      <div className="flex items-center space-x-3">
        {hasData ? (
          <div className="flex items-center space-x-2 bg-blue-50/70 border border-blue-200/80 px-3 py-1 rounded-full text-xs text-blue-900">
            <FileSpreadsheet className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-medium truncate max-w-[200px]">{session.csv_filename}</span>
            <span className="text-blue-400">•</span>
            <span>{session.row_count.toLocaleString()} rows</span>
            <span className="text-blue-400">•</span>
            <span>{session.column_count} cols</span>
          </div>
        ) : (
          <div className="flex items-center space-x-2 bg-slate-100 px-3 py-1 rounded-full text-xs text-slate-500 border border-slate-200">
            <Database className="w-3.5 h-3.5" />
            <span>No dataset loaded</span>
          </div>
        )}
      </div>

      {/* Action Controls */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onOpenUpload}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-50 hover:border-slate-400 transition-colors shadow-sm"
        >
          <Upload className="w-3.5 h-3.5 text-slate-600" />
          <span>{hasData ? 'Switch Data' : 'Upload Data'}</span>
        </button>

        <button
          onClick={onNewSession}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors shadow-sm"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>New Session</span>
        </button>

        <div className="h-5 w-px bg-slate-200 mx-1" />

        <button
          onClick={onToggleSidePanel}
          title={sidePanelOpen ? 'Collapse side reasoning panel' : 'Expand side reasoning panel'}
          className={`p-1.5 rounded-md border transition-colors ${
            sidePanelOpen
              ? 'bg-blue-50 border-blue-300 text-blue-700'
              : 'bg-white border-slate-300 text-slate-600 hover:bg-slate-50'
          }`}
        >
          {sidePanelOpen ? (
            <SidebarClose className="w-4 h-4" />
          ) : (
            <SidebarOpen className="w-4 h-4" />
          )}
        </button>
      </div>
    </header>
  );
};
