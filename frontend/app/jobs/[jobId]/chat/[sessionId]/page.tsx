"use client";

import React, { use, useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Send,
  Square,
  Bot,
  User,
  UploadCloud,
  AlertCircle,
  Sparkles,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { fetchJob, fetchMessages, ChatMessage } from "@/lib/api";
import { useChatStream } from "@/lib/useChatStream";
import LockedChatState from "@/components/LockedChatState";
import ResumeUploadModal from "@/components/ResumeUploadModal";

export default function ChatSessionConversationPage({
  params,
}: {
  params: Promise<{ jobId: string; sessionId: string }> | { jobId: string; sessionId: string };
}) {
  const unwrappedParams = use(params as any) as { jobId: string; sessionId: string };
  const { jobId, sessionId } = unwrappedParams;
  const searchParams = useSearchParams();

  const [inputQuery, setInputQuery] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autoSynthesizedRef = useRef(false);

  // Fetch Job details to monitor title and ranking_status
  const {
    data: job,
    refetch: refetchJob,
  } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
  });

  // Message history load: useQuery keyed on sessionId fetching persisted ChatMessage rows
  // Set refetchOnWindowFocus: false on this query per specification
  const {
    data: messages = [],
    isLoading: isLoadingMessages,
    refetch: refetchMessages,
  } = useQuery({
    queryKey: ["messages", String(sessionId)],
    queryFn: () => fetchMessages(sessionId),
    refetchOnWindowFocus: false,
  });

  // Stream state & send/abort wiring
  const {
    state: streamState,
    sendQuery,
    abortStream,
    isStreaming,
    partialText,
    errorDetail,
  } = useChatStream({
    sessionId,
    jobId,
  });

  // Auto-synthesize top candidates query if directed from resume upload transition
  useEffect(() => {
    const shouldAutoSynthesize = searchParams.get("autoSynthesize") === "true";
    if (
      shouldAutoSynthesize &&
      !autoSynthesizedRef.current &&
      !isLoadingMessages &&
      messages.length === 0
    ) {
      autoSynthesizedRef.current = true;
      const headCount = job?.head_count || 5;
      const synthesizedQuery = `Please provide a profile of the top ${headCount} candidates ranked by final_score, each with strengths, summary, and gaps.`;
      sendQuery(synthesizedQuery);
    }
  }, [searchParams, isLoadingMessages, messages.length, job?.head_count, sendQuery]);

  // Auto-scroll to bottom as messages or streamed text updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, partialText]);

  // Check for locked state (no processed resumes exist yet)
  const isLocked =
    !job?.ranking_status ||
    job.ranking_status === "not_started" ||
    job.ranking_status === "failed";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isStreaming || isLocked) return;

    const textToSend = inputQuery.trim();
    setInputQuery("");
    sendQuery(textToSend);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Called when additional resumes uploaded & ranked while in chat
  const handleUploadMoreSuccess = async () => {
    setShowUploadModal(false);
    await refetchJob();
    // Synthesize updated ranking summary query in this same chat per specification
    const headCount = job?.head_count || 5;
    const synthesizedQuery = `Please provide an updated profile of the top ${headCount} candidates ranked by final_score, including each candidate's strengths, summary, and gaps.`;
    sendQuery(synthesizedQuery);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950">
      {/* Top Session Header */}
      <header className="h-14 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/30 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              <span>{job?.title || "Candidate Chat"}</span>
              <span className="text-[10px] text-zinc-500 font-normal">
                (Session #{sessionId})
              </span>
            </h2>
            <p className="text-[10px] text-zinc-400">
              RAG Assistant • Context-grounded screening
            </p>
          </div>
        </div>

        {/* Upload More Resumes affordance */}
        <button
          onClick={() => setShowUploadModal(true)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700/80 border border-zinc-700/60 text-zinc-200 text-xs font-medium transition-all shadow-sm cursor-pointer"
        >
          <UploadCloud className="w-3.5 h-3.5 text-blue-400" />
          <span>Upload More Resumes</span>
        </button>
      </header>

      {/* Main Conversation Body */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {isLoadingMessages ? (
          <div className="flex items-center justify-center h-full text-xs text-zinc-500">
            Loading message history...
          </div>
        ) : messages.length === 0 && !partialText ? (
          <div className="max-w-xl mx-auto my-auto text-center space-y-3 py-12">
            <div className="w-12 h-12 rounded-2xl bg-zinc-900 border border-zinc-800 text-zinc-400 flex items-center justify-center mx-auto">
              <Sparkles className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-base font-semibold text-zinc-200">
              Ready to evaluate candidates
            </h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Ask about candidates&apos; matching skills, experience gaps, or ask for the top
              candidates ranked by score.
            </p>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-4">
            {/* Persisted Messages loaded via useQuery */}
            {messages.map((msg: ChatMessage) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex gap-3 text-sm ${
                    isUser ? "justify-end" : "justify-start"
                  }`}
                >
                  {!isUser && (
                    <div className="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                  )}
                  <div
                    className={`rounded-2xl px-4 py-3 max-w-[85%] whitespace-pre-wrap leading-relaxed shadow-sm ${
                      isUser
                        ? "bg-blue-600 text-white rounded-br-xs"
                        : "bg-zinc-900/90 border border-zinc-800/80 text-zinc-200 rounded-bl-xs"
                    }`}
                  >
                    {msg.content}
                  </div>
                  {isUser && (
                    <div className="w-7 h-7 rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700 flex items-center justify-center shrink-0 mt-0.5">
                      <User className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              );
            })}

            {/* Live Streaming Bubble (Rendered above live stream from useReducer) */}
            {partialText && (
              <div className="flex gap-3 text-sm justify-start animate-fade-in">
                <div className="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                </div>
                <div className="rounded-2xl px-4 py-3 max-w-[85%] whitespace-pre-wrap leading-relaxed bg-zinc-900/90 border border-blue-500/40 text-zinc-100 shadow-md shadow-blue-500/5 rounded-bl-xs relative">
                  {partialText}
                  {isStreaming && (
                    <span className="inline-block w-2 h-4 ml-1 bg-blue-400 animate-pulse align-middle" />
                  )}
                </div>
              </div>
            )}

            {/* Error Detail Display */}
            {errorDetail && (
              <div className="flex gap-3 text-sm justify-start">
                <div className="w-7 h-7 rounded-lg bg-red-600/20 text-red-400 border border-red-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                </div>
                <div className="rounded-2xl px-4 py-3 max-w-[85%] bg-red-950/40 border border-red-800/60 text-red-300 text-xs">
                  <p className="font-semibold mb-1">Streaming Error</p>
                  <p>{errorDetail}</p>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Composer Section / Locked State */}
      <div className="border-t border-zinc-800/80 p-4 bg-zinc-900/40 backdrop-blur-xl shrink-0">
        <div className="max-w-3xl mx-auto">
          {isLocked ? (
            /* Locked State — composer replaced with upload message + affordance */
            <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-600/30 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
                <div className="text-left">
                  <p className="text-xs font-medium text-amber-200">
                    Chat is locked: Resumes must be uploaded
                  </p>
                  <p className="text-[11px] text-amber-400/80">
                    Process candidate resumes before submitting questions.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowUploadModal(true)}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 active:bg-amber-700 text-white text-xs font-medium transition-all shrink-0 cursor-pointer shadow-md"
              >
                Upload Resumes
              </button>
            </div>
          ) : (
            /* Normal Composer Form */
            <form onSubmit={handleSubmit} className="relative flex items-center gap-2">
              <textarea
                ref={textareaRef}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about candidate qualifications, skills, or ranking..."
                rows={1}
                disabled={isStreaming}
                className="flex-1 bg-zinc-900/90 border border-zinc-700/70 focus:border-blue-500 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none resize-none min-h-[46px] max-h-32 transition-all shadow-inner"
              />

              {isStreaming ? (
                <button
                  type="button"
                  onClick={abortStream}
                  className="h-[46px] px-4 rounded-xl bg-red-600/90 hover:bg-red-500 active:bg-red-700 text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-md shadow-red-600/20 cursor-pointer"
                  title="Stop generating"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!inputQuery.trim()}
                  className="h-[46px] px-4 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium flex items-center gap-1.5 transition-all shadow-md shadow-blue-600/20 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send</span>
                </button>
              )}
            </form>
          )}
        </div>
      </div>

      {/* Upload Modal (accessible via header affordance or locked state) */}
      {showUploadModal && (
        <ResumeUploadModal
          jobId={jobId}
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadMoreSuccess}
        />
      )}
    </div>
  );
}
