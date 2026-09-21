"use client";

import React, { use } from "react";
import Link from "next/link";
import { useParams, useRouter, usePathname } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MessageSquare,
  Plus,
  Briefcase,
  Layers,
  ChevronRight,
  Sparkles,
  Bot,
  Compass,
} from "lucide-react";
import { fetchSessions, createSession, fetchJob, ChatSession } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function ChatLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ jobId: string }> | { jobId: string };
}) {
  const unwrappedParams = use(params as any) as { jobId: string };
  const jobId = unwrappedParams.jobId;
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { email, isAuthenticated, logout } = useAuth();

  // Fetch job details (to display job title and check ranking_status)
  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
    staleTime: 1000 * 30,
  });

  // Fetch session list for this job
  const { data: sessions = [], isLoading: isLoadingSessions } = useQuery({
    queryKey: ["sessions", jobId],
    queryFn: () => fetchSessions(jobId),
  });

  // Create new session mutation with auto-navigate
  const createSessionMutation = useMutation({
    mutationFn: () => createSession(jobId),
    onSuccess: (newSession: ChatSession) => {
      queryClient.invalidateQueries({ queryKey: ["sessions", jobId] });
      // Auto-navigate into newly created session per spec
      router.push(`/jobs/${jobId}/chat/${newSession.id}`);
    },
    onError: (err) => {
      console.error("Failed to create chat session:", err);
    },
  });

  return (
    <div className="flex h-screen w-full overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Google AI Studio–style Persistent Left Sidebar */}
      <aside className="w-72 flex flex-col shrink-0 border-r border-zinc-800/80 bg-zinc-900/40 backdrop-blur-xl select-none">
        {/* Top Header / Brand */}
        <div className="p-4 border-b border-zinc-800/60 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2.5 text-zinc-100 font-semibold tracking-tight hover:opacity-90 transition-opacity"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-md shadow-blue-500/20">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-semibold tracking-tight">AI Screener</span>
          </Link>

          <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400">
            RAG Chat
          </span>
        </div>

        {/* Action Buttons Section */}
        <div className="p-3 space-y-2 border-b border-zinc-800/60">
          {/* New Job Button - Navigates out of [jobId] to /jobs/new */}
          <Link
            href="/jobs/new"
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700/60 hover:border-zinc-600 text-zinc-200 text-xs font-medium transition-all group"
          >
            <Briefcase className="w-3.5 h-3.5 text-zinc-400 group-hover:text-blue-400 transition-colors" />
            <span className="flex-1 text-left">New Job</span>
            <ChevronRight className="w-3 h-3 text-zinc-500 group-hover:text-zinc-300" />
          </Link>

          {/* New Chat Button - Creates session & auto-navigates */}
          <button
            onClick={() => createSessionMutation.mutate()}
            disabled={createSessionMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 active:to-indigo-700 text-white text-xs font-medium transition-all shadow-md shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{createSessionMutation.isPending ? "Creating..." : "New Chat"}</span>
          </button>
        </div>

        {/* Current Job Info Header */}
        <div className="px-4 py-2.5 bg-zinc-950/30 border-b border-zinc-800/40">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            Current Job
          </p>
          <p className="text-xs font-medium text-zinc-200 truncate mt-0.5" title={job?.title}>
            {job?.title || `Job #${jobId}`}
          </p>
          {job?.ranking_status && (
            <div className="flex items-center gap-1.5 mt-1">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  job.ranking_status === "done"
                    ? "bg-emerald-400"
                    : job.ranking_status === "computing"
                    ? "bg-amber-400 animate-ping"
                    : "bg-zinc-500"
                }`}
              />
              <span className="text-[10px] text-zinc-400 capitalize">
                Status: {job.ranking_status.replace("_", " ")}
              </span>
            </div>
          )}
        </div>

        {/* Session List Title */}
        <div className="px-4 pt-3 pb-1 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
            Chat Sessions
          </span>
          <span className="text-[10px] text-zinc-500">
            {sessions.length}
          </span>
        </div>

        {/* Vertical Google AI Studio-style Session List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {isLoadingSessions ? (
            <div className="p-4 text-center text-xs text-zinc-500">
              Loading sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-zinc-500 space-y-1">
              <MessageSquare className="w-6 h-6 mx-auto opacity-40 text-zinc-400 mb-2" />
              <p>No chat sessions yet</p>
              <p className="text-[11px] text-zinc-600">Click &quot;New Chat&quot; to start</p>
            </div>
          ) : (
            sessions.map((session) => {
              const isActive = pathname === `/jobs/${jobId}/chat/${session.id}`;
              const formattedDate = new Date(session.updated_at || session.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              });

              return (
                <Link
                  key={session.id}
                  href={`/jobs/${jobId}/chat/${session.id}`}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs transition-all group relative ${
                    isActive
                      ? "bg-zinc-800 text-white font-medium shadow-sm border border-zinc-700/60"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40"
                  }`}
                >
                  <MessageSquare
                    className={`w-3.5 h-3.5 shrink-0 transition-colors ${
                      isActive ? "text-blue-400" : "text-zinc-500 group-hover:text-zinc-400"
                    }`}
                  />
                  <span className="flex-1 truncate">
                    Chat #{session.id}
                  </span>
                  <span className="text-[10px] text-zinc-500 shrink-0">
                    {formattedDate}
                  </span>
                </Link>
              );
            })
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-zinc-800/60 space-y-2">
          <Link
            href={`/jobs/${jobId}/upload`}
            className="w-full flex items-center justify-center gap-1.5 text-[11px] text-blue-400 hover:text-blue-300 font-medium transition-colors py-1"
          >
            <Layers className="w-3.5 h-3.5" />
            Resume Upload Pipeline
          </Link>

          {/* User Profile / Logout */}
          <div className="pt-2 border-t border-zinc-800/40 flex items-center justify-between text-xs">
            <span className="text-[11px] text-zinc-400 truncate max-w-[150px]" title={email}>
              {email || "Company Account"}
            </span>
            {isAuthenticated ? (
              <button
                onClick={() => logout()}
                className="text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
              >
                Sign Out
              </button>
            ) : (
              <Link
                href="/login"
                className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </aside>

      {/* Main Chat Panel View */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative">
        {children}
      </main>
    </div>
  );
}
