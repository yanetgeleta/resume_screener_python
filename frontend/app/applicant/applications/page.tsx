"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Building2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowLeft,
  Briefcase,
  Compass,
  LogOut,
} from "lucide-react";
import {
  applicantGetApplicationsApi,
  getApplicantToken,
  getStoredApplicant,
  clearApplicantTokens,
  ApplicantApplication,
} from "@/lib/api";

export default function ApplicantApplicationsPage() {
  const router = useRouter();
  const [token, setToken] = useState<string>("");
  const [applicant, setApplicant] = useState(() => getStoredApplicant());

  useEffect(() => {
    const curToken = getApplicantToken();
    if (!curToken) {
      router.push("/applicant/login");
    } else {
      setToken(curToken);
      setApplicant(getStoredApplicant());
    }
  }, [router]);

  const {
    data: applications = [],
    isLoading,
    refetch,
  } = useQuery<ApplicantApplication[]>({
    queryKey: ["applicant-applications", token],
    queryFn: applicantGetApplicationsApi,
    enabled: !!token,
    refetchInterval: 5000, // Poll every 5s while applications are processing
  });

  const handleLogout = () => {
    clearApplicantTokens();
    router.push("/applicant/login");
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "processed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
            <CheckCircle2 className="w-3 h-3" />
            <span>Screened</span>
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-semibold">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Processing</span>
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-semibold">
            <AlertCircle className="w-3 h-3" />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold">
            <Clock className="w-3 h-3" />
            <span>Queued</span>
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top Navbar */}
      <header className="h-16 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link href="/jobs" className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Job Marketplace</span>
          </Link>
          <span className="text-zinc-600">/</span>
          <span className="text-xs font-semibold text-zinc-200">My Applications</span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <Link
            href="/applicant/resumes"
            className="px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
          >
            My Resumes
          </Link>
          <Link
            href="/jobs"
            className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all shadow-sm"
          >
            Browse Jobs
          </Link>
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-xl text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-6 sm:p-10 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Your Submitted Applications</h1>
            <p className="text-xs text-zinc-400 mt-1">
              Live status tracking for jobs you've applied to.
            </p>
          </div>
          {applicant && (
            <div className="text-xs text-zinc-400">
              Logged in as <strong className="text-zinc-200">{applicant.full_name}</strong>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-zinc-500">
            Loading your applications...
          </div>
        ) : applications.length === 0 ? (
          <div className="p-12 rounded-3xl bg-zinc-900/40 border border-zinc-800 text-center space-y-4">
            <Briefcase className="w-10 h-10 text-zinc-600 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-zinc-300">No applications submitted yet</h3>
              <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                Explore open positions on the marketplace and submit your application with a single click.
              </p>
            </div>
            <Link
              href="/jobs"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow-md shadow-blue-600/20 transition-all"
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Browse Job Marketplace</span>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {applications.map((app) => (
              <div
                key={app.id}
                className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700/80 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-sm font-semibold text-zinc-100">{app.job.title}</h3>
                    {getStatusBadge(app.pipeline_status)}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400">
                    {app.job.company_name && (
                      <span className="flex items-center gap-1 text-[11px]">
                        <Building2 className="w-3 h-3 text-zinc-500" />
                        <span>{app.job.company_name}</span>
                      </span>
                    )}
                    <span className="flex items-center gap-1 text-[11px]">
                      <FileText className="w-3 h-3 text-zinc-500" />
                      <span>{app.resume_filename || "Resume PDF"}</span>
                    </span>
                    <span className="text-[11px] text-zinc-500">
                      Applied {new Date(app.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    href={`/jobs/${app.job.id}`}
                    className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs transition-colors"
                  >
                    View Job Posting
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
