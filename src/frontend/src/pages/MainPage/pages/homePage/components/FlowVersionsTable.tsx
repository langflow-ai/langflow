import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { cn } from "@/utils/utils";
import { useCallback, useEffect, useMemo, useState } from "react";
import FlowVersionsTableRow from "./FlowVersionsTableRow";

type FlowHistoryApiResponse = {
  entries: FlowHistoryEntry[];
  deployment_counts?: Record<string, number>;
};

type FlowVersionsTableProps = {
  flows: FlowType[];
  folderId?: string;
};

export default function FlowVersionsTable({
  flows,
  folderId,
}: FlowVersionsTableProps) {
  const [expandedFlowIds, setExpandedFlowIds] = useState<Set<string>>(
    new Set(),
  );
  const [historyByFlowId, setHistoryByFlowId] = useState<
    Record<string, FlowHistoryApiResponse>
  >({});
  const [isLoadingHistoryByFlowId, setIsLoadingHistoryByFlowId] = useState<
    Record<string, boolean>
  >({});

  useEffect(() => {
    const flowIds = new Set(flows.map((flow) => flow.id));
    setHistoryByFlowId((prev) =>
      Object.fromEntries(
        Object.entries(prev).filter(([flowId]) => flowIds.has(flowId)),
      ),
    );
    setIsLoadingHistoryByFlowId((prev) =>
      Object.fromEntries(
        Object.entries(prev).filter(([flowId]) => flowIds.has(flowId)),
      ),
    );
  }, [flows]);

  const loadHistoryForFlow = useCallback(
    async (flowId: string) => {
      if (historyByFlowId[flowId] || isLoadingHistoryByFlowId[flowId]) {
        return;
      }
      setIsLoadingHistoryByFlowId((prev) => ({ ...prev, [flowId]: true }));
      try {
        const response = await api.get<FlowHistoryApiResponse>(
          `${getURL("FLOWS")}/${flowId}/history/`,
          { params: { limit: 20, offset: 0 } },
        );
        setHistoryByFlowId((prev) => ({ ...prev, [flowId]: response.data }));
      } catch {
        setHistoryByFlowId((prev) => ({
          ...prev,
          [flowId]: { entries: [], deployment_counts: {} },
        }));
      } finally {
        setIsLoadingHistoryByFlowId((prev) => ({ ...prev, [flowId]: false }));
      }
    },
    [historyByFlowId, isLoadingHistoryByFlowId],
  );

  const rows = useMemo(() => {
    return flows.map((flow) => {
      const historyResponse = historyByFlowId[flow.id];
      const hasLoadedHistory = Boolean(historyResponse);
      const entries = historyResponse?.entries ?? [];
      const deploymentCounts = historyResponse?.deployment_counts ?? {};
      const deployedEntryCount = hasLoadedHistory
        ? entries.filter((entry) => (deploymentCounts[entry.id] ?? 0) > 0)
            .length
        : flow.has_deployments
          ? 1
          : 0;
      return {
        flow,
        entries,
        hasLoadedHistory,
        versionCount: hasLoadedHistory ? entries.length : null,
        deployedEntryCount,
        deploymentCounts,
        isLoadingHistory: isLoadingHistoryByFlowId[flow.id] ?? false,
      };
    });
  }, [flows, historyByFlowId, isLoadingHistoryByFlowId]);

  const tableGridCols =
    "grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.2fr)]";

  return (
    <div className="px-5 pb-5 pt-7">
      <div
        className={cn(
          "grid items-center gap-4 px-4 py-4 text-xs font-medium text-muted-foreground",
          tableGridCols,
        )}
      >
        <span className="pl-3">Name</span>
        <span>Version</span>
        <span>Status</span>
        <span>Last updated</span>
      </div>
      <div className="mt-1 border-y border-border/70">
        {rows.map(
          ({
            flow,
            entries,
            hasLoadedHistory,
            versionCount,
            deployedEntryCount,
            deploymentCounts,
            isLoadingHistory,
          }) => (
            <FlowVersionsTableRow
              key={flow.id}
              flow={flow}
              entries={entries}
              hasLoadedHistory={hasLoadedHistory}
              versionCount={versionCount}
              deployedEntryCount={deployedEntryCount}
              deploymentCounts={deploymentCounts}
              isLoadingHistory={isLoadingHistory}
              folderId={folderId}
              tableGridCols={tableGridCols}
              isExpanded={expandedFlowIds.has(flow.id)}
              onToggleExpand={() => {
                setExpandedFlowIds((prev) => {
                  const shouldOpen = !prev.has(flow.id);
                  const next = new Set(prev);
                  if (next.has(flow.id)) {
                    next.delete(flow.id);
                  } else {
                    next.add(flow.id);
                  }
                  if (shouldOpen && !hasLoadedHistory) {
                    void loadHistoryForFlow(flow.id);
                  }
                  return next;
                });
              }}
            />
          ),
        )}
      </div>
    </div>
  );
}
