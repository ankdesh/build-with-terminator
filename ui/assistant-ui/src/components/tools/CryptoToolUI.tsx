"use client";

import React from "react";
import { TrendingUp, TrendingDown, DollarSign, CheckCircle2, AlertCircle, Coins } from "lucide-react";
import type { CryptoToolResult } from "@/lib/http-tool-executor";

interface CryptoToolUIProps {
  args: { coin?: string };
  result?: CryptoToolResult;
}

export function CryptoToolUI({ args, result }: CryptoToolUIProps) {
  const coin = result?.symbol || args.coin?.toUpperCase() || "CRYPTO";
  const isLoading = !result;
  const isError = result && !result.success;

  const isPositive = (result?.change24h ?? 0) >= 0;

  return (
    <div className="my-3 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-emerald-950/50 border border-emerald-500/20 p-5 shadow-xl backdrop-blur-md transition-all duration-300 hover:border-emerald-500/40">
      {/* Header Badge */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Coins className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">External HTTP Tool</span>
          <span className="text-xs font-medium text-slate-400 px-2 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/50">
            CoinGecko REST API
          </span>
        </div>
        {isLoading ? (
          <div className="flex items-center space-x-2 text-xs text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>Fetching Price...</span>
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
          <div className="inline-block w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mb-2" />
          <p className="text-xs text-slate-400">Requesting market data for <strong className="text-white">{coin}</strong> via HTTP API...</p>
        </div>
      )}

      {isError && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
          <p className="font-semibold">Crypto API Error:</p>
          <p className="mt-1 font-mono text-slate-300">{result.error}</p>
        </div>
      )}

      {result && result.success && (
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <DollarSign className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-lg font-bold text-white tracking-wide">{result.symbol}</h4>
              <p className="text-xs text-slate-400">Updated: {result.lastUpdated}</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">USD Price</p>
              <p className="text-2xl font-extrabold text-white tracking-tight">
                ${result.priceUsd ? result.priceUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : "--"}
              </p>
            </div>

            {result.change24h !== undefined && (
              <div
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-xl border text-xs font-bold ${
                  isPositive
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-400"
                }`}
              >
                {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                <span>{result.change24h.toFixed(2)}%</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
