"use client";

import React, { useState } from "react";
import { Header } from "@/components/Header";
import { AssistantChat } from "@/components/AssistantChat";

export default function Home() {
  const [userApiKey, setUserApiKey] = useState("");

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 selection:bg-indigo-500 selection:text-white flex flex-col font-sans">
      <Header userApiKey={userApiKey} setUserApiKey={setUserApiKey} />
      <div className="flex-1">
        <AssistantChat userApiKey={userApiKey} />
      </div>
    </main>
  );
}
