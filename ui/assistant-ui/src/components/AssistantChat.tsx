"use client";

import React, { useState, useMemo } from "react";
import { AssistantRuntimeProvider, useLocalRuntime, useThread, useThreadRuntime, makeAssistantToolUI } from "@assistant-ui/react";
import { createLocalRuntimeAdapter } from "@/lib/chat-adapter";
import { WeatherToolUI } from "@/components/tools/WeatherToolUI";
import { CryptoToolUI } from "@/components/tools/CryptoToolUI";
import { WikiToolUI } from "@/components/tools/WikiToolUI";
import type { WeatherToolResult, CryptoToolResult, WikiToolResult } from "@/lib/http-tool-executor";
import { Send, Bot, User, Sparkles, Cloud, Coins, BookOpen, RefreshCw } from "lucide-react";

interface AssistantChatProps {
  userApiKey: string;
}

// Generative Tool UI Definitions
const WeatherTool = makeAssistantToolUI({
  toolName: "get_weather",
  render: function WeatherToolRender({ args, result }) {
    return <WeatherToolUI args={args as { city?: string }} result={result as WeatherToolResult | undefined} />;
  },
});

const CryptoTool = makeAssistantToolUI({
  toolName: "fetch_crypto_price",
  render: function CryptoToolRender({ args, result }) {
    return <CryptoToolUI args={args as { coin?: string }} result={result as CryptoToolResult | undefined} />;
  },
});

const WikiTool = makeAssistantToolUI({
  toolName: "fetch_wiki_summary",
  render: function WikiToolRender({ args, result }) {
    return <WikiToolUI args={args as { topic?: string }} result={result as WikiToolResult | undefined} />;
  },
});

function ChatView() {
  const thread = useThread();
  const threadRuntime = useThreadRuntime();
  const [inputValue, setInputValue] = useState("");

  const handleSend = (overrideText?: string) => {
    const text = overrideText || inputValue;
    if (!text.trim()) return;
    threadRuntime.append({
      role: "user",
      content: [{ type: "text", text }],
    });
    setInputValue("");
  };

  const samplePrompts = [
    { label: "Tokyo Weather", icon: Cloud, prompt: "What is the current weather in Tokyo?" },
    { label: "Bitcoin Price", icon: Coins, prompt: "What is the live price of Bitcoin and Ethereum?" },
    { label: "Quantum Computing", icon: BookOpen, prompt: "Fetch a summary of Quantum computing from Wikipedia." },
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-4.5rem)] max-w-4xl mx-auto px-4 py-4">
      {/* Tool UI Components */}
      <WeatherTool />
      <CryptoTool />
      <WikiTool />

      {/* Prompt Suggestions */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 mr-1">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>Quick External HTTP Tools:</span>
        </span>
        {samplePrompts.map((p, idx) => {
          const Icon = p.icon;
          return (
            <button
              key={idx}
              onClick={() => handleSend(p.prompt)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-indigo-600/20 border border-slate-800 hover:border-indigo-500/40 text-xs font-medium text-slate-300 hover:text-indigo-300 transition-all shadow-sm cursor-pointer"
            >
              <Icon className="w-3.5 h-3.5 text-indigo-400" />
              <span>{p.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Chat Thread Box */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4 rounded-3xl border border-slate-800 bg-slate-950/60 shadow-2xl backdrop-blur-xl custom-scrollbar">
        {thread.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-8 rounded-3xl border border-dashed border-slate-800/80 bg-slate-900/20">
            <div className="p-4 rounded-3xl bg-indigo-600/10 text-indigo-400 border border-indigo-500/20 mb-4">
              <Bot className="w-10 h-10" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">LocalRuntime & External HTTP Tools</h3>
            <p className="text-xs text-slate-400 max-w-md mb-6 leading-relaxed">
              Ask anything or click a sample prompt to invoke external REST APIs (Open-Meteo, CoinGecko, Wikipedia) with real-time UI tool rendering.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-lg">
              {samplePrompts.map((p, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(p.prompt)}
                  className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-left transition-all group"
                >
                  <p className="text-xs font-bold text-white mb-1 group-hover:text-indigo-300 transition-colors">
                    {p.label}
                  </p>
                  <p className="text-[11px] text-slate-400 line-clamp-2">{p.prompt}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          thread.messages.map((msg, index) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id || index}
                className={`flex items-start space-x-3 ${isUser ? "flex-row-reverse space-x-reverse" : ""}`}
              >
                {/* Avatar */}
                <div
                  className={`p-2.5 rounded-2xl shrink-0 shadow-md ${
                    isUser
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-900 border border-slate-800 text-indigo-400"
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Bubble */}
                <div
                  className={`max-w-[85%] rounded-3xl p-4 shadow-lg ${
                    isUser
                      ? "bg-indigo-600/90 text-white rounded-tr-sm"
                      : "bg-slate-900/90 border border-slate-800/80 text-slate-200 rounded-tl-sm"
                  }`}
                >
                  {Array.isArray(msg.content) ? (
                    msg.content.map((part, pIdx) => {
                      if (part.type === "text") {
                        return (
                          <div key={pIdx} className="text-sm whitespace-pre-wrap leading-relaxed">
                            {part.text}
                          </div>
                        );
                      }
                      if (part.type === "tool-call") {
                        const { toolName, args, result } = part as {
                          toolName: string;
                          args: Record<string, unknown>;
                          result?: unknown;
                        };
                        if (toolName === "get_weather") {
                          return <WeatherToolUI key={pIdx} args={args} result={result as WeatherToolResult | undefined} />;
                        }
                        if (toolName === "fetch_crypto_price") {
                          return <CryptoToolUI key={pIdx} args={args} result={result as CryptoToolResult | undefined} />;
                        }
                        if (toolName === "fetch_wiki_summary") {
                          return <WikiToolUI key={pIdx} args={args} result={result as WikiToolResult | undefined} />;
                        }
                        return (
                          <div key={pIdx} className="my-2 p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-400">
                            Tool Call [{toolName}]: {JSON.stringify(args)}
                          </div>
                        );
                      }
                      return null;
                    })
                  ) : (
                    <div className="text-sm whitespace-pre-wrap leading-relaxed">
                      {String(msg.content)}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {thread.isRunning && (
          <div className="flex items-center space-x-2 text-xs text-indigo-400 p-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>LocalRuntime running ChatModelAdapter and HTTP tools loop...</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="mt-3 flex gap-2"
      >
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask a question or request weather, crypto, wikipedia..."
          className="flex-1 bg-slate-900/90 border border-slate-800 hover:border-slate-700 focus:border-indigo-500 rounded-2xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none transition-all shadow-inner"
        />
        <button
          type="submit"
          disabled={!inputValue.trim() || thread.isRunning}
          className="px-5 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-2xl font-semibold shadow-lg shadow-indigo-500/20 transition-all flex items-center justify-center cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

export function AssistantChat({ userApiKey }: AssistantChatProps) {
  const adapter = useMemo(() => createLocalRuntimeAdapter(() => userApiKey), [userApiKey]);
  const runtime = useLocalRuntime(adapter);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatView />
    </AssistantRuntimeProvider>
  );
}
