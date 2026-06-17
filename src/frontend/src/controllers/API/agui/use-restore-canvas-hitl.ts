import { useEffect } from "react";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
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
 * the badge from it (no extra job-status query needed).
 */
export function useRestoreCanvasHitl(flowId: string | undefined): void {
  const { data } = useGetMessagesQuery(
    { id: flowId ?? "", mode: "union" },
    { enabled: Boolean(flowId) },
  );

  useEffect(() => {
    const rows =
      (data as { rows?: { data?: Message[] } } | undefined)?.rows?.data ?? [];
    for (let i = rows.length - 1; i >= 0; i--) {
      const message = rows[i];
      const content = findHumanInputContent(message.content_blocks);
      if (content && !content.submitted_action && content.request_id) {
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
  }, [data]);
}
