"use client";

import React, { use, useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  UploadCloud,
  FileText,
  X,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Sparkles,
  ArrowRight,
  SkipForward,
  Briefcase,
} from "lucide-react";
import { uploadResumes, fetchJob, createSession, recomputeJobRankings } from "@/lib/api";

type Step = "select" | "uploading" | "processing" | "completed";

export default function ResumeUploadPage({
  params,
}: {
  params: Promise<{ jobId: string }> | { jobId: string };
}) {
  const unwrappedParams = use(params as any) as { jobId: string };
  const jobId = unwrappedParams.jobId;
  const router = useRouter();

  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [step, setStep] = useState<Step>("select");
  const [rankingStatus, setRankingStatus] = useState<string>("not_started");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
  });

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );
    if (droppedFiles.length > 0) {
      setFiles((prev) => [...prev, ...droppedFiles]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).filter((file) =>
        file.name.toLowerCase().endsWith(".pdf")
      );
      setFiles((prev) => [...prev, ...selected]);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const startPollingRanking = () => {
    setStep("processing");
    pollIntervalRef.current = setInterval(async () => {
      try {
        const updatedJob = await fetchJob(jobId);
        setRankingStatus(updatedJob.ranking_status);

        if (updatedJob.ranking_status === "done") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setStep("completed");

          // Transition to done first time:
          // 1. Create a new chat session for that job
          // 2. Navigate to that chat session with autoSynthesize flag
          setTimeout(async () => {
            try {
              const newSession = await createSession(jobId);
              router.push(`/jobs/${jobId}/chat/${newSession.id}?autoSynthesize=true`);
            } catch (createErr) {
              console.error("Failed to auto-create session on ranking done:", createErr);
              router.push(`/jobs/${jobId}/chat`);
            }
          }, 1500);
        } else if (updatedJob.ranking_status === "failed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setErrorMsg("Candidate ranking recomputation failed on the backend.");
        }
      } catch (err: unknown) {
        console.error("Error polling ranking status:", err);
      }
    }, 2000);
  };

  const handleUploadAndProcess = async () => {
    if (files.length === 0) return;
    setErrorMsg(null);
    setStep("uploading");

    try {
      await uploadResumes(jobId, files);
      try {
        await recomputeJobRankings(jobId);
      } catch {
        // Ignored if already computing
      }
      startPollingRanking();
    } catch (err: unknown) {
      setStep("select");
      setErrorMsg(err instanceof Error ? err.message : "Failed to upload candidate resumes.");
    }
  };

  const isRetrievalDone =
    rankingStatus === "retrieval_done" || rankingStatus === "done";
  const isCompleted = rankingStatus === "done";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl w-full mx-auto space-y-8">
        {/* Header with Title and Job Context */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto shadow-lg shadow-blue-500/10">
            <UploadCloud className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Upload Resumes for Screening
          </h1>
          <p className="text-sm text-zinc-400 max-w-md mx-auto">
            Job: <span className="text-zinc-200 font-medium">{job?.title || `Job #${jobId}`}</span>
          </p>
        </div>

        {/* Upload Container */}
        <div className="p-8 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 shadow-2xl backdrop-blur-xl space-y-6">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
              <span>{errorMsg}</span>
            </div>
          )}

          {step === "processing" || step === "completed" ? (
            /* In-Loop Progress State (not a bare spinner) */
            <div className="space-y-6 py-4">
              <div className="space-y-2 text-center">
                <h3 className="text-lg font-semibold text-zinc-100 flex items-center justify-center gap-2">
                  <Sparkles className="w-5 h-5 text-purple-400 animate-pulse" />
                  Candidate Screening Pipeline
                </h3>
                <p className="text-xs text-zinc-400">
                  Processing documents through embedding generation, vector retrieval, and LLM scoring.
                </p>
              </div>

              {/* Progress Steps */}
              <div className="space-y-3 max-w-md mx-auto">
                <div className="flex items-center gap-3 p-3.5 rounded-xl bg-zinc-800/60 border border-zinc-700/50">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                    ✓
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-200">Resumes Uploaded & Chunked</p>
                    <p className="text-[11px] text-zinc-400">{files.length} document(s) received</p>
                  </div>
                </div>

                <div
                  className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all ${
                    isRetrievalDone
                      ? "bg-zinc-800/60 border-zinc-700/50"
                      : "bg-blue-950/20 border-blue-500/40 shadow-sm shadow-blue-500/10"
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                      isRetrievalDone
                        ? "bg-emerald-500/20 text-emerald-400"
                        : "bg-blue-500/20 text-blue-400"
                    }`}
                  >
                    {isRetrievalDone ? (
                      "✓"
                    ) : (
                      <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-200">
                      Vector Similarity Search
                    </p>
                    <p className="text-[11px] text-zinc-400">
                      {isRetrievalDone
                        ? "Candidate chunks ranked by pgvector"
                        : "Matching candidate vectors against job description..."}
                    </p>
                  </div>
                </div>

                <div
                  className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all ${
                    isCompleted
                      ? "bg-zinc-800/60 border-zinc-700/50"
                      : isRetrievalDone
                      ? "bg-purple-950/20 border-purple-500/40"
                      : "bg-zinc-900/40 border-zinc-800/50 opacity-60"
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${
                      isCompleted
                        ? "bg-emerald-500/20 text-emerald-400"
                        : isRetrievalDone
                        ? "bg-purple-500/20 text-purple-400"
                        : "bg-zinc-800 text-zinc-500"
                    }`}
                  >
                    {isCompleted ? (
                      "✓"
                    ) : isRetrievalDone ? (
                      <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                    ) : (
                      "3"
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-200">
                      Final Weighted Composite Scoring & Profiles
                    </p>
                    <p className="text-[11px] text-zinc-400">
                      {isCompleted
                        ? "Top candidates ready"
                        : isRetrievalDone
                        ? "Synthesizing match summaries and gaps..."
                        : "Waiting on retrieval stage"}
                    </p>
                  </div>
                </div>
              </div>

              {isCompleted && (
                <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm font-medium py-3">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Ranking completed! Opening chat session...</span>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Drag & Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all flex flex-col items-center gap-4 ${
                  isDragging
                    ? "border-blue-500 bg-blue-950/20"
                    : "border-zinc-700/80 hover:border-zinc-600 bg-zinc-950/40"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <div className="w-14 h-14 rounded-2xl bg-zinc-800/80 border border-zinc-700/80 flex items-center justify-center text-blue-400 shadow-md">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-200">
                    Click to browse or drag & drop PDFs
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    Upload candidate resumes (PDF format, up to 10MB each)
                  </p>
                </div>
              </div>

              {/* Selected Files List */}
              {files.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    Selected Files ({files.length})
                  </p>
                  <div className="max-h-44 overflow-y-auto space-y-1.5 pr-1">
                    {files.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 rounded-xl bg-zinc-800/50 border border-zinc-700/40 text-xs"
                      >
                        <div className="flex items-center gap-2.5 truncate">
                          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                          <span className="text-zinc-200 truncate font-medium">{file.name}</span>
                          <span className="text-zinc-500 text-[10px]">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFile(idx);
                          }}
                          className="text-zinc-400 hover:text-red-400 p-1 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons: Skip vs Upload & Rank */}
              <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
                {/* Skip Control — routes straight to job's chat in locked state */}
                <Link
                  href={`/jobs/${jobId}/chat`}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/40 transition-colors"
                >
                  <SkipForward className="w-3.5 h-3.5" />
                  <span>Skip for now</span>
                </Link>

                <button
                  type="button"
                  disabled={files.length === 0 || step === "uploading"}
                  onClick={handleUploadAndProcess}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium transition-all shadow-lg shadow-blue-600/20 cursor-pointer"
                >
                  {step === "uploading" ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <>
                      <span>Upload & Screen Candidates</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
