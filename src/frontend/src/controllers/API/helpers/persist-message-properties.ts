import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

/**
 * Persists message property updates to the backend.
 *
 * - Authenticated shareable playground: routes to /shared endpoint
 * - Anonymous/auto-login playground: skips (sessionStorage only, no DB persistence)
 * - Regular playground (flow editor): routes to standard endpoint
 */
export function persistMessageProperties(
  messageId: string,
  messagePayload: Record<string, unknown>,
): void {
  const isPlayground = useFlowStore.getState().playgroundPage;

  if (isPlayground) {
    // Authenticated playground: persist via shared endpoint
    if (isAuthenticatedPlayground()) {
      const sourceFlowId = useFlowsManagerStore.getState().currentFlowId;
      api
        .put(`${getURL("MESSAGES")}/shared/${messageId}`, messagePayload, {
          params: { source_flow_id: sourceFlowId },
        })
        .catch((err: unknown) => {
          console.warn("Failed to persist message properties (shared)", {
            messageId,
            error: err instanceof Error ? err.message : String(err),
          });
        });
    }
    // Anonymous/auto-login playground: skip — messages live in sessionStorage only
    return;
  }

  // Regular playground (flow editor): standard endpoint
  api
    .put(`${getURL("MESSAGES")}/${messageId}`, messagePayload)
    .catch((err: unknown) => {
      console.warn("Failed to persist message properties", {
        messageId,
        error: err instanceof Error ? err.message : String(err),
      });
    });
}
