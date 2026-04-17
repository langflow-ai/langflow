import { useCallback, useEffect, useRef, useState } from "react";
import { usePostDeploymentRun } from "@/controllers/API/queries/deployments/use-post-deployment-run";
import {
  buildAssistantErrorUpdate,
  buildAssistantSuccessUpdate,
  isTerminalStatus,
} from "./deployment-chat-response";
import type { ChatMessage } from "./types";
import { useDeploymentRunPolling } from "./use-deployment-run-polling";
import { extractThreadId } from "./watsonx-result-parsers";

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
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const { mutateAsync: postRun } = usePostDeploymentRun();

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

  const finishWaiting = useCallback(() => {
    if (isMountedRef.current) {
      setIsWaitingForResponse(false);
    }
  }, []);

  const { startPolling, stopPolling } = useDeploymentRunPolling({
    deploymentId,
    updateAssistantMessage,
    setThreadId,
    finishWaiting,
  });

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

      let runId: string | null = null;

      try {
        const createResponse = await postRun({
          deployment_id: deploymentId,
          provider_data: {
            input: text,
            ...(threadId ? { thread_id: threadId } : {}),
          },
        });

        const providerData = createResponse.provider_data;
        runId = providerData?.id ?? null;

        const newThreadId = extractThreadId(
          providerData as Record<string, unknown> | null,
        );
        if (newThreadId && isMountedRef.current) {
          setThreadId(newThreadId);
        }

        const alreadyTerminal =
          isTerminalStatus(providerData?.status) ||
          !!providerData?.completed_at;

        if (alreadyTerminal || !runId) {
          if (!runId && !alreadyTerminal) {
            updateAssistantMessage(
              assistantMsgId,
              buildAssistantErrorUpdate(
                "Run started but no run ID was returned.",
              ),
            );
          } else {
            updateAssistantMessage(
              assistantMsgId,
              buildAssistantSuccessUpdate(providerData),
            );
          }
          finishWaiting();
          return;
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to start run";
        updateAssistantMessage(
          assistantMsgId,
          buildAssistantErrorUpdate(message),
        );
        finishWaiting();
        return;
      }

      startPolling(runId, assistantMsgId);
    },
    [
      deploymentId,
      finishWaiting,
      isWaitingForResponse,
      postRun,
      providerId,
      startPolling,
      threadId,
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
