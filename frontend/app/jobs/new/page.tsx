"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import {
  Briefcase,
  AlertCircle,
  ArrowRight,
  Loader2,
  Clock,
  Users,
  Plus,
  Trash2,
  CheckCircle2,
  UploadCloud,
  FileQuestion,
  HelpCircle,
} from "lucide-react";
import { createJob, Job, JobApplicationField } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";

interface DynamicFieldDraft {
  id: string;
  label: string;
  field_type: "text" | "textarea" | "number" | "boolean" | "single_choice";
  choices_str: string;
  required: boolean;
}

export default function NewJobPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [requiredExperienceYears, setRequiredExperienceYears] = useState<string>("");
  const [headCount, setHeadCount] = useState<string>("");

  // Dynamic application fields builder
  const [dynamicFields, setDynamicFields] = useState<DynamicFieldDraft[]>([]);
  const [createdJob, setCreatedJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.push("/login?redirect=/jobs/new");
    }
  }, [isAuthenticated, isAuthLoading, router]);

  const addField = () => {
    setDynamicFields((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substring(2, 9),
        label: "",
        field_type: "text",
        choices_str: "",
        required: false,
      },
    ]);
  };

  const removeField = (id: string) => {
    setDynamicFields((prev) => prev.filter((f) => f.id !== id));
  };

  const updateField = (id: string, updates: Partial<DynamicFieldDraft>) => {
    setDynamicFields((prev) =>
      prev.map((f) => (f.id === id ? { ...f, ...updates } : f))
    );
  };

  const createJobMutation = useMutation({
    mutationFn: async () => {
      const expYears =
        requiredExperienceYears.trim() !== "" ? parseInt(requiredExperienceYears, 10) : null;
      const count = headCount.trim() !== "" ? parseInt(headCount, 10) : null;

      const formattedFields: JobApplicationField[] = dynamicFields
        .filter((f) => f.label.trim())
        .map((f, idx) => ({
          label: f.label.trim(),
          field_type: f.field_type,
          choices:
            f.field_type === "single_choice"
              ? f.choices_str
                  .split(",")
                  .map((c) => c.trim())
                  .filter(Boolean)
              : [],
          required: f.required,
          order: idx,
        }));

      return createJob({
        title: title.trim(),
        description: description.trim(),
        required_experience_years: expYears,
        head_count: count,
        application_fields: formattedFields,
      });
    },
    onSuccess: (newJob) => {
      // Per Phase 8.2: Submit -> confirmation message, no forced redirect anywhere!
      setCreatedJob(newJob);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    createJobMutation.mutate();
  };

  const resetForm = () => {
    setTitle("");
    setDescription("");
    setRequiredExperienceYears("");
    setHeadCount("");
    setDynamicFields([]);
    setCreatedJob(null);
  };

  const isExpBlank = requiredExperienceYears.trim() === "";
  const isHeadCountBlank = headCount.trim() === "";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl w-full mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto shadow-lg shadow-blue-500/10">
            <Briefcase className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Create a New Job Opening
          </h1>
          <p className="text-sm text-zinc-400 max-w-md mx-auto">
            Configure job specifications and custom applicant questions. Our AI pipeline handles embedding, extraction, and candidate ranking.
          </p>
        </div>

        {/* Confirmation Message State (Phase 8.2: No forced redirect) */}
        {createdJob ? (
          <div className="p-8 rounded-2xl bg-zinc-900/80 border border-emerald-500/40 shadow-2xl backdrop-blur-xl text-center space-y-6">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div className="space-y-2">
              <h2 className="text-xl font-bold text-zinc-100">
                Job Opening Created Successfully!
              </h2>
              <p className="text-sm text-zinc-300 font-medium">{createdJob.title}</p>
              <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                This job is now published and accepting candidate applications. You can optionally bulk-upload resumes on-demand or return to your dashboard.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <Link
                href={`/jobs/${createdJob.id}/upload`}
                className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-all shadow-md shadow-blue-600/20"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload Resumes (On-Demand)</span>
              </Link>
              <Link
                href="/"
                className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-xs transition-all"
              >
                <span>Back to Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <button
              onClick={resetForm}
              className="text-xs text-zinc-500 hover:text-zinc-300 underline underline-offset-4 cursor-pointer"
            >
              Create another job opening
            </button>
          </div>
        ) : (
          /* Job Form */
          <form
            onSubmit={handleSubmit}
            className="p-8 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 shadow-2xl backdrop-blur-xl space-y-6"
          >
            {createJobMutation.isError && (
              <div className="p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>
                  {(createJobMutation.error as Error)?.message || "Failed to create job"}
                </span>
              </div>
            )}

            {/* Title Field (Required) */}
            <div className="space-y-1.5">
              <label
                htmlFor="title"
                className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
              >
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
              <label
                htmlFor="description"
                className="block text-xs font-semibold uppercase tracking-wider text-zinc-300"
              >
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

            {/* Experience & Headcount Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="experience"
                  className="block text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5"
                >
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
                    <span>Optional; if blank, requirements inferred from text.</span>
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="headCount"
                  className="block text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5"
                >
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
                    <span>Defaults to 5 candidates in ranking if unspecified.</span>
                  </p>
                )}
              </div>
            </div>

            {/* Job Application Custom Fields Builder (Phase 8.1 & 8.2) */}
            <div className="pt-4 border-t border-zinc-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
                    <FileQuestion className="w-4 h-4 text-blue-400" />
                    <span>Custom Application Questions</span>
                  </h3>
                  <p className="text-[11px] text-zinc-400">
                    Add custom questions for applicants (Full name & resume are always included).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={addField}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600/10 hover:bg-blue-600/20 border border-blue-500/30 text-blue-400 text-xs font-medium transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Question</span>
                </button>
              </div>

              {dynamicFields.length === 0 ? (
                <div className="p-4 rounded-xl border border-dashed border-zinc-800 text-center text-xs text-zinc-500">
                  No custom questions added. Only standard candidate profile + resume will be required.
                </div>
              ) : (
                <div className="space-y-3">
                  {dynamicFields.map((field, idx) => (
                    <div
                      key={field.id}
                      className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800/90 space-y-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 space-y-2">
                          <input
                            type="text"
                            required
                            placeholder={`Question #${idx + 1} Label (e.g. Years of Django experience, Portfolio URL)`}
                            value={field.label}
                            onChange={(e) => updateField(field.id, { label: e.target.value })}
                            className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-100 text-xs focus:outline-none focus:border-blue-500"
                          />

                          <div className="flex flex-wrap items-center gap-3">
                            <select
                              value={field.field_type}
                              onChange={(e) =>
                                updateField(field.id, {
                                  field_type: e.target.value as any,
                                })
                              }
                              className="px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-200 text-xs focus:outline-none"
                            >
                              <option value="text">Short Text</option>
                              <option value="textarea">Paragraph Text</option>
                              <option value="number">Number</option>
                              <option value="boolean">Yes / No Checkbox</option>
                              <option value="single_choice">Single Choice (Dropdown)</option>
                            </select>

                            <label className="flex items-center gap-1.5 text-xs text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={field.required}
                                onChange={(e) =>
                                  updateField(field.id, { required: e.target.checked })
                                }
                                className="rounded border-zinc-700 text-blue-600 focus:ring-0"
                              />
                              <span>Required</span>
                            </label>
                          </div>

                          {field.field_type === "single_choice" && (
                            <input
                              type="text"
                              placeholder="Comma-separated options (e.g. Remote, Hybrid, Onsite)"
                              value={field.choices_str}
                              onChange={(e) =>
                                updateField(field.id, { choices_str: e.target.value })
                              }
                              className="w-full px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-100 text-xs focus:outline-none focus:border-blue-500"
                            />
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => removeField(field.id)}
                          className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                          title="Remove question"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={!title.trim() || !description.trim() || createJobMutation.isPending}
              className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:from-blue-700 text-white font-medium text-sm transition-all shadow-lg shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
            >
              {createJobMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Publishing Job Opening...</span>
                </>
              ) : (
                <>
                  <span>Publish Job Opening</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
