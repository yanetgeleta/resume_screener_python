"use client";

import React, { useState } from "react";
import { UploadCloud, AlertCircle, FileText } from "lucide-react";
import ResumeUploadModal from "./ResumeUploadModal";

interface LockedChatStateProps {
  jobId: string | number;
  jobTitle?: string;
  onUploadSuccess?: () => void;
}

export default function LockedChatState({
  jobId,
  jobTitle = "this job",
  onUploadSuccess,
}: LockedChatStateProps) {
  const [showUploadModal, setShowUploadModal] = useState(false);

  return (
    <div className="w-full max-w-2xl mx-auto my-auto p-8 rounded-2xl bg-zinc-900/70 border border-zinc-800 shadow-2xl backdrop-blur-md text-center flex flex-col items-center gap-5">
      <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
        <AlertCircle className="w-8 h-8" />
      </div>

      <div className="space-y-2">
        <h3 className="text-xl font-semibold text-zinc-100 tracking-tight">
          Chat is Locked
        </h3>
        <p className="text-sm text-zinc-400 max-w-md mx-auto leading-relaxed">
          No processed candidate resumes exist yet for <span className="text-zinc-200 font-medium">{jobTitle}</span>.
          Upload candidate PDF resumes to start screening, ranking, and asking questions.
        </p>
      </div>

      <button
        onClick={() => setShowUploadModal(true)}
        className="inline-flex items-center gap-2.5 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium text-sm transition-all shadow-lg shadow-blue-600/20 cursor-pointer"
      >
        <UploadCloud className="w-4 h-4" />
        Upload Resumes Now
      </button>

      {showUploadModal && (
        <ResumeUploadModal
          jobId={jobId}
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            setShowUploadModal(false);
            onUploadSuccess?.();
          }}
        />
      )}
    </div>
  );
}
