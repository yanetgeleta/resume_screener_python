"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  Search,
  Building2,
  Clock,
  Sparkles,
  ArrowRight,
  Filter,
  CheckCircle2,
  Users,
  Compass,
  User,
  LogIn,
  LogOut,
} from "lucide-react";
import { searchJobsApi, Job, getStoredApplicant, clearApplicantTokens } from "@/lib/api";

export default function JobsMarketplacePage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [applicant, setApplicant] = useState(() => getStoredApplicant());

  React.useEffect(() => {
    const handleAuthChange = () => setApplicant(getStoredApplicant());
    window.addEventListener("applicant_auth_changed", handleAuthChange);
    return () => window.removeEventListener("applicant_auth_changed", handleAuthChange);
  }, []);

  // Debounce search input
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 350);
    return () => clearTimeout(timer);
  }, [query]);

  const {
    data: jobs = [],
    isLoading,
    error,
  } = useQuery<Job[]>({
    queryKey: ["jobs-search", debouncedQuery],
    queryFn: () => searchJobsApi(debouncedQuery),
  });

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Marketplace Header */}
      <header className="h-16 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 group-hover:scale-105 transition-transform">
              <Compass className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-zinc-100">
                ATS Job Marketplace
              </h1>
              <p className="text-[10px] text-zinc-400">
                Explore Open Positions & Apply with AI Screening
              </p>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {applicant ? (
            <div className="flex items-center gap-2">
              <Link
                href="/applicant/applications"
                className="px-3 py-1.5 rounded-xl bg-blue-600/10 border border-blue-500/30 text-blue-400 hover:bg-blue-600/20 transition-all font-medium"
              >
                My Applications
              </Link>
              <Link
                href="/applicant/resumes"
                className="px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors font-medium"
              >
                My Resumes
              </Link>
              <span className="hidden sm:inline text-zinc-400 text-[11px] pl-1">
                {applicant.full_name}
              </span>
              <button
                onClick={() => {
                  clearApplicantTokens();
                  setApplicant(null);
                }}
                className="p-1.5 rounded-xl text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/applicant/login"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Applicant Sign In</span>
              </Link>
              <Link
                href="/applicant/signup"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md shadow-blue-600/20 transition-all"
              >
                <span>Applicant Sign Up</span>
              </Link>
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-6 sm:p-10 space-y-8">
        {/* Search Hero */}
        <div className="p-8 sm:p-10 rounded-3xl bg-gradient-to-br from-blue-950/40 via-zinc-900/60 to-purple-950/20 border border-zinc-800/80 shadow-2xl space-y-6">
          <div className="max-w-xl space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Hybrid Full-Text + Semantic Vector Search</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Find Your Next Role
            </h2>
            <p className="text-zinc-400 text-sm leading-relaxed">
              Search by job title, description, or desired tech stack. Our MiniLM vector model ranks relevant opportunities semantically.
            </p>
          </div>

          {/* Search Input Bar */}
          <div className="relative max-w-2xl">
            <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by keywords, skills (e.g. Python, Django, React, AWS)..."
              className="w-full pl-12 pr-4 py-3.5 rounded-2xl bg-zinc-950/90 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none shadow-xl transition-all"
            />
            {query && (
              <button
                onClick={() => setQuery("")}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-zinc-400 hover:text-zinc-200"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Results Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-blue-400" />
            <h3 className="text-base font-semibold text-zinc-200">
              {debouncedQuery ? `Search Results for "${debouncedQuery}"` : "All Open Positions"}
            </h3>
          </div>
          <span className="text-xs text-zinc-500">{jobs.length} open position(s)</span>
        </div>

        {/* Jobs Listing */}
        {isLoading ? (
          <div className="p-12 text-center text-xs text-zinc-500">
            Scanning job marketplace with semantic vector matching...
          </div>
        ) : error ? (
          <div className="p-8 rounded-2xl bg-red-950/30 border border-red-800/40 text-red-300 text-xs text-center">
            Failed to load jobs. {(error as Error).message}
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-12 rounded-2xl bg-zinc-900/40 border border-zinc-800 text-center space-y-3">
            <Briefcase className="w-8 h-8 text-zinc-600 mx-auto" />
            <p className="text-sm font-medium text-zinc-300">No matching jobs found</p>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              Try adjusting your search keywords or browsing all open opportunities.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="p-6 rounded-2xl bg-zinc-900/50 hover:bg-zinc-900/80 border border-zinc-800/80 hover:border-zinc-700/80 transition-all shadow-sm space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <h4 className="text-base font-semibold text-zinc-100">{job.title}</h4>
                      {job.company_name && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-zinc-800 text-zinc-300 text-xs font-medium border border-zinc-700">
                          <Building2 className="w-3 h-3 text-zinc-400" />
                          <span>{job.company_name}</span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                      {job.description}
                    </p>
                  </div>

                  <Link
                    href={`/jobs/${job.id}`}
                    className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium text-xs transition-all shadow-md shadow-blue-600/20 shrink-0 self-start"
                  >
                    <span>View & Apply</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>

                {/* Tags & Meta Row */}
                <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-zinc-800/60 text-xs text-zinc-400">
                  {job.head_count !== null && job.head_count !== undefined && (
                    <span className="flex items-center gap-1 text-[11px] text-zinc-400">
                      <Users className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Target: {job.head_count}</span>
                    </span>
                  )}

                  {job.required_experience_years !== null && (
                    <span className="flex items-center gap-1 text-[11px] text-zinc-400">
                      <Clock className="w-3.5 h-3.5 text-zinc-500" />
                      <span>{job.required_experience_years}+ years experience</span>
                    </span>
                  )}

                  {Array.isArray(job.skills) && job.skills.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      {job.skills.slice(0, 5).map((skill, sIdx) => (
                        <span
                          key={sIdx}
                          className="px-2 py-0.5 rounded-md bg-blue-950/40 border border-blue-800/40 text-blue-300 text-[10px]"
                        >
                          {skill}
                        </span>
                      ))}
                      {job.skills.length > 5 && (
                        <span className="text-[10px] text-zinc-500">
                          +{job.skills.length - 5} more
                        </span>
                      )}
                    </div>
                  )}

                  {Array.isArray(job.application_fields) && job.application_fields.length > 0 && (
                    <span className="text-[11px] text-zinc-500 ml-auto">
                      {job.application_fields.length} custom question(s)
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
