import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Columns,
  Eye,
  Info,
  Layers,
  ShieldAlert,
  Table,
} from 'lucide-react';
import { DataProfile } from '../lib/types';

interface DataProfileCardProps {
  profile: DataProfile;
}

export const DataProfileCard: React.FC<DataProfileCardProps> = ({ profile }) => {
  const [showQualityReport, setShowQualityReport] = useState<boolean>(true);
  const [showPreviewTable, setShowPreviewTable] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  const qualityFlags = profile.quality_report.flags || [];
  const hasWarnings = qualityFlags.some((f) => f.severity === 'warning' || f.severity === 'critical');

  return (
    <div className="border border-slate-200 bg-white rounded-xl shadow-xs overflow-hidden mb-4">
      {/* Card Header Bar */}
      <div className="px-4 py-3 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-blue-100 rounded-lg text-blue-700">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-semibold text-slate-800 flex items-center space-x-2">
              <span>Dataset Profile:</span>
              <span className="font-mono text-blue-600">{profile.dataset_name}</span>
            </h3>
            <p className="text-[11px] text-slate-500">
              {profile.row_count.toLocaleString()} rows • {profile.column_count} columns
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Data Quality Toggle Button */}
          <button
            onClick={() => setShowQualityReport(!showQualityReport)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
              showQualityReport
                ? 'bg-amber-50 border-amber-200 text-amber-800'
                : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {hasWarnings ? (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            ) : (
              <ShieldAlert className="w-3.5 h-3.5 text-slate-500" />
            )}
            <span>Quality Report ({qualityFlags.length})</span>
          </button>

          {/* Expand/Collapse Full Profile */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-200/50"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* High-level summary metrics */}
          <div className="grid grid-cols-4 gap-3">
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Total Rows</span>
              <p className="text-base font-bold text-slate-800">{profile.row_count.toLocaleString()}</p>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Columns</span>
              <p className="text-base font-bold text-slate-800">{profile.column_count}</p>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Missing Cells</span>
              <p className="text-base font-bold text-slate-800">
                {profile.quality_report.missing_cells_percentage}%
              </p>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
              <span className="text-[10px] uppercase font-semibold text-slate-400">Duplicates</span>
              <p className="text-base font-bold text-slate-800">
                {profile.quality_report.duplicate_rows_count}
              </p>
            </div>
          </div>

          {/* Toggleable Data Quality & Assumptions Section */}
          {showQualityReport && (
            <div className="p-3 bg-amber-50/50 border border-amber-200/70 rounded-lg space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-amber-900">
                  <ShieldAlert className="w-4 h-4 text-amber-700" />
                  <span>Data Quality Checks & Analysis Assumptions</span>
                </div>
                <span className="text-[10px] text-amber-700 font-medium">Toggleable view</span>
              </div>

              {qualityFlags.length === 0 ? (
                <div className="flex items-center space-x-1.5 text-xs text-emerald-700 py-1">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                  <span>No data quality issues or anomalies detected. Dataset is clean.</span>
                </div>
              ) : (
                <ul className="space-y-1.5 text-xs text-slate-700">
                  {qualityFlags.map((flag, idx) => (
                    <li
                      key={idx}
                      className="flex items-start space-x-2 bg-white/80 p-2 rounded-md border border-amber-100"
                    >
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-sm shrink-0 mt-0.5 ${
                          flag.severity === 'critical'
                            ? 'bg-red-100 text-red-700'
                            : flag.severity === 'warning'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {flag.severity}
                      </span>
                      <span className="text-slate-700 leading-relaxed">{flag.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Column Breakdown Pills */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                <Columns className="w-3.5 h-3.5 text-slate-500" />
                <span>Columns & Schemas</span>
              </span>
              <button
                onClick={() => setShowPreviewTable(!showPreviewTable)}
                className="text-xs text-blue-600 hover:text-blue-800 flex items-center space-x-1"
              >
                <Table className="w-3.5 h-3.5" />
                <span>{showPreviewTable ? 'Hide Preview' : 'Show Sample Preview'}</span>
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {profile.columns.map((col) => (
                <div
                  key={col.name}
                  className="p-2 rounded-lg border border-slate-200/80 bg-white hover:border-slate-300 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-medium text-slate-800 truncate" title={col.name}>
                      {col.name}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded-sm font-mono">
                      {col.data_type}
                    </span>
                  </div>
                  {col.column_description ? (
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-2" title={col.column_description}>
                      {col.column_description}
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-400 mt-1 italic">No description</p>
                  )}
                  {col.mean_value !== undefined && col.mean_value !== null && (
                    <div className="mt-1 text-[10px] text-slate-500 flex items-center justify-between border-t border-slate-100 pt-1">
                      <span>Mean: {col.mean_value}</span>
                      <span>Range: [{col.min_value}, {col.max_value}]</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Sample Head Preview Table */}
          {showPreviewTable && profile.preview_rows.length > 0 && (
            <div className="mt-3 border border-slate-200 rounded-lg overflow-x-auto bg-slate-50/50">
              <div className="p-2 border-b border-slate-200 bg-white flex items-center space-x-2 text-xs font-semibold text-slate-700">
                <Eye className="w-3.5 h-3.5 text-slate-500" />
                <span>Sample Data Preview (First 5 Rows)</span>
              </div>
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-100/80 border-b border-slate-200 text-slate-600">
                    {profile.columns.map((c) => (
                      <th key={c.name} className="px-3 py-2 font-mono text-[11px]">
                        {c.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white font-mono text-[11px]">
                  {profile.preview_rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-slate-50">
                      {profile.columns.map((c) => (
                        <td key={c.name} className="px-3 py-1.5 whitespace-nowrap text-slate-700">
                          {row[c.name] !== null && row[c.name] !== undefined ? String(row[c.name]) : '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
