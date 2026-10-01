const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getAuthToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token") || "";
  }
  return "";
}

export function getRefreshToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("refresh_token") || "";
  }
  return "";
}

export function setAuthTokens(access: string, refresh?: string, email?: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("access_token", access);
    if (refresh) localStorage.setItem("refresh_token", refresh);
    if (email) localStorage.setItem("user_email", email);
    window.dispatchEvent(new Event("auth_token_changed"));
  }
}

export function clearAuthTokens(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_email");
    window.dispatchEvent(new Event("auth_token_changed"));
  }
}

export function getStoredUserEmail(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("user_email") || "";
  }
  return "";
}

let refreshPromise: Promise<string> | null = null;

export async function refreshTokenApi(): Promise<string> {
  const refresh = getRefreshToken();
  if (!refresh) {
    clearAuthTokens();
    throw new Error("No refresh token available");
  }

  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });

      if (!res.ok) {
        clearAuthTokens();
        throw new Error(`Token refresh failed with status ${res.status}`);
      }

      const data = await res.json();
      if (!data.access) {
        clearAuthTokens();
        throw new Error("Invalid token refresh response from server");
      }

      setAuthTokens(data.access, data.refresh || refresh);
      return data.access as string;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function loginApi(email: string, password: string): Promise<{ access: string; refresh: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let msg = `Login failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || JSON.stringify(err);
    } catch {
      // Ignore
    }
    throw new Error(msg);
  }
  const data = await res.json();
  setAuthTokens(data.access, data.refresh, email);
  return data;
}

export async function registerApi(
  email: string,
  company_name: string,
  password: string
): Promise<{ id: number; email: string; company_name: string }> {
  const res = await fetch(`${API_BASE_URL}/api/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, company_name, password }),
  });
  if (!res.ok) {
    let msg = `Registration failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || (Array.isArray(err.password) ? err.password.join(" ") : null) || JSON.stringify(err);
    } catch {
      // Ignore
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function logoutApi(): Promise<void> {
  const refresh = getRefreshToken();
  const token = getAuthToken();
  if (refresh) {
    try {
      await fetch(`${API_BASE_URL}/api/auth/logout/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ refresh }),
      });
    } catch {
      // Best-effort logout
    }
  }
  clearAuthTokens();
}

export interface JobApplicationField {
  id?: number;
  label: string;
  field_type: "text" | "textarea" | "number" | "boolean" | "single_choice";
  choices?: string[];
  required: boolean;
  order?: number;
}

export interface Job {
  id: number;
  title: string;
  description: string;
  required_experience_years: number | null;
  skills?: string[] | null;
  head_count: number | null;
  ranking_status: "not_started" | "computing" | "retrieval_done" | "done" | "failed";
  company?: number;
  company_name?: string;
  created_at: string;
  is_active: boolean;
  application_fields?: JobApplicationField[];
  application_count?: number;
  processed_application_count?: number;
}

export interface Applicant {
  id: number;
  email: string;
  full_name: string;
  phone_number: string;
  created_at?: string;
}

export interface ApplicantResume {
  id: number;
  original_filename: string;
  file: string;
  skills?: string[] | null;
  experience_years?: number | null;
  created_at: string;
}

export interface ApplicantApplication {
  id: number;
  job: {
    id: number;
    title: string;
    company_name?: string;
    created_at: string;
    is_active: boolean;
  };
  resume: number;
  resume_filename?: string;
  source: string;
  pipeline_status: "pending" | "processing" | "processed" | "failed";
  status: string;
  created_at: string;
}

// ---------------------------------------------------------
// Applicant Token Storage & Authentication
// ---------------------------------------------------------
export function getApplicantToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("applicant_access_token") || "";
  }
  return "";
}

export function getApplicantRefreshToken(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("applicant_refresh_token") || "";
  }
  return "";
}

export function setApplicantTokens(access: string, refresh?: string, applicant?: Applicant): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("applicant_access_token", access);
    if (refresh) localStorage.setItem("applicant_refresh_token", refresh);
    if (applicant) localStorage.setItem("applicant_user", JSON.stringify(applicant));
    window.dispatchEvent(new Event("applicant_auth_changed"));
  }
}

export function clearApplicantTokens(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("applicant_access_token");
    localStorage.removeItem("applicant_refresh_token");
    localStorage.removeItem("applicant_user");
    window.dispatchEvent(new Event("applicant_auth_changed"));
  }
}

export function getStoredApplicant(): Applicant | null {
  if (typeof window !== "undefined") {
    const raw = localStorage.getItem("applicant_user");
    if (raw) {
      try {
        return JSON.parse(raw) as Applicant;
      } catch {
        return null;
      }
    }
  }
  return null;
}

export interface ChatSession {
  id: number;
  job: number;
  job_title?: string;
  company: number;
  created_at: string;
  updated_at: string;
  messages?: ChatMessage[];
}

export interface ChatMessage {
  id: number;
  session: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export async function fetchWithAuth(url: string, options: RequestInit = {}) {
  let token = getAuthToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response = await fetch(url, {
    ...options,
    headers,
  });

  // If 401 Unauthorized and refresh token exists, attempt refresh & retry once
  if (response.status === 401 && getRefreshToken()) {
    try {
      const newToken = await refreshTokenApi();
      headers.set("Authorization", `Bearer ${newToken}`);
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch {
      // If refresh fails, fall through to error handling
    }
  }

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const err = await response.json();
      errorDetail = err.detail || err.error || JSON.stringify(err);
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// Jobs
export async function fetchJobs(): Promise<Job[]> {
  const data = await fetchWithAuth(`${API_BASE_URL}/api/jobs/`);
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function fetchPublicJobs(): Promise<Job[]> {
  const applicantToken = getApplicantToken();
  const headers: HeadersInit = {};
  if (applicantToken) {
    headers["Authorization"] = `Bearer ${applicantToken}`;
  }
  const res = await fetch(`${API_BASE_URL}/api/jobs/`, { headers });
  if (!res.ok) {
    let msg = `Failed to fetch jobs (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || JSON.stringify(err);
    } catch { }
    throw new Error(msg);
  }
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function fetchJob(jobId: string | number): Promise<Job> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/${jobId}/`);
}

export async function createJob(data: {
  title: string;
  description: string;
  required_experience_years?: number | null;
  head_count?: number | null;
  application_fields?: JobApplicationField[];
}): Promise<Job> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function seeResultApi(jobId: string | number): Promise<{
  session_id: number;
  created: boolean;
  has_messages: boolean;
  job_id: number;
  job_title: string;
}> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/${jobId}/see-result/`, {
    method: "POST",
  });
}

export async function searchJobsApi(query: string = ""): Promise<Job[]> {
  const url = `${API_BASE_URL}/api/jobs/search/?q=${encodeURIComponent(query)}`;
  const res = await fetch(url);
  if (!res.ok) {
    let msg = `Search failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || JSON.stringify(err);
    } catch { }
    throw new Error(msg);
  }
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function applyJobApi(
  jobId: string | number,
  formData: FormData
): Promise<{ status: string; application_id: number; pipeline_status: string; message: string }> {
  const applicantToken = getApplicantToken();
  const headers: Record<string, string> = {};
  if (applicantToken) {
    headers["Authorization"] = `Bearer ${applicantToken}`;
  }

  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/apply/`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `Application submission failed (${response.status})`;
    try {
      const err = await response.json();
      errorDetail = err.error || err.detail || (Array.isArray(err.password) ? err.password.join(" ") : null) || JSON.stringify(err);
    } catch { }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ---------------------------------------------------------
// Applicant Auth & Portal APIs
// ---------------------------------------------------------
export async function applicantSignupApi(payload: {
  email: string;
  password: string;
  full_name: string;
  phone_number: string;
}): Promise<{ applicant: Applicant; tokens: { access: string; refresh: string } }> {
  const res = await fetch(`${API_BASE_URL}/api/applicants/signup/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = `Sign up failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || (Array.isArray(err.password) ? err.password.join(" ") : null) || JSON.stringify(err);
    } catch { }
    throw new Error(msg);
  }

  const data = await res.json();
  setApplicantTokens(data.tokens.access, data.tokens.refresh, data.applicant);
  return data;
}

export async function applicantLoginApi(payload: {
  email: string;
  password: string;
}): Promise<{ applicant: Applicant; tokens: { access: string; refresh: string } }> {
  const res = await fetch(`${API_BASE_URL}/api/applicants/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = `Login failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || JSON.stringify(err);
    } catch { }
    throw new Error(msg);
  }

  const data = await res.json();
  setApplicantTokens(data.tokens.access, data.tokens.refresh, data.applicant);
  return data;
}

export async function applicantGetResumesApi(): Promise<ApplicantResume[]> {
  const token = getApplicantToken();
  if (!token) return [];

  const res = await fetch(`${API_BASE_URL}/api/applicants/me/resumes/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function applicantUploadResumeApi(file: File): Promise<ApplicantResume> {
  const token = getApplicantToken();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE_URL}/api/applicants/me/resumes/`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    let msg = `Upload failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.error || JSON.stringify(err);
    } catch { }
    throw new Error(msg);
  }

  return res.json();
}

export async function applicantGetApplicationsApi(): Promise<ApplicantApplication[]> {
  const token = getApplicantToken();
  if (!token) return [];

  const res = await fetch(`${API_BASE_URL}/api/applicants/me/applications/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return [];
  const data = await res.json();
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function recomputeJobRankings(jobId: string | number): Promise<{ detail: string; ranking_status: string }> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/${jobId}/recompute/`, {
    method: "POST",
  });
}

// Sessions
export async function fetchSessions(jobId: string | number): Promise<ChatSession[]> {
  const data = await fetchWithAuth(`${API_BASE_URL}/api/sessions/?job_id=${jobId}`);
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export async function createSession(jobId: string | number): Promise<ChatSession> {
  return fetchWithAuth(`${API_BASE_URL}/api/sessions/`, {
    method: "POST",
    body: JSON.stringify({ job: Number(jobId) }),
  });
}

// Messages
export async function fetchMessages(sessionId: string | number): Promise<ChatMessage[]> {
  const data = await fetchWithAuth(`${API_BASE_URL}/api/sessions/${sessionId}/messages/`);
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

// Resume Upload
export async function uploadResumes(jobId: string | number, files: File[]): Promise<any> {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append("job_id", String(jobId));
  formData.append("job", String(jobId));
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch(`${API_BASE_URL}/api/resumes/`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `Upload failed (${response.status})`;
    try {
      const err = await response.json();
      errorDetail = err.detail || err.error || JSON.stringify(err);
    } catch {
      // Ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}
