"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  Plus,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Bot,
  LogIn,
  LogOut,
  UserPlus,
  Layers,
  ChevronRight,
  Lock,
  RefreshCw,
  Check,
} from "lucide-react";
import { fetchJobs } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function HomePage() {
  const { isAuthenticated, email, logout, refreshAuth, isRefreshing, isLoading: isAuthLoading } = useAuth();
  const [refreshSuccess, setRefreshSuccess] = React.useState(false);

  const handleManualRefresh = async () => {
    const ok = await refreshAuth();
    if (ok) {
      setRefreshSuccess(true);
      setTimeout(() => setRefreshSuccess(false), 2000);
    }
  };

  const {
    data: jobs = [],
    isLoading: isJobsLoading,
    error: jobsError,
  } = useQuery({
    queryKey: ["all-jobs", isAuthenticated],
    queryFn: fetchJobs,
    enabled: isAuthenticated,
  });

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top Navbar */}
      <header className="h-16 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-zinc-100">
              AI Candidate Screener
            </h1>
            <p className="text-[10px] text-zinc-400">
              Context-Grounded Resume Screening & RAG Chat
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <>
              {email && (
                <span className="hidden sm:inline-block text-xs text-zinc-400">
                  {email}
                </span>
              )}
              <button
                onClick={handleManualRefresh}
                disabled={isRefreshing}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800/80 hover:bg-zinc-700/80 border border-zinc-700/60 text-zinc-300 hover:text-zinc-100 text-xs font-medium transition-all cursor-pointer disabled:opacity-50"
                title="Refresh Authentication Token"
              >
                {refreshSuccess ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="hidden sm:inline text-emerald-400">Refreshed</span>
                  </>
                ) : (
                  <>
                    <RefreshCw className={`w-3.5 h-3.5 text-blue-400 ${isRefreshing ? "animate-spin" : ""}`} />
                    <span className="hidden sm:inline">{isRefreshing ? "Refreshing..." : "Refresh Token"}</span>
                  </>
                )}
              </button>
              <Link
                href="/jobs/new"
                className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-medium transition-all shadow-md shadow-blue-600/20"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New Job</span>
              </Link>
              <button
                onClick={() => logout()}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors cursor-pointer"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-md shadow-blue-600/20"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Sign Up</span>
              </Link>
            </>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-6 sm:p-10 space-y-8">
        {/* Hero Section */}
        <div className="p-8 rounded-3xl bg-gradient-to-br from-blue-950/30 via-zinc-900/60 to-purple-950/20 border border-zinc-800/80 shadow-2xl relative overflow-hidden">
          <div className="max-w-xl space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Multi-Candidate AI RAG Screening</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Screen, Rank & Profile Candidates with AI
            </h2>
            <p className="text-zinc-400 text-sm leading-relaxed">
              Upload resumes, automatically compute vector embeddings and composite match scores, and interact through a Google AI Studio-style streaming chat panel.
            </p>
            <div className="pt-2 flex items-center gap-3">
              {isAuthenticated ? (
                <Link
                  href="/jobs/new"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-xs font-medium transition-all shadow-lg shadow-blue-600/20"
                >
                  <span>Create Job & Upload Resumes</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              ) : (
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-xs font-medium transition-all shadow-lg shadow-blue-600/20"
                >
                  <span>Get Started Free</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Jobs List Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-zinc-200 flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-blue-400" />
              <span>Your Job Openings</span>
            </h3>
            {isAuthenticated && (
              <span className="text-xs text-zinc-500">
                {jobs.length} opening(s)
              </span>
            )}
          </div>

          {!isAuthenticated ? (
            /* Unauthenticated Callout */
            <div className="p-10 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-zinc-800/80 border border-zinc-700 text-zinc-400 flex items-center justify-center mx-auto">
                <Lock className="w-6 h-6 text-zinc-400" />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-semibold text-zinc-200">
                  Authentication Required
                </h4>
                <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                  Please sign in or create a company account to view your jobs and chat sessions.
                </p>
              </div>
              <div className="flex items-center justify-center gap-3 pt-2">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span>Sign In</span>
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all shadow-md shadow-blue-600/20"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>Register Company</span>
                </Link>
              </div>
            </div>
          ) : isJobsLoading ? (
            <div className="p-8 text-center text-xs text-zinc-500">
              Loading your jobs...
            </div>
          ) : jobs.length === 0 ? (
            <div className="p-12 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-3">
              <Briefcase className="w-8 h-8 text-zinc-600 mx-auto" />
              <p className="text-sm font-medium text-zinc-300">No job openings yet</p>
              <p className="text-xs text-zinc-500">
                Create your first job posting to begin screening candidates.
              </p>
              <Link
                href="/jobs/new"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Job</span>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {jobs.map((job: any) => (
                <div
                  key={job.id}
                  className="p-5 rounded-2xl bg-zinc-900/60 hover:bg-zinc-900/90 border border-zinc-800/80 hover:border-zinc-700/80 transition-all space-y-4 shadow-sm flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-semibold text-zinc-100 truncate">
                        {job.title}
                      </h4>
                      <span
                        className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full shrink-0 ${
                          job.ranking_status === "done"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : job.ranking_status === "computing"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                        }`}
                      >
                        {job.ranking_status ? job.ranking_status.replace("_", " ") : "not started"}
                      </span>
                    </div>

                    <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                      {job.description}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-zinc-500">
                      Target: {job.head_count || "N/A"} candidate(s)
                    </span>

                    <div className="flex items-center gap-2">
                      <Link
                        href={`/jobs/${job.id}/upload`}
                        className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors"
                      >
                        Upload
                      </Link>
                      <Link
                        href={`/jobs/${job.id}/chat`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all"
                      >
                        <MessageSquare className="w-3 h-3" />
                        <span>Chat</span>
                        <ChevronRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
