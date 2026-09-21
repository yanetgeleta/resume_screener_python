"use client";

import { useReducer, useRef, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamChat } from "./streamChat";

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

      dispatch({ type: "RESET" });

      const activeToken = customToken || token || (typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "");

      try {
        await streamChat(
          sessionId,
          queryText,
          activeToken,
          (chunk) => {
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
            dispatch({ type: "DONE" });
            abortControllerRef.current = null;

            // Invalidate message-history query, and only clear partialText once
            // that refetch resolves and the persisted message is available
            try {
              await queryClient.invalidateQueries({
                queryKey: ["messages", String(sessionId)],
              });
              await queryClient.refetchQueries({
                queryKey: ["messages", String(sessionId)],
              });
            } catch (err) {
              console.error("Failed to refetch messages after stream:", err);
            } finally {
              dispatch({ type: "CLEAR_PARTIAL" });
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
