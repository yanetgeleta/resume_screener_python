"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import {
  Briefcase,
  AlertCircle,
  ArrowRight,
  Loader2,
  FileText,
  Clock,
  Users,
} from "lucide-react";
import { createJob } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

export default function NewJobPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [requiredExperienceYears, setRequiredExperienceYears] = useState<string>("");
  const [headCount, setHeadCount] = useState<string>("");

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.push("/login?redirect=/jobs/new");
    }
  }, [isAuthenticated, isAuthLoading, router]);

  const createJobMutation = useMutation({
    mutationFn: async () => {
      const expYears = requiredExperienceYears.trim() !== "" ? parseInt(requiredExperienceYears, 10) : null;
      const count = headCount.trim() !== "" ? parseInt(headCount, 10) : null;

      return createJob({
        title: title.trim(),
        description: description.trim(),
        required_experience_years: expYears,
        head_count: count,
      });
    },
    onSuccess: (newJob) => {
      // On successful submit, redirect to resume-upload step
      router.push(`/jobs/${newJob.id}/upload`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    createJobMutation.mutate();
  };

  const isExpBlank = requiredExperienceYears.trim() === "";
  const isHeadCountBlank = headCount.trim() === "";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-xl w-full mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto shadow-lg shadow-blue-500/10">
            <Briefcase className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Create a New Job Opening
          </h1>
          <p className="text-sm text-zinc-400 max-w-sm mx-auto">
            Specify the job details. Our AI pipeline will extract required skills, compute embeddings, and screen candidates.
          </p>
        </div>

        {/* Job Form */}
        <form
          onSubmit={handleSubmit}
          className="p-8 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 shadow-2xl backdrop-blur-xl space-y-6"
        >
          {createJobMutation.isError && (
            <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
              <span>{(createJobMutation.error as Error)?.message || "Failed to create job"}</span>
            </div>
          )}

          {/* Title Field (Required) */}
          <div className="space-y-1.5">
            <label htmlFor="title" className="block text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Job Title <span className="text-red-400">*</span>
            </label>
            <input
              id="title"
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Backend Python Engineer"
              className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
            />
          </div>

          {/* Description Field (Required) */}
          <div className="space-y-1.5">
            <label htmlFor="description" className="block text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Job Description <span className="text-red-400">*</span>
            </label>
            <textarea
              id="description"
              required
              rows={5}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the responsibilities, qualifications, and core technical requirements..."
              className="w-full px-4 py-3 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all resize-y shadow-inner leading-relaxed"
            />
          </div>

          {/* Optional Fields Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Required Experience Years */}
            <div className="space-y-1.5">
              <label htmlFor="experience" className="block text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                Required Experience (Years)
              </label>
              <input
                id="experience"
                type="number"
                min={0}
                max={50}
                value={requiredExperienceYears}
                onChange={(e) => setRequiredExperienceYears(e.target.value)}
                placeholder="e.g. 5 (Optional)"
                className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
              />
              {isExpBlank && (
                <p className="text-[11px] text-amber-400/90 flex items-start gap-1 leading-tight mt-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>Warning: Left blank; required experience must then be stated in the description.</span>
                </p>
              )}
            </div>

            {/* Head Count */}
            <div className="space-y-1.5">
              <label htmlFor="headCount" className="block text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-zinc-400" />
                Target Head Count
              </label>
              <input
                id="headCount"
                type="number"
                min={1}
                max={100}
                value={headCount}
                onChange={(e) => setHeadCount(e.target.value)}
                placeholder="e.g. 2 (Optional)"
                className="w-full px-4 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 focus:border-blue-500 text-zinc-100 text-sm focus:outline-none transition-all shadow-inner"
              />
              {isHeadCountBlank && (
                <p className="text-[11px] text-amber-400/90 flex items-start gap-1 leading-tight mt-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>Warning: Left blank; target head count must then be stated in the description.</span>
                </p>
              )}
            </div>
          </div>

          <p className="text-[11px] text-zinc-500 italic">
            Skills extraction, semantic embedding, and ranking status are managed automatically by the backend.
          </p>

          <button
            type="submit"
            disabled={!title.trim() || !description.trim() || createJobMutation.isPending}
            className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 text-white font-medium text-sm transition-all shadow-lg shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
          >
            {createJobMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Creating Job...</span>
              </>
            ) : (
              <>
                <span>Continue to Resume Upload</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
