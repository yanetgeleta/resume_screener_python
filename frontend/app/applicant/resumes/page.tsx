"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  UploadCloud,
  Loader2,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Trash2,
  Plus,
  Clock,
  Sparkles,
  LogOut,
} from "lucide-react";
import {
  applicantGetResumesApi,
  applicantUploadResumeApi,
  getApplicantToken,
  clearApplicantTokens,
  ApplicantResume,
} from "@/lib/api";

export default function ApplicantResumesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  useEffect(() => {
    const curToken = getApplicantToken();
    if (!curToken) {
      router.push("/applicant/login");
    } else {
      setToken(curToken);
    }
  }, [router]);

  const {
    data: resumes = [],
    isLoading,
    refetch,
  } = useQuery<ApplicantResume[]>({
    queryKey: ["applicant-resumes", token],
    queryFn: applicantGetResumesApi,
    enabled: !!token,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => applicantUploadResumeApi(file),
    onSuccess: () => {
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ["applicant-resumes", token] });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Only PDF files are allowed.");
        return;
      }
      setSelectedFile(file);
      uploadMutation.mutate(file);
    }
  };

  const handleLogout = () => {
    clearApplicantTokens();
    router.push("/applicant/login");
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top Navbar */}
      <header className="h-16 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <Link href="/applicant/applications" className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>My Applications</span>
          </Link>
          <span className="text-zinc-600">/</span>
          <span className="text-xs font-semibold text-zinc-200">My Resumes</span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <Link
            href="/jobs"
            className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all shadow-sm"
          >
            Find Jobs
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
            <h1 className="text-xl font-bold text-white tracking-tight">Your Saved Resumes</h1>
            <p className="text-xs text-zinc-400 mt-1">
              Upload and manage your resumes to easily apply to marketplace positions.
            </p>
          </div>

          <label className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium cursor-pointer transition-all shadow-md shadow-blue-600/20 self-start sm:self-auto">
            {uploadMutation.isPending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Uploading PDF...</span>
              </>
            ) : (
              <>
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Upload New Resume</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploadMutation.isPending}
            />
          </label>
        </div>

        {uploadMutation.isError && (
          <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{(uploadMutation.error as Error)?.message || "Failed to upload resume"}</span>
          </div>
        )}

        {isLoading ? (
          <div className="p-12 text-center text-xs text-zinc-500">
            Loading your resumes...
          </div>
        ) : resumes.length === 0 ? (
          <div className="p-12 rounded-3xl bg-zinc-900/40 border border-zinc-800 text-center space-y-4">
            <FileText className="w-10 h-10 text-zinc-600 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-zinc-300">No resumes uploaded yet</h3>
              <p className="text-xs text-zinc-500 max-w-sm mx-auto">
                Upload your resume in PDF format to reuse across applications.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {resumes.map((r) => (
              <div
                key={r.id}
                className="p-5 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700/80 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-zinc-100">{r.original_filename}</h3>
                      <p className="text-[10px] text-zinc-500">
                        Uploaded {new Date(r.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  {Array.isArray(r.skills) && r.skills.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-[10px] text-zinc-500">Extracted Skills:</span>
                      {r.skills.slice(0, 6).map((sk, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 text-[10px]"
                        >
                          {sk}
                        </span>
                      ))}
                    </div>
                  )}

                  {r.experience_years !== null && r.experience_years !== undefined && (
                    <div className="text-[11px] text-zinc-400 flex items-center gap-1">
                      <Clock className="w-3 h-3 text-zinc-500" />
                      <span>{r.experience_years} years professional experience</span>
                    </div>
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
