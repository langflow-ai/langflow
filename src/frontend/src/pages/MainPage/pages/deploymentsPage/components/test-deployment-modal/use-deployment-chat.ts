import { useCallback, useEffect, useRef, useState } from "react";
import { useGetDeploymentExecution } from "@/controllers/API/queries/deployments/use-get-deployment-execution";
import { usePostDeploymentExecution } from "@/controllers/API/queries/deployments/use-post-deployment-execution";
import type { ChatMessage } from "./types";
import {
  extractTextFromResult,
  extractThreadId,
  extractToolTraces,
} from "./watsonx-result-parsers";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 30;

const TERMINAL_STATUSES = new Set([
  "completed",
  "success",
  "failed",
  "error",
  "cancelled",
]);

function isTerminalStatus(status: string | null | undefined): boolean {
  return !!status && TERMINAL_STATUSES.has(status.toLowerCase());
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

interface UseDeploymentChatOptions {
  providerId: string;
  deploymentId: string;
}

export function useDeploymentChat({
  providerId,
  deploymentId,
}: UseDeploymentChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const { mutateAsync: postExecution } = usePostDeploymentExecution();
  const { mutateAsync: getExecution } = useGetDeploymentExecution();

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const updateAssistantMessage = useCallback(
    (
      id: string,
      update: Partial<
        Pick<ChatMessage, "content" | "toolTraces" | "isLoading" | "error">
      >,
    ) => {
      if (!isMountedRef.current) return;
      setMessages((prev) =>
        prev.map((msg) => (msg.id === id ? { ...msg, ...update } : msg)),
      );
    },
    [],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isWaitingForResponse || !deploymentId || !providerId)
        return;

      const userMsgId = generateId();
      const assistantMsgId = generateId();

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content: text },
        { id: assistantMsgId, role: "assistant", content: "", isLoading: true },
      ]);
      setIsWaitingForResponse(true);

      let executionId: string | null = null;

      try {
        const createResponse = await postExecution({
          deployment_id: deploymentId,
          provider_data: {
            input: text,
            ...(threadId ? { thread_id: threadId } : {}),
          },
        });

        const providerData = createResponse.provider_data;
        executionId = providerData?.execution_id ?? null;

        const newThreadId = extractThreadId(
          providerData as Record<string, unknown> | null,
        );
        if (newThreadId && isMountedRef.current) {
          setThreadId(newThreadId);
        }

        const alreadyTerminal =
          isTerminalStatus(providerData?.status) ||
          !!providerData?.completed_at;

        if (alreadyTerminal || !executionId) {
          if (!executionId && !alreadyTerminal) {
            updateAssistantMessage(assistantMsgId, {
              content: "",
              isLoading: false,
              error: "Execution started but no execution ID was returned.",
            });
          } else {
            const result = providerData?.result as
              | Record<string, unknown>
              | null
              | undefined;
            const replyText =
              extractTextFromResult(result) ||
              (typeof providerData?.status === "string"
                ? providerData.status
                : "Done.");
            const toolTraces = extractToolTraces(result);

            updateAssistantMessage(assistantMsgId, {
              content: replyText,
              toolTraces: toolTraces.length > 0 ? toolTraces : undefined,
              isLoading: false,
            });
          }
          if (isMountedRef.current) setIsWaitingForResponse(false);
          return;
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to start execution";
        updateAssistantMessage(assistantMsgId, {
          content: "",
          isLoading: false,
          error: message,
        });
        if (isMountedRef.current) setIsWaitingForResponse(false);
        return;
      }

      // Poll for completion using recursive setTimeout to avoid overlapping requests
      let attempts = 0;
      stopPolling();

      const currentExecutionId = executionId as string;

      const schedulePoll = () => {
        pollTimerRef.current = setTimeout(async () => {
          if (!isMountedRef.current) return;

          attempts++;

          if (attempts > MAX_POLL_ATTEMPTS) {
            updateAssistantMessage(assistantMsgId, {
              content: "",
              isLoading: false,
              error: "Execution timed out. Please try again.",
            });
            if (isMountedRef.current) setIsWaitingForResponse(false);
            return;
          }

          try {
            const statusResponse = await getExecution({
              deployment_id: deploymentId,
              execution_id: currentExecutionId,
            });

            if (!isMountedRef.current) return;

            const providerData = statusResponse.provider_data;

            const newThreadId = extractThreadId(
              providerData as Record<string, unknown> | null,
            );
            if (newThreadId && isMountedRef.current) {
              setThreadId(newThreadId);
            }

            const isTerminal =
              isTerminalStatus(providerData?.status) ||
              !!providerData?.completed_at ||
              !!providerData?.failed_at ||
              !!providerData?.cancelled_at;

            if (!isTerminal) {
              schedulePoll();
              return;
            }

            if (providerData?.failed_at || providerData?.cancelled_at) {
              const errorMsg = providerData?.last_error ?? "Execution failed.";
              updateAssistantMessage(assistantMsgId, {
                content: "",
                isLoading: false,
                error: String(errorMsg),
              });
            } else {
              const result = providerData?.result as
                | Record<string, unknown>
                | null
                | undefined;
              const replyText =
                extractTextFromResult(result) ||
                (typeof providerData?.status === "string"
                  ? providerData.status
                  : "Done.");
              const toolTraces = extractToolTraces(result);

              updateAssistantMessage(assistantMsgId, {
                content: replyText,
                toolTraces: toolTraces.length > 0 ? toolTraces : undefined,
                isLoading: false,
              });
            }

            if (isMountedRef.current) setIsWaitingForResponse(false);
          } catch (err: unknown) {
            if (!isMountedRef.current) return;
            const message =
              err instanceof Error
                ? err.message
                : "Failed to fetch execution status";
            updateAssistantMessage(assistantMsgId, {
              content: "",
              isLoading: false,
              error: message,
            });
            if (isMountedRef.current) setIsWaitingForResponse(false);
          }
        }, POLL_INTERVAL_MS);
      };

      schedulePoll();
    },
    [
      isWaitingForResponse,
      threadId,
      providerId,
      deploymentId,
      postExecution,
      getExecution,
      stopPolling,
      updateAssistantMessage,
    ],
  );

  const resetChat = useCallback(() => {
    stopPolling();
    setMessages([]);
    setThreadId(null);
    setIsWaitingForResponse(false);
  }, [stopPolling]);

  return { messages, isWaitingForResponse, sendMessage, resetChat };
}
