"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Briefcase,
  Building2,
  Clock,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  FileText,
  UploadCloud,
  Loader2,
  Send,
  UserCheck,
  Users,
  LogOut,
} from "lucide-react";
import {
  fetchJob,
  applyJobApi,
  applicantGetResumesApi,
  applicantGetApplicationsApi,
  getStoredApplicant,
  getApplicantToken,
  clearApplicantTokens,
  ApplicantResume,
  ApplicantApplication,
  Job,
} from "@/lib/api";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params?.jobId as string;

  const [applicant, setApplicant] = useState(() => getStoredApplicant());
  const [applicantToken, setApplicantToken] = useState<string | null>(() => getApplicantToken());

  // Fixed fields
  const [fullName, setFullName] = useState(applicant?.full_name || "");
  const [email, setEmail] = useState(applicant?.email || "");
  const [phone, setPhone] = useState(applicant?.phone_number || "");
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  // Dynamic answers: key = field.id, val = string
  const [dynamicAnswers, setDynamicAnswers] = useState<Record<number, string>>({});
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [applicationId, setApplicationId] = useState<number | null>(null);

  // Listen for applicant auth changes
  useEffect(() => {
    const handleAuthChange = () => {
      const cur = getStoredApplicant();
      setApplicant(cur);
      setApplicantToken(getApplicantToken());
      if (cur) {
        setFullName(cur.full_name);
        setEmail(cur.email);
        setPhone(cur.phone_number);
      }
    };
    window.addEventListener("applicant_auth_changed", handleAuthChange);
    return () => window.removeEventListener("applicant_auth_changed", handleAuthChange);
  }, []);

  const {
    data: job,
    isLoading: isJobLoading,
    error: jobError,
  } = useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
    enabled: !!jobId,
  });

  // If authenticated applicant, fetch their saved resumes for the picker
  const { data: savedResumes = [] } = useQuery<ApplicantResume[]>({
    queryKey: ["applicant-resumes", applicantToken],
    queryFn: applicantGetResumesApi,
    enabled: !!applicantToken,
  });

  // If authenticated applicant, fetch their existing applications to detect already applied state
  const { data: myApplications = [] } = useQuery<ApplicantApplication[]>({
    queryKey: ["applicant-applications", applicantToken],
    queryFn: applicantGetApplicationsApi,
    enabled: !!applicantToken,
  });

  const existingApplication = applicantToken
    ? myApplications.find((app) => String(app.job?.id) === String(jobId))
    : null;

  const applyMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      if (!applicant) {
        formData.append("full_name", fullName.trim());
        formData.append("email", email.trim());
        formData.append("phone_number", phone.trim());
      }

      if (selectedResumeId) {
        formData.append("resume_id", selectedResumeId);
      } else if (resumeFile) {
        formData.append("file", resumeFile);
      }

      // Dynamic field answers
      const answersPayload = Object.entries(dynamicAnswers).map(([fId, val]) => ({
        field_id: Number(fId),
        value: val,
      }));
      formData.append("answers", JSON.stringify(answersPayload));

      return applyJobApi(jobId, formData);
    },
    onSuccess: (data) => {
      setIsSubmitted(true);
      setApplicationId(data.application_id);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!applicant) {
      if (!fullName.trim() || !email.trim() || !phone.trim()) {
        alert("Please complete all personal contact information.");
        return;
      }
      if (!resumeFile && !selectedResumeId) {
        alert("Please upload your resume in PDF format.");
        return;
      }
    } else {
      if (!selectedResumeId && !resumeFile) {
        alert("Please select a saved resume or upload a new one.");
        return;
      }
    }
    applyMutation.mutate();
  };

  if (isJobLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-6 text-sm text-zinc-500">
        Loading job opening details...
      </div>
    );
  }

  if (jobError || !job) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center p-6 space-y-4">
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-sm">
          Job opening not found or inactive.
        </div>
        <Link href="/jobs" className="text-xs text-blue-400 hover:underline">
          Return to Job Marketplace
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top Navbar */}
      <header className="h-16 border-b border-zinc-800/80 px-6 flex items-center justify-between bg-zinc-900/40 backdrop-blur-md sticky top-0 z-40">
        <Link
          href="/jobs"
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Marketplace</span>
        </Link>

        {applicant ? (
          <div className="flex items-center gap-3">
            <Link
              href="/applicant/applications"
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              My Applications
            </Link>
            <button
              onClick={() => {
                clearApplicantTokens();
                setApplicant(null);
                setApplicantToken(null);
                router.push("/jobs");
              }}
              className="p-1.5 rounded-xl text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <Link
            href="/applicant/login"
            className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            Sign In
          </Link>
        )}
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto p-6 sm:p-10 space-y-8">
        {/* Job Header Card */}
        <div className="p-8 rounded-3xl bg-zinc-900/60 border border-zinc-800/80 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-white tracking-tight">{job.title}</h1>
              {job.company_name && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-800 text-zinc-300 text-xs font-medium border border-zinc-700">
                  <Building2 className="w-3.5 h-3.5 text-zinc-400" />
                  <span>{job.company_name}</span>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3 shrink-0">
              {job.head_count !== null && job.head_count !== undefined && (
                <span className="flex items-center gap-1.5 text-xs text-zinc-400">
                  <Users className="w-4 h-4 text-emerald-400" />
                  <span>Target: <strong className="text-zinc-200 font-medium">{job.head_count}</strong></span>
                </span>
              )}
              {job.required_experience_years !== null && (
                <span className="flex items-center gap-1 text-xs text-zinc-400">
                  <Clock className="w-4 h-4 text-blue-400" />
                  <span>{job.required_experience_years}+ years experience</span>
                </span>
              )}
            </div>
          </div>

          <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-line pt-2 border-t border-zinc-800/60">
            {job.description}
          </p>

          {Array.isArray(job.skills) && job.skills.length > 0 && (
            <div className="pt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs text-zinc-500 font-medium">Desired Skills:</span>
              {job.skills.map((s, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-0.5 rounded-lg bg-blue-950/40 border border-blue-800/40 text-blue-300 text-xs"
                >
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Application Submission Form or Success View / Already Applied */}
        {isSubmitted || existingApplication ? (
          /* Confirmation / Already Applied state */
          <div className="p-8 sm:p-10 rounded-3xl bg-zinc-900/70 border border-emerald-500/40 text-center space-y-6 shadow-2xl backdrop-blur-xl">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl font-bold text-white">
                {existingApplication && !isSubmitted
                  ? "You've Already Applied to this Position"
                  : "Application Submitted!"}
              </h2>
              <p className="text-sm text-zinc-300">
                {existingApplication && !isSubmitted
                  ? `You have already submitted an application for ${job.title}.`
                  : `Thank you for applying to ${job.title}.`}
              </p>
              <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                {existingApplication && !isSubmitted
                  ? `Application ID #${existingApplication.id} • Status: ${(existingApplication.pipeline_status || "queued").toUpperCase()} • Submitted on ${new Date(existingApplication.created_at).toLocaleDateString()}`
                  : `Your application (ID #${applicationId}) has been received and queued for screening. You do not need to wait on this page.`}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              {applicant ? (
                <Link
                  href="/applicant/applications"
                  className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow-md shadow-blue-600/20 transition-all"
                >
                  View in My Applications
                </Link>
              ) : (
                <Link
                  href="/applicant/signup"
                  className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs shadow-md shadow-blue-600/20 transition-all"
                >
                  Create Applicant Account to Track Status
                </Link>
              )}
              <Link
                href="/jobs"
                className="px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-xs transition-colors"
              >
                Browse More Jobs
              </Link>
            </div>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="p-8 rounded-3xl bg-zinc-900/60 border border-zinc-800/80 shadow-2xl backdrop-blur-xl space-y-6"
          >
            <div className="border-b border-zinc-800/80 pb-4">
              <h2 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                <Send className="w-4 h-4 text-blue-400" />
                <span>Apply for this Position</span>
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                {applicant ? (
                  <span className="text-blue-400 flex items-center gap-1">
                    <UserCheck className="w-3.5 h-3.5" />
                    Applying as {applicant.full_name} ({applicant.email})
                  </span>
                ) : (
                  <span>
                    Applying as guest. Fill out your contact details below or{" "}
                    <Link href="/applicant/login" className="text-blue-400 hover:underline">
                      sign in
                    </Link>{" "}
                    to use saved resumes.
                  </span>
                )}
              </p>
            </div>

            {applyMutation.isError && (
              <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>
                  {(applyMutation.error as Error)?.message || "Failed to submit application"}
                </span>
              </div>
            )}

            {/* Contact Information (Fixed non-configurable inputs) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-300">
                  Full Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-300">
                  Email Address <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@example.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-300">
                  Phone Number <span className="text-red-400">*</span>
                </label>
                <input
                  type="tel"
                  required
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                />
              </div>
            </div>

            {/* Resume Selection / Upload */}
            <div className="space-y-3 pt-2 border-t border-zinc-800/60">
              <label className="block text-xs font-semibold text-zinc-300">
                Resume (PDF) <span className="text-red-400">*</span>
              </label>

              {applicant && savedResumes.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] text-zinc-400 font-medium">
                    Select a previously saved resume:
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {savedResumes.map((r) => (
                      <button
                        type="button"
                        key={r.id}
                        onClick={() => {
                          setSelectedResumeId(String(r.id));
                          setResumeFile(null);
                        }}
                        className={`p-3 rounded-xl border text-left flex items-center gap-3 transition-all cursor-pointer ${selectedResumeId === String(r.id)
                          ? "bg-blue-600/10 border-blue-500 text-white"
                          : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700"
                          }`}
                      >
                        <FileText
                          className={`w-4 h-4 shrink-0 ${selectedResumeId === String(r.id) ? "text-blue-400" : "text-zinc-500"
                            }`}
                        />
                        <div className="min-w-0 flex-1 truncate">
                          <div className="text-xs font-medium truncate">{r.original_filename}</div>
                          <div className="text-[10px] text-zinc-500">
                            Uploaded {new Date(r.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="text-[11px] text-zinc-500 text-center py-1">or</div>
                </div>
              )}

              {/* Upload new PDF */}
              <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <UploadCloud className="w-5 h-5 text-blue-400 shrink-0" />
                  <div>
                    <div className="text-xs font-medium text-zinc-200">
                      {resumeFile ? resumeFile.name : "Upload New Resume (PDF, max 10MB)"}
                    </div>
                    <div className="text-[10px] text-zinc-500">
                      Standard text extractable PDF file
                    </div>
                  </div>
                </div>
                <label className="px-3.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium transition-colors cursor-pointer shrink-0">
                  <span>{resumeFile ? "Change File" : "Browse PDF"}</span>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setResumeFile(file);
                        setSelectedResumeId("");
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            {/* Dynamic JobApplicationFields */}
            {Array.isArray(job.application_fields) && job.application_fields.length > 0 && (
              <div className="pt-4 border-t border-zinc-800/60 space-y-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                  Additional Application Questions
                </h3>

                <div className="space-y-4">
                  {job.application_fields.map((field) => (
                    <div key={field.id} className="space-y-1.5">
                      <label className="block text-xs font-medium text-zinc-300">
                        {field.label}{" "}
                        {field.required && <span className="text-red-400">*</span>}
                      </label>

                      {field.field_type === "textarea" ? (
                        <textarea
                          required={field.required}
                          rows={3}
                          value={dynamicAnswers[field.id!] || ""}
                          onChange={(e) =>
                            setDynamicAnswers((prev) => ({
                              ...prev,
                              [field.id!]: e.target.value,
                            }))
                          }
                          className="w-full px-3.5 py-2 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                        />
                      ) : field.field_type === "number" ? (
                        <input
                          type="number"
                          required={field.required}
                          value={dynamicAnswers[field.id!] || ""}
                          onChange={(e) =>
                            setDynamicAnswers((prev) => ({
                              ...prev,
                              [field.id!]: e.target.value,
                            }))
                          }
                          className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                        />
                      ) : field.field_type === "boolean" ? (
                        <div className="flex items-center gap-6 pt-1">
                          <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                            <input
                              type="radio"
                              name={`field_${field.id}`}
                              required={field.required}
                              checked={dynamicAnswers[field.id!] === "true"}
                              onChange={() =>
                                setDynamicAnswers((prev) => ({
                                  ...prev,
                                  [field.id!]: "true",
                                }))
                              }
                              className="text-blue-600 border-zinc-700 focus:ring-blue-500/20 bg-zinc-950 cursor-pointer"
                            />
                            <span>Yes</span>
                          </label>
                          <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                            <input
                              type="radio"
                              name={`field_${field.id}`}
                              required={field.required}
                              checked={dynamicAnswers[field.id!] === "false"}
                              onChange={() =>
                                setDynamicAnswers((prev) => ({
                                  ...prev,
                                  [field.id!]: "false",
                                }))
                              }
                              className="text-blue-600 border-zinc-700 focus:ring-blue-500/20 bg-zinc-950 cursor-pointer"
                            />
                            <span>No</span>
                          </label>
                        </div>
                      ) : field.field_type === "single_choice" ? (
                        <select
                          required={field.required}
                          value={dynamicAnswers[field.id!] || ""}
                          onChange={(e) =>
                            setDynamicAnswers((prev) => ({
                              ...prev,
                              [field.id!]: e.target.value,
                            }))
                          }
                          className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500"
                        >
                          <option value="">Select an option...</option>
                          {field.choices?.map((c, cIdx) => (
                            <option key={cIdx} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          required={field.required}
                          value={dynamicAnswers[field.id!] || ""}
                          onChange={(e) =>
                            setDynamicAnswers((prev) => ({
                              ...prev,
                              [field.id!]: e.target.value,
                            }))
                          }
                          className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-700/80 text-zinc-100 text-xs focus:outline-none focus:border-blue-500 shadow-inner"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={applyMutation.isPending}
              className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-sm transition-all shadow-lg shadow-blue-600/20 disabled:opacity-50 cursor-pointer"
            >
              {applyMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Submitting Application...</span>
                </>
              ) : (
                <>
                  <span>Submit Application</span>
                  <Send className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
