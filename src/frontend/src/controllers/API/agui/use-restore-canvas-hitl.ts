import { useEffect } from "react";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useHitlStore } from "@/stores/hitlStore";
import type { Message } from "@/types/messages";
import { findHumanInputContent } from "./human-input-card";

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
      const content = findHumanInputContent(rows[i].content_blocks);
      if (content && !content.submitted_action && content.request_id) {
        useHitlStore.getState().setPending({
          nodeId: content.request_id.split(":")[0],
          content,
        });
        return;
      }
    }
  }, [data]);
}
