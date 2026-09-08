import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  FileCode,
  FileSpreadsheet,
  Loader2,
  Sparkles,
  Upload,
  X,
} from 'lucide-react';

interface FileUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (csvFile: File, descFile: File | null, descText: string) => Promise<void>;
  onLoadSample: () => Promise<void>;
}

export const FileUploadModal: React.FC<FileUploadModalProps> = ({
  isOpen,
  onClose,
  onUpload,
  onLoadSample,
}) => {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [descFile, setDescFile] = useState<File | null>(null);
  const [descText, setDescText] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSampleLoading, setIsSampleLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleCsvDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.csv')) {
        setCsvFile(file);
        setErrorMessage(null);
      } else {
        setErrorMessage('Please select a valid CSV file.');
      }
    }
  };

  const handleDescDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setDescFile(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      setErrorMessage('Please select a CSV file to upload.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      await onUpload(csvFile, descFile, descText);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload and profile dataset.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadSample = async () => {
    setIsSampleLoading(true);
    setErrorMessage(null);
    try {
      await onLoadSample();
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load sample dataset.');
    } finally {
      setIsSampleLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="bg-white border border-slate-200 rounded-xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Upload Dataset</h2>
            <p className="text-xs text-slate-500">Provide your CSV data and optional column descriptions</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* CSV File Input */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              1. CSV Data File <span className="text-red-500">*</span>
            </label>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleCsvDrop}
              className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
                csvFile
                  ? 'border-blue-300 bg-blue-50/40'
                  : 'border-slate-300 hover:border-blue-400 bg-slate-50/50'
              }`}
            >
              {csvFile ? (
                <div className="flex items-center justify-between text-left">
                  <div className="flex items-center space-x-2.5 overflow-hidden">
                    <FileSpreadsheet className="w-6 h-6 text-blue-600 shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-slate-800 truncate">{csvFile.name}</p>
                      <p className="text-[11px] text-slate-500">{(csvFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setCsvFile(null)}
                    className="text-slate-400 hover:text-red-500 p-1 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center py-2">
                  <Upload className="w-6 h-6 text-slate-400 mb-1.5" />
                  <p className="text-xs text-slate-600">
                    Drag and drop your CSV here, or{' '}
                    <label className="text-blue-600 hover:underline cursor-pointer font-medium">
                      browse
                      <input
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            setCsvFile(e.target.files[0]);
                            setErrorMessage(null);
                          }
                        }}
                      />
                    </label>
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1">Supports up to 100 MB (~1M rows)</p>
                </div>
              )}
            </div>
          </div>

          {/* Description File or Text */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              2. Column Descriptions (Optional)
            </label>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDescDrop}
              className={`border border-slate-200 rounded-lg p-3 bg-slate-50/40 mb-2 ${
                descFile ? 'border-blue-200 bg-blue-50/30' : ''
              }`}
            >
              {descFile ? (
                <div className="flex items-center justify-between text-left">
                  <div className="flex items-center space-x-2">
                    <FileCode className="w-5 h-5 text-blue-600" />
                    <div>
                      <p className="text-xs font-medium text-slate-800">{descFile.name}</p>
                      <p className="text-[10px] text-slate-400">Attached file</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setDescFile(null)}
                    className="text-slate-400 hover:text-red-500 text-xs"
                  >
                    Clear
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Attach .txt / .md description file</span>
                  <label className="text-xs text-blue-600 hover:underline cursor-pointer font-medium">
                    Select File
                    <input
                      type="file"
                      accept=".txt,.md"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setDescFile(e.target.files[0]);
                        }
                      }}
                    />
                  </label>
                </div>
              )}
            </div>

            {!descFile && (
              <textarea
                rows={3}
                value={descText}
                onChange={(e) => setDescText(e.target.value)}
                placeholder="Or paste column descriptions here:&#10;kwh: Total energy in kilowatt hours&#10;zone: Building department name..."
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-1 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400 font-mono"
              />
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-200">
            <button
              type="button"
              onClick={handleLoadSample}
              disabled={isSampleLoading || isLoading}
              className="flex items-center space-x-1.5 text-xs text-slate-600 hover:text-blue-700 py-1.5 px-2.5 rounded-md hover:bg-slate-100 transition-colors"
            >
              {isSampleLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              )}
              <span>Load Electric Usage Sample</span>
            </button>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading || !csvFile}
                className="flex items-center space-x-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm"
              >
                {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Profile & Load</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
