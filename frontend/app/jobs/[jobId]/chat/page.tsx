"use client";

import React, { use } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Sparkles,
  Plus,
  ArrowRight,
  UploadCloud,
  FileQuestion,
  Users,
  ShieldAlert,
} from "lucide-react";
import { fetchJob, createSession, ChatSession } from "@/lib/api";
import LockedChatState from "@/components/LockedChatState";

export default function ChatWelcomePage({
  params,
}: {
  params: Promise<{ jobId: string }> | { jobId: string };
}) {
  const unwrappedParams = use(params as any) as { jobId: string };
  const jobId = unwrappedParams.jobId;
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: job, isLoading, refetch } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
  });

  const createSessionMutation = useMutation({
    mutationFn: () => createSession(jobId),
    onSuccess: (newSession: ChatSession) => {
      queryClient.invalidateQueries({ queryKey: ["sessions", jobId] });
      router.push(`/jobs/${jobId}/chat/${newSession.id}`);
    },
  });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
        Loading job information...
      </div>
    );
  }

  // Check if ranking_status indicates no processed resumes exist yet
  // If not started, failed, or no ranking status, render locked state
  const isLocked =
    !job?.ranking_status ||
    job.ranking_status === "not_started" ||
    job.ranking_status === "failed";

  if (isLocked) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <LockedChatState
          jobId={jobId}
          jobTitle={job?.title}
          onUploadSuccess={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center max-w-2xl mx-auto space-y-8">
      {/* Welcome Banner */}
      <div className="space-y-3">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-indigo-600/20 border border-blue-500/30 flex items-center justify-center mx-auto text-blue-400 shadow-xl shadow-blue-500/10">
          <Bot className="w-8 h-8" />
        </div>

        <h2 className="text-2xl font-bold text-zinc-100 tracking-tight">
          {job?.title || "Candidate Intelligence"}
        </h2>
        <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
          Ask questions about applicant qualifications, compare candidates, or inspect match scores and experience for this opening.
        </p>
      </div>

      {/* Suggested Quick Starters */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full text-left">
        <button
          onClick={() => createSessionMutation.mutate()}
          className="p-4 rounded-xl bg-zinc-900/60 hover:bg-zinc-800/80 border border-zinc-800/80 hover:border-zinc-700 transition-all group flex flex-col gap-1 cursor-pointer"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-400">
            <Users className="w-4 h-4" />
            <span>Candidate Overview</span>
          </div>
          <p className="text-xs text-zinc-400 group-hover:text-zinc-300">
            Profile the top ranked candidates with summary, strengths, and gaps.
          </p>
        </button>

        <button
          onClick={() => createSessionMutation.mutate()}
          className="p-4 rounded-xl bg-zinc-900/60 hover:bg-zinc-800/80 border border-zinc-800/80 hover:border-zinc-700 transition-all group flex flex-col gap-1 cursor-pointer"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-purple-400">
            <Sparkles className="w-4 h-4" />
            <span>Skills Deep Dive</span>
          </div>
          <p className="text-xs text-zinc-400 group-hover:text-zinc-300">
            Compare candidate proficiencies in specific technologies and years of experience.
          </p>
        </button>
      </div>

      {/* Start Chat Button */}
      <button
        onClick={() => createSessionMutation.mutate()}
        disabled={createSessionMutation.isPending}
        className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-sm transition-all shadow-lg shadow-blue-600/20 cursor-pointer disabled:opacity-50"
      >
        <Plus className="w-4 h-4" />
        <span>{createSessionMutation.isPending ? "Starting Chat..." : "Start a New Conversation"}</span>
        <ArrowRight className="w-4 h-4 ml-1" />
      </button>
    </div>
  );
}
