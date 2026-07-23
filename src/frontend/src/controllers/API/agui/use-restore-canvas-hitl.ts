import { useEffect } from "react";
import { useGetPendingWorkflows } from "@/controllers/API/queries/workflows/use-get-pending-workflows";
import { useHitlStore } from "@/stores/hitlStore";
import type { InteractiveContent } from "@/types/chat";
import { registerResumeContext } from "./human-input-card";

/**
 * Keep the canvas awaiting-input badge in sync with the backend pending list (LE-1603).
 *
 * The pending list is the single source of truth: it is polled (every 5s) and carries the full
 * card (request_id, prompt, options, job_id), so the badge derives from it directly. Earlier this
 * cross-checked the messages query, but that query is NOT polled — during a live run it lags and
 * has no card yet, so the 5s pending poll re-ran this reconciler, found no matching message, and
 * cleared the badge "after a while". Deriving from the pending list survives the live run and the
 * reload alike, and clears the badge exactly when nothing is pending.
 */
export function useRestoreCanvasHitl(flowId: string | undefined): void {
  const { data: pendingRequests } = useGetPendingWorkflows(
    { flowId },
    { enabled: Boolean(flowId) },
  );

  useEffect(() => {
    if (pendingRequests === undefined) return;
    if (pendingRequests.length === 0) {
      useHitlStore.getState().clear();
      return;
    }
    const latest = [...pendingRequests].sort((a, b) =>
      (a.created_at ?? "").localeCompare(b.created_at ?? ""),
    )[pendingRequests.length - 1];
    const content: InteractiveContent = {
      type: "human_input",
      kind: (latest.kind as InteractiveContent["kind"]) ?? "node_input",
      request_id: latest.request_id,
      prompt: latest.prompt ?? undefined,
      options: latest.options ?? [],
      allowed_decisions: latest.allowed_decisions ?? [],
      job_id: latest.job_id,
    };
    if (latest.job_id) {
      registerResumeContext(latest.request_id, latest.job_id, {
        flowId: latest.flow_id ?? flowId ?? "",
        threadId: latest.session_id ?? undefined,
      });
    }
    useHitlStore.getState().setPending({
      nodeId: latest.request_id.split(":")[0],
      content,
    });
  }, [pendingRequests, flowId]);
}
