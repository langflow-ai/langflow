import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

/**
 * Persists message property updates to the backend.
 * Routes to the shared endpoint for authenticated shareable playground,
 * or the standard endpoint otherwise.
 */
export function persistMessageProperties(
  messageId: string,
  messagePayload: Record<string, unknown>,
): void {
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
  } else {
    api
      .put(`${getURL("MESSAGES")}/${messageId}`, messagePayload)
      .catch((err: unknown) => {
        console.warn("Failed to persist message properties", {
          messageId,
          error: err instanceof Error ? err.message : String(err),
        });
      });
  }
}
