import { useCallback, useEffect, useRef } from "react";
import { useGetDeploymentRun } from "@/controllers/API/queries/deployments/use-get-deployment-run";
import {
  type AssistantMessageUpdate,
  buildAssistantErrorUpdate,
  buildAssistantSuccessUpdate,
  isTerminalStatus,
} from "./deployment-chat-response";
import { extractThreadId } from "./watsonx-result-parsers";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 30;

interface UseDeploymentRunPollingParams {
  deploymentId: string;
  updateAssistantMessage: (id: string, update: AssistantMessageUpdate) => void;
  setThreadId: (threadId: string) => void;
  finishWaiting: () => void;
}

export function useDeploymentRunPolling({
  deploymentId,
  updateAssistantMessage,
  setThreadId,
  finishWaiting,
}: UseDeploymentRunPollingParams) {
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const { mutateAsync: getRun } = useGetDeploymentRun();

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (pollTimerRef.current !== null) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (runId: string, assistantMessageId: string) => {
      let attempts = 0;
      stopPolling();

      const schedulePoll = () => {
        pollTimerRef.current = setTimeout(async () => {
          if (!isMountedRef.current) {
            return;
          }

          attempts++;
          if (attempts > MAX_POLL_ATTEMPTS) {
            updateAssistantMessage(
              assistantMessageId,
              buildAssistantErrorUpdate("Run timed out. Please try again."),
            );
            finishWaiting();
            return;
          }

          try {
            const statusResponse = await getRun({
              deployment_id: deploymentId,
              run_id: runId,
            });

            if (!isMountedRef.current) {
              return;
            }

            const providerData = statusResponse.provider_data;
            const newThreadId = extractThreadId(
              providerData as Record<string, unknown> | null,
            );
            if (newThreadId) {
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
              updateAssistantMessage(
                assistantMessageId,
                buildAssistantErrorUpdate(
                  String(providerData?.last_error ?? "Run failed."),
                ),
              );
            } else {
              updateAssistantMessage(
                assistantMessageId,
                buildAssistantSuccessUpdate(providerData),
              );
            }

            finishWaiting();
          } catch (err: unknown) {
            if (!isMountedRef.current) {
              return;
            }

            const message =
              err instanceof Error ? err.message : "Failed to fetch run status";
            updateAssistantMessage(
              assistantMessageId,
              buildAssistantErrorUpdate(message),
            );
            finishWaiting();
          }
        }, POLL_INTERVAL_MS);
      };

      schedulePoll();
    },
    [
      deploymentId,
      finishWaiting,
      getRun,
      setThreadId,
      stopPolling,
      updateAssistantMessage,
    ],
  );

  return {
    startPolling,
    stopPolling,
  };
}
