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

export function setAuthTokens(access: string, refresh: string, email?: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    if (email) localStorage.setItem("user_email", email);
  }
}

export function clearAuthTokens(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_email");
  }
}

export function getStoredUserEmail(): string {
  if (typeof window !== "undefined") {
    return localStorage.getItem("user_email") || "";
  }
  return "";
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

export interface Job {
  id: number;
  title: string;
  description: string;
  required_experience_years: number | null;
  skills?: string[] | null;
  head_count: number | null;
  ranking_status: "not_started" | "computing" | "retrieval_done" | "done" | "failed";
  company?: number;
  created_at: string;
  is_active: boolean;
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
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

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

export async function fetchJob(jobId: string | number): Promise<Job> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/${jobId}/`);
}

export async function createJob(data: {
  title: string;
  description: string;
  required_experience_years?: number | null;
  head_count?: number | null;
}): Promise<Job> {
  return fetchWithAuth(`${API_BASE_URL}/api/jobs/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
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
