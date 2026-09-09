import React, { useEffect, useRef, useState } from 'react';
import {
  createSession,
  deleteSession,
  exportCsv,
  getMessages,
  getSession,
  listSessions,
  streamChat,
  uploadDataset,
} from './lib/api';
import {
  ChatMessage,
  ExecutionResult,
  SessionDetail,
  SessionMetadata,
} from './lib/types';
import { Header } from './components/Header';
import { SessionSidebar } from './components/SessionSidebar';
import { FileUploadModal } from './components/FileUploadModal';
import { DataProfileCard } from './components/DataProfileCard';
import { SidePanel } from './components/SidePanel';
import { ChatInterface } from './components/ChatInterface';

export const App: React.FC = () => {
  const [sessions, setSessions] = useState<SessionMetadata[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // UI state
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(true);
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null);

  // Streaming state
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);
  const [streamingPlan, setStreamingPlan] = useState<string | null>(null);
  const [streamingLogs, setStreamingLogs] = useState<string[]>([]);
  const [streamingToken, setStreamingToken] = useState<string>('');
  const [streamingResult, setStreamingResult] = useState<ExecutionResult | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 1. Initial load
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const list = await listSessions();
      setSessions(list);
      if (list.length > 0) {
        selectSession(list[0].session_id);
      } else {
        handleNewSession();
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  const selectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    setSelectedMessage(null);
    try {
      const detail = await getSession(sessionId);
      setSessionDetail(detail);
      const msgs = await getMessages(sessionId);
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load session detail:', err);
    }
  };

  const handleNewSession = async () => {
    try {
      const newMeta = await createSession();
      setSessions((prev) => [newMeta, ...prev]);
      setActiveSessionId(newMeta.session_id);
      setSessionDetail({ metadata: newMeta, profile: null, message_count: 0 });
      setMessages([]);
      setSelectedMessage(null);
      // Automatically prompt upload modal for fresh session
      setIsUploadOpen(true);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      const remaining = sessions.filter((s) => s.session_id !== sessionId);
      setSessions(remaining);
      if (activeSessionId === sessionId) {
        if (remaining.length > 0) {
          selectSession(remaining[0].session_id);
        } else {
          handleNewSession();
        }
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleUpload = async (csvFile: File, descFile: File | null, descText: string) => {
    if (!activeSessionId) return;
    const updated = await uploadDataset(activeSessionId, csvFile, descFile, descText);
    setSessionDetail(updated);
    setSessions((prev) =>
      prev.map((s) => (s.session_id === activeSessionId ? updated.metadata : s))
    );
  };

  const handleLoadSample = async () => {
    if (!activeSessionId) return;

    // Load sample files from server
    const csvResp = await fetch('/sample_data/electric_usage.csv');
    if (!csvResp.ok) throw new Error('Could not fetch sample CSV');
    const csvBlob = await csvResp.blob();
    const csvFile = new File([csvBlob], 'electric_usage.csv', { type: 'text/csv' });

    const descResp = await fetch('/sample_data/electric_usage_desc.txt');
    let descText = '';
    if (descResp.ok) {
      descText = await descResp.text();
    }

    await handleUpload(csvFile, null, descText);
  };

  const handleSendMessage = async (query: string) => {
    if (!activeSessionId || isStreaming) return;

    // Optimistically add user message
    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Reset streaming states
    setIsStreaming(true);
    setStreamingStatus('Initializing query...');
    setStreamingPlan(null);
    setStreamingLogs([]);
    setStreamingToken('');
    setStreamingResult(null);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      await streamChat(
        activeSessionId,
        query,
        {
          onStatus: (status) => setStreamingStatus(status),
          onPlan: (plan) => setStreamingPlan(plan),
          onLog: (log) => setStreamingLogs((prev) => [...prev, log]),
          onToken: (tok) => setStreamingToken((prev) => prev + tok),
          onResult: (res) => {
            setStreamingResult(res);
            setSelectedMessage({
              id: 'live',
              role: 'assistant',
              content: res.explanation,
              plan: res.plan,
              execution_result: res,
            });
          },
          onError: (err) => {
            setStreamingStatus(`Error: ${err}`);
          },
          onDone: async () => {
            setIsStreaming(false);
            setStreamingStatus(null);
            // Reload full messages from session store
            const updatedMsgs = await getMessages(activeSessionId);
            setMessages(updatedMsgs);
            if (updatedMsgs.length > 0) {
              setSelectedMessage(updatedMsgs[updatedMsgs.length - 1]);
            }
          },
        },
        abortController.signal
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Chat operation cancelled by user');
        setIsStreaming(false);
        setStreamingStatus(null);
        return;
      }
      console.error('Chat error:', err);
      setIsStreaming(false);
      setStreamingStatus(`Error: ${err.message || err}`);
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleCancelOperation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setStreamingStatus(null);
  };

  const handleExportCsv = async (columns: string[], rows: any[]) => {
    if (!activeSessionId) return;
    try {
      await exportCsv(activeSessionId, columns, rows);
    } catch (err) {
      console.error('Failed to export CSV:', err);
    }
  };

  const hasDataset = Boolean(sessionDetail?.metadata.csv_filename && sessionDetail?.profile);

  return (
    <div className="h-screen flex flex-col bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* Top Header */}
      <Header
        session={sessionDetail?.metadata || null}
        sidePanelOpen={isSidePanelOpen}
        onToggleSidePanel={() => setIsSidePanelOpen(!isSidePanelOpen)}
        onOpenUpload={() => setIsUploadOpen(true)}
        onNewSession={handleNewSession}
      />

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sessions Sidebar */}
        <SessionSidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={selectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
        />

        {/* Center Chat & Data Profiling Area */}
        <main className="flex-1 flex flex-col h-full overflow-hidden">
          {/* Data Profile Card if dataset loaded */}
          {sessionDetail?.profile && (
            <div className="px-4 md:px-8 pt-4 pb-0 shrink-0">
              <DataProfileCard profile={sessionDetail.profile} />
            </div>
          )}

          {/* Assistant Chat Interface */}
          <ChatInterface
            messages={messages}
            streamingStatus={streamingStatus}
            streamingPlan={streamingPlan}
            streamingToken={streamingToken}
            streamingResult={streamingResult}
            isStreaming={isStreaming}
            onSendMessage={handleSendMessage}
            onSelectMessageForSidePanel={(msg) => {
              setSelectedMessage(msg);
              if (!isSidePanelOpen) setIsSidePanelOpen(true);
            }}
            hasDataset={hasDataset}
            onOpenUpload={() => setIsUploadOpen(true)}
            onExportCsv={handleExportCsv}
            onCancelOperation={handleCancelOperation}
          />
        </main>

        {/* Right Side Panel for Reasoning & Code Inspection */}
        <SidePanel
          isOpen={isSidePanelOpen}
          onClose={() => setIsSidePanelOpen(false)}
          selectedMessage={selectedMessage}
          activePlan={streamingPlan}
          activeLogs={isStreaming ? streamingLogs : (selectedMessage?.execution_result?.step_logs || [])}
          activeResult={streamingResult}
          isStreaming={isStreaming}
        />
      </div>

      {/* Upload Modal */}
      <FileUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUpload={handleUpload}
        onLoadSample={handleLoadSample}
      />
    </div>
  );
};

export default App;
