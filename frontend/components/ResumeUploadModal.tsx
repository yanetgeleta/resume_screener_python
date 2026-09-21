"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  UploadCloud,
  FileText,
  X,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { uploadResumes, fetchJob, recomputeJobRankings } from "../lib/api";

interface ResumeUploadModalProps {
  jobId: string | number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (jobRankingsStatus: string) => void;
}

type Step = "select" | "uploading" | "processing" | "done";

export default function ResumeUploadModal({
  jobId,
  isOpen,
  onClose,
  onSuccess,
}: ResumeUploadModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [step, setStep] = useState<Step>("select");
  const [rankingStatus, setRankingStatus] = useState<string>("not_started");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  if (!isOpen) return null;

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
        const job = await fetchJob(jobId);
        setRankingStatus(job.ranking_status);

        if (job.ranking_status === "done") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setStep("done");
          setTimeout(() => {
            onSuccess?.("done");
          }, 1200);
        } else if (job.ranking_status === "failed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setErrorMsg("Ranking computation failed on the server.");
        }
      } catch (err: unknown) {
        console.error("Error polling job status:", err);
      }
    }, 2000);
  };

  const handleUploadAndProcess = async () => {
    if (files.length === 0) return;
    setErrorMsg(null);
    setStep("uploading");

    try {
      await uploadResumes(jobId, files);
      // Resume upload endpoint automatically links to job and triggers recompute_job_rankings
      // Also invoke recompute endpoint explicitly if needed to ensure ranking status updates
      try {
        await recomputeJobRankings(jobId);
      } catch {
        // May already be queued
      }
      startPollingRanking();
    } catch (err: unknown) {
      setStep("select");
      setErrorMsg(err instanceof Error ? err.message : "Failed to upload resumes.");
    }
  };

  const renderProcessingProgress = () => {
    const isRetrievalDone =
      rankingStatus === "retrieval_done" || rankingStatus === "done";
    const isCompleted = rankingStatus === "done";

    return (
      <div className="space-y-6 py-4">
        <div className="space-y-2 text-center">
          <h4 className="text-lg font-semibold text-zinc-100 flex items-center justify-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-400 animate-pulse" />
            AI Screening & Ranking Pipeline
          </h4>
          <p className="text-xs text-zinc-400">
            Extracting candidate profiles, computing vector embeddings, and scoring matches...
          </p>
        </div>

        {/* Multi-step progress timeline */}
        <div className="space-y-3 max-w-md mx-auto">
          {/* Step 1 */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-zinc-800/60 border border-zinc-700/50">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
              ✓
            </div>
            <div className="flex-1 text-left">
              <p className="text-xs font-medium text-zinc-200">Resumes Uploaded & Chunked</p>
              <p className="text-[11px] text-zinc-400">{files.length} document(s) parsed</p>
            </div>
          </div>

          {/* Step 2 */}
          <div
            className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
              isRetrievalDone
                ? "bg-zinc-800/60 border-zinc-700/50"
                : "bg-blue-950/20 border-blue-500/30 shadow-sm shadow-blue-500/10"
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
            <div className="flex-1 text-left">
              <p className="text-xs font-medium text-zinc-200">
                Vector Semantic Retrieval
              </p>
              <p className="text-[11px] text-zinc-400">
                {isRetrievalDone
                  ? "Top candidate chunks matched"
                  : "Matching embeddings against job description..."}
              </p>
            </div>
          </div>

          {/* Step 3 */}
          <div
            className={`flex items-center gap-3 p-3 rounded-xl border transition-all ${
              isCompleted
                ? "bg-zinc-800/60 border-zinc-700/50"
                : isRetrievalDone
                ? "bg-purple-950/20 border-purple-500/30"
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
            <div className="flex-1 text-left">
              <p className="text-xs font-medium text-zinc-200">
                LLM Profile & Final Weighted Scoring
              </p>
              <p className="text-[11px] text-zinc-400">
                {isCompleted
                  ? "Top candidates scored & ready"
                  : isRetrievalDone
                  ? "Synthesizing strengths, summary, and gaps..."
                  : "Pending retrieval"}
              </p>
            </div>
          </div>
        </div>

        {isCompleted && (
          <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm font-medium py-2">
            <CheckCircle2 className="w-5 h-5" />
            Ranking complete! Initializing synthesized profile...
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl p-6 relative flex flex-col gap-5 max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          disabled={step === "processing" || step === "uploading"}
          className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-200 disabled:opacity-30 p-1"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="space-y-1">
          <h3 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-blue-400" />
            Upload Candidate Resumes
          </h3>
          <p className="text-xs text-zinc-400">
            Upload PDF resumes to run AI screening and ranking.
          </p>
        </div>

        {errorMsg && (
          <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {step === "processing" || step === "done" ? (
          renderProcessingProgress()
        ) : (
          <>
            {/* Drag and drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center gap-3 ${
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
              <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center text-blue-400">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-zinc-200">
                  Click to browse or drag & drop PDFs
                </p>
                <p className="text-xs text-zinc-500 mt-1">
                  Supports multiple PDF files up to 10MB each
                </p>
              </div>
            </div>

            {/* Selected files list */}
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Selected Files ({files.length})
                </p>
                <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1">
                  {files.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-800/60 border border-zinc-700/40 text-xs"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                        <span className="text-zinc-200 truncate">{file.name}</span>
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
                        className="text-zinc-400 hover:text-red-400 p-1"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={files.length === 0 || step === "uploading"}
                onClick={handleUploadAndProcess}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-medium transition-all shadow-lg shadow-blue-600/20"
              >
                {step === "uploading" ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    Upload & Rank
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
