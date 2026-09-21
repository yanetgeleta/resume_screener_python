export interface StreamErrorPayload {
  error: string;
  detail?: string;
  [key: string]: unknown;
}

export type OnChunkCallback = (chunk: string) => void;
export type OnErrorCallback = (errorPayload: StreamErrorPayload | string) => void;
export type OnDoneCallback = () => void;

export interface StreamChatOptions {
  jobId?: string | number;
  signal?: AbortSignal;
  apiBaseUrl?: string;
}

/**
 * Standalone SSE client function that streams assistant chat responses.
 *
 * Requirements:
 * - POST with `Authorization: Bearer <token>`
 * - Reads body using ReadableStream.getReader() + TextDecoder
 * - Internal buffer split on \n\n for complete SSE events only, keeping trailing partial data across reads
 * - For each complete data: line, parses as JSON and dispatches:
 *     - content -> onChunk
 *     - error -> onError (does not stop reading yet)
 *     - literal [DONE] -> stops reading and calls onDone
 * - Token is an explicit parameter, not pulled from a shared auth module.
 */
export async function streamChat(
  sessionId: string | number,
  query: string,
  token: string,
  onChunk: OnChunkCallback,
  onError: OnErrorCallback,
  onDone: OnDoneCallback,
  options?: StreamChatOptions
): Promise<void> {
  const jobId = options?.jobId;
  const signal = options?.signal;
  const baseUrl = options?.apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Target endpoint: POST /jobs/{jobId}/chat/{sessionId}/ (with fallback to /api/jobs/{jobId}/chat/{sessionId}/)
  const endpoint = jobId
    ? `${baseUrl}/jobs/${jobId}/chat/${sessionId}/`
    : `${baseUrl}/api/sessions/${sessionId}/stream/`;

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ query }),
      signal,
    });
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    onError({
      error: "Network error",
      detail: err instanceof Error ? err.message : String(err),
    });
    return;
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || JSON.stringify(errJson);
    } catch {
      // Ignored if response is not JSON
    }
    onError({
      error: `Request failed with status ${response.status}`,
      detail: errorDetail,
    });
    return;
  }

  if (!response.body) {
    onError({
      error: "Response body is empty or streaming is not supported.",
    });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Split on \n\n for complete SSE events only
      const parts = buffer.split("\n\n");
      // The last part is incomplete (trailing partial data), keep it in buffer
      buffer = parts.pop() ?? "";

      for (const eventBlock of parts) {
        const lines = eventBlock.split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) {
            continue;
          }

          const rawData = trimmed.slice(5).trim();

          // Check for terminal [DONE]
          if (rawData === "[DONE]") {
            onDone();
            return;
          }

          try {
            const parsed = JSON.parse(rawData);
            if (parsed && typeof parsed === "object") {
              if ("error" in parsed) {
                // Dispatch error but do not stop reading yet per spec
                onError(parsed);
              }
              if ("content" in parsed && typeof parsed.content === "string") {
                onChunk(parsed.content);
              }
            }
          } catch (jsonErr) {
            // If data is plain text or partial JSON
            console.warn("Could not parse SSE JSON line:", rawData, jsonErr);
          }
        }
      }
    }

    // Flush any remaining buffer if stream ended without [DONE]
    if (buffer.trim()) {
      const lines = buffer.trim().split("\n");
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data:")) {
          const rawData = trimmed.slice(5).trim();
          if (rawData === "[DONE]") {
            onDone();
            return;
          }
          try {
            const parsed = JSON.parse(rawData);
            if (parsed && typeof parsed === "object") {
              if ("error" in parsed) onError(parsed);
              if ("content" in parsed && typeof parsed.content === "string") {
                onChunk(parsed.content);
              }
            }
          } catch {
            // Ignore trailing unparseable
          }
        }
      }
    }

    onDone();
  } catch (readErr: unknown) {
    if (signal?.aborted) {
      return;
    }
    onError({
      error: "Stream interrupted",
      detail: readErr instanceof Error ? readErr.message : String(readErr),
    });
  } finally {
    reader.releaseLock();
  }
}
