import { useEffect } from "react";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useGetPendingWorkflows } from "@/controllers/API/queries/workflows/use-get-pending-workflows";
import { useHitlStore } from "@/stores/hitlStore";
import type { Message } from "@/types/messages";
import {
  findHumanInputContent,
  registerResumeContext,
} from "./human-input-card";

/**
 * Restore the canvas awaiting-input badge after a reload (LE-1603 reconnect): the
 * pending state lives in memory and is lost on F5, but the pause is persisted as a
 * chat message. Find the latest unanswered human_input card for the flow and re-arm
 * the badge — but only when the backend still lists that run as pending. A card whose
 * job was resumed elsewhere / expired keeps `submitted_action` empty (the resume does
 * not always stamp it), so trusting the message alone re-armed a stale badge on every
 * open; cross-checking the pending list is the source of truth and also clears the
 * badge when navigating to a flow with nothing pending.
 */
export function useRestoreCanvasHitl(flowId: string | undefined): void {
  const { data } = useGetMessagesQuery(
    { id: flowId ?? "", mode: "union" },
    { enabled: Boolean(flowId) },
  );
  const { data: pendingRequests } = useGetPendingWorkflows(
    { flowId },
    { enabled: Boolean(flowId) },
  );

  useEffect(() => {
    if (pendingRequests === undefined) return;
    const pendingByRequestId = new Set(
      pendingRequests.map((req) => req.request_id),
    );
    const rows =
      (data as { rows?: { data?: Message[] } } | undefined)?.rows?.data ?? [];
    for (let i = rows.length - 1; i >= 0; i--) {
      const message = rows[i];
      const content = findHumanInputContent(message.content_blocks);
      if (
        content &&
        !content.submitted_action &&
        content.request_id &&
        pendingByRequestId.has(content.request_id)
      ) {
        if (content.job_id) {
          registerResumeContext(content.request_id, content.job_id, {
            flowId: message.flow_id ?? flowId ?? "",
            threadId: message.session_id ?? undefined,
          });
        }
        useHitlStore.getState().setPending({
          nodeId: content.request_id.split(":")[0],
          content,
        });
        return;
      }
    }
    // Nothing actually pending for this flow — drop any stale badge (e.g. resolved
    // elsewhere, expired, or carried over from a previously opened flow).
    useHitlStore.getState().clear();
  }, [data, pendingRequests, flowId]);
}
