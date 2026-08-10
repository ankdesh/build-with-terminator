"use client";

import React from "react";
import { Cloud, CloudRain, Sun, Wind, Droplets, MapPin, CheckCircle2, AlertCircle } from "lucide-react";
import type { WeatherToolResult } from "@/lib/http-tool-executor";

interface WeatherToolUIProps {
  args: { city?: string };
  result?: WeatherToolResult;
  status?: string;
}

export function WeatherToolUI({ args, result }: WeatherToolUIProps) {
  const city = result?.city || args.city || "Unknown City";
  const isLoading = !result;
  const isError = result && !result.success;

  const getWeatherIcon = (cond?: string) => {
    if (!cond) return <Sun className="w-8 h-8 text-amber-400 animate-pulse" />;
    const lower = cond.toLowerCase();
    if (lower.includes("rain") || lower.includes("drizzle")) return <CloudRain className="w-8 h-8 text-blue-400" />;
    if (lower.includes("cloud") || lower.includes("fog")) return <Cloud className="w-8 h-8 text-slate-300" />;
    return <Sun className="w-8 h-8 text-amber-400" />;
  };

  return (
    <div className="my-3 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-blue-950/60 border border-blue-500/20 p-5 shadow-xl backdrop-blur-md transition-all duration-300 hover:border-blue-500/40">
      {/* Header Badge */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80 mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Cloud className="w-4 h-4" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">External HTTP Tool</span>
          <span className="text-xs font-medium text-slate-400 px-2 py-0.5 rounded-full bg-slate-800/80 border border-slate-700/50">
            Open-Meteo REST API
          </span>
        </div>
        {isLoading ? (
          <div className="flex items-center space-x-2 text-xs text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>Fetching HTTP API...</span>
          </div>
        ) : isError ? (
          <div className="flex items-center space-x-1.5 text-xs text-rose-400">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>HTTP Request Error</span>
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
          <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-2" />
          <p className="text-xs text-slate-400">Sending HTTP GET request for weather in <strong className="text-white">{city}</strong>...</p>
        </div>
      )}

      {isError && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
          <p className="font-semibold">Weather API Error:</p>
          <p className="mt-1 font-mono text-slate-300">{result.error}</p>
        </div>
      )}

      {result && result.success && (
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-4">
            <div className="p-3 rounded-2xl bg-slate-800/60 border border-slate-700/40">
              {getWeatherIcon(result.weatherCondition)}
            </div>
            <div>
              <div className="flex items-center space-x-1.5 text-slate-200">
                <MapPin className="w-4 h-4 text-blue-400" />
                <h4 className="text-lg font-bold text-white">{result.city}</h4>
                {result.country && <span className="text-xs text-slate-400 font-medium">({result.country})</span>}
              </div>
              <p className="text-sm font-medium text-slate-300 mt-0.5">{result.weatherCondition}</p>
            </div>
          </div>

          <div className="flex items-baseline space-x-1">
            <span className="text-4xl font-extrabold text-white tracking-tight">
              {result.temperature !== undefined ? Math.round(result.temperature) : "--"}
            </span>
            <span className="text-lg font-bold text-blue-400">°C</span>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-3 md:pt-0 border-t md:border-t-0 md:border-l border-slate-800 md:pl-4">
            <div className="flex items-center space-x-2">
              <Droplets className="w-4 h-4 text-cyan-400" />
              <div>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Humidity</p>
                <p className="text-xs font-bold text-slate-200">{result.humidity ?? "--"}%</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Wind className="w-4 h-4 text-indigo-400" />
              <div>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">Wind</p>
                <p className="text-xs font-bold text-slate-200">{result.windSpeed ?? "--"} km/h</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
