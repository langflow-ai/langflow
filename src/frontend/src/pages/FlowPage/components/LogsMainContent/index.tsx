import { useCallback, useEffect, useState } from "react";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import { LogsTableView, type RunData } from "./components/LogsTableView";
import { TracesDetailView } from "./components/TracesDetailView";

type LogsTab = "logs" | "traces";

interface LogsMainContentProps {
  activeTab: LogsTab;
  onTabChange: (tab: LogsTab) => void;
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

/**
 * Main content area for logs - replaces the canvas when logs section is active
 * - Logs tab: Shows table of all runs
 * - Traces tab: Shows execution tree for selected run
 */
export default function LogsMainContent({
  activeTab,
  onTabChange,
  selectedRunId,
  onSelectRun,
}: LogsMainContentProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize] = useState(50);

  // Fetch transactions/runs
  const { data, isLoading, refetch } = useGetTransactionsQuery({
    id: currentFlowId,
    params: {
      page: pageIndex,
      size: pageSize,
    },
    mode: "union",
  });

  // Convert transactions to RunData format
  const [runs, setRuns] = useState<RunData[]>([]);

  useEffect(() => {
    if (data?.rows) {
      const convertedRuns: RunData[] = data.rows.map((row) => ({
        id: row.id || row.vertex_id,
        sessionId: row.flow_id || "default",
        timestamp: convertUTCToLocalTimezone(row.timestamp),
        input:
          typeof row.inputs === "object"
            ? JSON.stringify(row.inputs)
            : String(row.inputs ?? ""),
        output:
          typeof row.outputs === "object"
            ? JSON.stringify(row.outputs)
            : String(row.outputs ?? ""),
        status: row.status === "error" ? "error" : "success",
        latencyMs: row.elapsed_time ? Math.round(row.elapsed_time * 1000) : 0,
        error: row.error || undefined,
      }));
      setRuns(convertedRuns);
    }
  }, [data]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleViewTrace = useCallback(
    (runId: string) => {
      onSelectRun(runId);
      onTabChange("traces");
    },
    [onSelectRun, onTabChange],
  );

  const handleLoadMore = useCallback(() => {
    setPageIndex((prev) => prev + 1);
  }, []);

  const hasMore = data?.pagination
    ? data.pagination.page < data.pagination.pages
    : false;

  return (
    <div className="flex h-full w-full flex-col bg-background">
      {activeTab === "logs" ? (
        <LogsTableView
          runs={runs}
          isLoading={isLoading}
          onViewTrace={handleViewTrace}
          onRefresh={handleRefresh}
          onLoadMore={handleLoadMore}
          hasMore={hasMore}
        />
      ) : (
        <TracesDetailView flowId={currentFlowId} initialRunId={selectedRunId} />
      )}
    </div>
  );
}
