import { useQueryClient } from "@tanstack/react-query";
import type { AgGridReact } from "ag-grid-react";
import { useEffect, useRef } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { isBusyStatus } from "../config/statusConfig";

const POLLING_INTERVAL_MS = 6000;

export interface KnowledgeBaseStatusTransition {
  kb: KnowledgeBaseInfo;
  previousStatus: string;
}

interface UseKnowledgeBasePollingOptions {
  knowledgeBases: KnowledgeBaseInfo[] | undefined;
  tableRef: React.RefObject<AgGridReact<unknown> | null>;
  onStatusChange?: (transitions: KnowledgeBaseStatusTransition[]) => void;
}

/**
 * Polls for knowledge base updates when any KB is in a busy state (ingesting/cancelling).
 * Updates the ag-grid directly for numeric-only changes to avoid re-renders,
 * and updates the React Query cache when a status transition occurs.
 */
export const useKnowledgeBasePolling = ({
  knowledgeBases,
  tableRef,
  onStatusChange,
}: UseKnowledgeBasePollingOptions) => {
  const queryClient = useQueryClient();
  const pollingRef = useRef(false);
  const onStatusChangeRef = useRef(onStatusChange);
  onStatusChangeRef.current = onStatusChange;

  // When data arrives, check if polling is needed
  useEffect(() => {
    if (knowledgeBases) {
      pollingRef.current = knowledgeBases.some((kb) => isBusyStatus(kb.status));
    }
  }, [knowledgeBases]);

  // Polling: direct grid update for numeric fields (avoids re-render / dropdown close),
  // but update React Query cache when a status transition occurs
  useEffect(() => {
    const poll = async () => {
      if (!pollingRef.current) return;

      try {
        const res = await api.get(`${getURL("KNOWLEDGE_BASES")}/`);
        const freshData: KnowledgeBaseInfo[] = res.data;

        const currentData = queryClient.getQueryData<KnowledgeBaseInfo[]>([
          "useGetKnowledgeBases",
        ]);

        // Collect status transitions for notification
        const transitions: KnowledgeBaseStatusTransition[] = [];
        if (currentData) {
          for (const kb of freshData) {
            const old = currentData.find((o) => o.dir_name === kb.dir_name);
            if (old && old.status !== kb.status) {
              transitions.push({ kb, previousStatus: old.status || "empty" });
            }
          }
        }

        // Check if any KB status changed or list size changed
        const statusChanged =
          !currentData ||
          currentData.length !== freshData.length ||
          transitions.length > 0;

        if (statusChanged) {
          // Status transition — update cache (causes re-render, acceptable)
          queryClient.setQueryData(["useGetKnowledgeBases"], freshData);

          // Notify the parent about status transitions
          if (transitions.length > 0) {
            onStatusChangeRef.current?.(transitions);
          }
        } else {
          // No status change — update grid directly to avoid re-render
          const gridApi = tableRef.current?.api;
          if (gridApi) {
            for (const kb of freshData) {
              const rowNode = gridApi.getRowNode(kb.dir_name);
              if (rowNode) {
                rowNode.setData(kb);
              }
            }
          }
        }

        pollingRef.current = freshData.some((kb) => isBusyStatus(kb.status));
      } catch (e) {
        // Silently ignore polling errors
      }
    };

    const intervalId = setInterval(poll, POLLING_INTERVAL_MS);
    return () => clearInterval(intervalId);
  }, [queryClient]);

  return { pollingRef };
};
