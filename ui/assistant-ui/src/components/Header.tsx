"use client";

import React, { useState } from "react";
import { Bot, Key, Sparkles, Server } from "lucide-react";

interface HeaderProps {
  userApiKey: string;
  setUserApiKey: (key: string) => void;
}

export function Header({ userApiKey, setUserApiKey }: HeaderProps) {
  const [showKeyInput, setShowKeyInput] = useState(false);

  return (
    <header className="sticky top-0 z-30 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl px-4 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        {/* Brand / Logo */}
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 shadow-lg shadow-indigo-500/25">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-base font-bold tracking-tight text-white">Assistant-UI LocalRuntime</h1>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                v0.11.58
              </span>
            </div>
            <p className="text-xs text-slate-400">External HTTP Tools & OpenAI Integration</p>
          </div>
        </div>

        {/* Status Indicators & Key Settings */}
        <div className="flex items-center space-x-3">
          {/* Runtime Badge */}
          <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300">
            <Server className="w-3.5 h-3.5 text-emerald-400" />
            <span>LocalRuntime</span>
          </div>

          {/* Model Badge */}
          <div className="hidden md:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>gpt-4o-mini</span>
          </div>

          {/* API Key Configure Button */}
          <button
            onClick={() => setShowKeyInput(!showKeyInput)}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 transition-colors text-xs font-semibold"
          >
            <Key className="w-3.5 h-3.5" />
            <span>{userApiKey ? "Custom Key Set" : "API Key Settings"}</span>
          </button>
        </div>
      </div>

      {/* Dynamic API Key Modal / Banner */}
      {showKeyInput && (
        <div className="mt-3 p-4 rounded-2xl bg-slate-900/90 border border-indigo-500/30 max-w-xl mx-auto shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-slate-200">
              <Key className="w-4 h-4 text-indigo-400" />
              <span>OpenAI API Key Configuration</span>
            </div>
            <button
              onClick={() => setShowKeyInput(false)}
              className="text-xs text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>
          <p className="text-xs text-slate-400 mb-3">
            The application checks for <code className="text-indigo-300 bg-slate-950 px-1 py-0.5 rounded">OPENAI_API_KEY</code> in environment variables (<code className="text-slate-300 font-mono">.env.local</code>). If not present, you can enter your key below:
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              placeholder="sk-..."
              value={userApiKey}
              onChange={(e) => setUserApiKey(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={() => setShowKeyInput(false)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              Save Key
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
