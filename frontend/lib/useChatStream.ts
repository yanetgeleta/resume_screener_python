"use client";

import { useReducer, useRef, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamChat } from "./streamChat";
import { ChatMessage } from "./api";

export interface StreamState {
  status: "idle" | "streaming" | "error";
  partialText: string;
  errorDetail: string | null;
}

export type StreamAction =
  | { type: "CHUNK"; payload: string }
  | { type: "ERROR"; payload: string }
  | { type: "DONE" }
  | { type: "RESET" }
  | { type: "CLEAR_PARTIAL" };

export const initialStreamState: StreamState = {
  status: "idle",
  partialText: "",
  errorDetail: null,
};

export function streamReducer(
  state: StreamState,
  action: StreamAction
): StreamState {
  switch (action.type) {
    case "CHUNK":
      return {
        ...state,
        status: "streaming",
        partialText: state.partialText + action.payload,
        errorDetail: null,
      };
    case "ERROR":
      return {
        ...state,
        status: "error",
        errorDetail: action.payload,
      };
    case "DONE":
      // Do not clear partialText immediately — keep it rendered
      return {
        ...state,
        status: "idle",
      };
    case "CLEAR_PARTIAL":
      return {
        ...state,
        partialText: "",
      };
    case "RESET":
      return {
        status: "idle",
        partialText: "",
        errorDetail: null,
      };
    default:
      return state;
  }
}

export interface UseChatStreamProps {
  sessionId: string | number | null;
  jobId?: string | number;
  token?: string;
  onStreamComplete?: () => void;
}

export function useChatStream({
  sessionId,
  jobId,
  token = "",
  onStreamComplete,
}: UseChatStreamProps) {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState);
  const abortControllerRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();
  const currentSessionIdRef = useRef(sessionId);
  const accumulatedTextRef = useRef<string>("");

  // Update current session ref
  useEffect(() => {
    currentSessionIdRef.current = sessionId;
  }, [sessionId]);

  // Handle session switch or component unmount: abort any in-flight stream
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  // When sessionId changes mid-stream, abort previous controller and reset UI
  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // Stop rendering the old partial reply when navigating
    accumulatedTextRef.current = "";
    dispatch({ type: "RESET" });
  }, [sessionId]);

  const sendQuery = useCallback(
    async (queryText: string, customToken?: string) => {
      if (!sessionId || !queryText.trim()) return;

      // Abort any prior in-flight stream before starting a new one
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;
      accumulatedTextRef.current = "";

      dispatch({ type: "RESET" });

      // Optimistically append the user message into the cache immediately
      // This ensures the user message NEVER disappears from screen while waiting for the model
      const tempUserMsgId = -Date.now();
      queryClient.setQueryData<ChatMessage[]>(["messages", String(sessionId)], (old = []) => [
        ...old,
        {
          id: tempUserMsgId,
          session: Number(sessionId),
          role: "user",
          content: queryText.trim(),
          created_at: new Date().toISOString(),
        },
      ]);

      const activeToken =
        customToken ||
        token ||
        (typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "");

      try {
        await streamChat(
          sessionId,
          queryText.trim(),
          activeToken,
          (chunk) => {
            accumulatedTextRef.current += chunk;
            dispatch({ type: "CHUNK", payload: chunk });
          },
          (errorPayload) => {
            const msg =
              typeof errorPayload === "string"
                ? errorPayload
                : errorPayload.detail || errorPayload.error || "Streaming error";
            dispatch({ type: "ERROR", payload: msg });
          },
          async () => {
            const completedContent = accumulatedTextRef.current;
            abortControllerRef.current = null;

            // 1. Immediately reset partialText to eliminate any double AI bubble flicker
            dispatch({ type: "RESET" });

            // 2. Synchronously append the completed assistant message into the query cache
            if (completedContent.trim()) {
              queryClient.setQueryData<ChatMessage[]>(["messages", String(sessionId)], (old = []) => {
                if (old.some((m) => m.role === "assistant" && m.content === completedContent)) {
                  return old;
                }
                return [
                  ...old,
                  {
                    id: -(Date.now() + 1),
                    session: Number(sessionId),
                    role: "assistant",
                    content: completedContent,
                    created_at: new Date().toISOString(),
                  },
                ];
              });
            }

            // 3. Silently invalidate in background to sync database IDs without UI jump
            try {
              await queryClient.invalidateQueries({
                queryKey: ["messages", String(sessionId)],
              });
            } catch (err) {
              console.error("Failed to sync messages after stream:", err);
            } finally {
              onStreamComplete?.();
            }
          },
          {
            signal: controller.signal,
            jobId,
          }
        );
      } catch (err: unknown) {
        if (!controller.signal.aborted) {
          dispatch({
            type: "ERROR",
            payload: err instanceof Error ? err.message : String(err),
          });
        }
      }
    },
    [sessionId, jobId, token, queryClient, onStreamComplete]
  );

  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    dispatch({ type: "RESET" });
  }, []);

  return {
    state,
    sendQuery,
    abortStream,
    isStreaming: state.status === "streaming",
    partialText: state.partialText,
    errorDetail: state.errorDetail,
  };
}
