"use client";

import React from "react";
import { BookOpen, ExternalLink, CheckCircle2, AlertCircle, Sparkles } from "lucide-react";
import type { WikiToolResult } from "@/lib/http-tool-executor";

interface WikiToolUIProps {
  args: { topic?: string };
  result?: WikiToolResult;
}

export function WikiToolUI({ args, result }: WikiToolUIProps) {
  const topic = result?.title || args.topic || "Wikipedia Topic";
  const isLoading = !result;
  const isError = result && !result.success;

  return (
    <div className="my-3 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-purple-950/50 border border-purple-500/20 p-5 shadow-xl backdrop-blur-md transition-all duration-300 hover:border-purple-500/40">
      {/* Header Badge */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <BookOpen className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-purple-400">External HTTP Tool</span>
          <span className="text-xs font-medium text-slate-400 px-2 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/50">
            Wikipedia REST API
          </span>
        </div>
        {isLoading ? (
          <div className="flex items-center space-x-2 text-xs text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>Fetching Summary...</span>
          </div>
        ) : isError ? (
          <div className="flex items-center space-x-1.5 text-xs text-rose-400">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>HTTP Error</span>
          </div>
        ) : (
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>200 OK</span>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="py-4 text-center">
          <div className="inline-block w-6 h-6 border-2 border-purple-400 border-t-transparent rounded-full animate-spin mb-2" />
          <p className="text-xs text-slate-400">Requesting Wikipedia article summary for <strong className="text-white">{topic}</strong>...</p>
        </div>
      )}

      {isError && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
          <p className="font-semibold">Wikipedia API Error:</p>
          <p className="mt-1 font-mono text-slate-300">{result.error}</p>
        </div>
      )}

      {result && result.success && (
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <h4 className="text-base font-bold text-white tracking-wide">{result.title}</h4>
            </div>
            {result.contentUrl && (
              <a
                href={result.contentUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center space-x-1 text-xs text-purple-400 hover:text-purple-300 font-semibold hover:underline"
              >
                <span>Read Full</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>

          <div className="flex gap-4 items-start">
            {result.thumbnailUrl && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={result.thumbnailUrl}
                alt={result.title || "Thumbnail"}
                className="w-20 h-20 rounded-xl object-cover border border-slate-700/50 shadow-md shrink-0"
              />
            )}
            <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/40 p-3 rounded-xl border border-slate-800/80">
              {result.extract}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
