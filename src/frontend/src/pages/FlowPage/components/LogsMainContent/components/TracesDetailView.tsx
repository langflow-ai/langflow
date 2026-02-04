import { useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { convertUTCToLocalTimezone } from "@/utils/utils";
import { TraceView } from "@/modals/flowLogsModal/components/TraceView";

interface TracesDetailViewProps {
  flowId: string;
  initialRunId?: string | null;
}

/**
 * Format latency
 */
function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format timestamp
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

/**
 * Pretty print JSON
 */
function prettyJson(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
}

/**
 * Fallback view showing run details when traces aren't available
 */
function RunDetailsFallback({ runId }: { runId: string }) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const { data: transactionsData, isLoading } = useGetTransactionsQuery({
    id: currentFlowId,
    params: { page: 1, size: 100 },
    mode: "union",
  });

  const selectedRun = useMemo(() => {
    if (!transactionsData?.rows || !runId) return null;
    return transactionsData.rows.find(
      (row) => (row.id || row.vertex_id) === runId,
    );
  }, [transactionsData, runId]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-8 w-8 animate-spin" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!selectedRun) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <IconComponent name="AlertCircle" className="h-12 w-12 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">Run not found</p>
          </div>
        </div>
      </div>
    );
  }

  const isError = selectedRun.status === "error";
  const latencyMs = selectedRun.elapsed_time
    ? Math.round(selectedRun.elapsed_time * 1000)
    : 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border px-6 py-4">
        <div className="flex items-center gap-3">
          <Badge variant={isError ? "errorStatic" : "successStatic"} size="sm">
            {isError ? "ERROR" : "SUCCESS"}
          </Badge>
          <span className="font-mono text-sm text-muted-foreground">
            {runId.slice(0, 8)}
          </span>
          <span className="text-sm text-muted-foreground">
            {formatTimestamp(convertUTCToLocalTimezone(selectedRun.timestamp))}
          </span>
          <span className="text-sm text-muted-foreground">
            {formatLatency(latencyMs)}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="space-y-6">
          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Input</h3>
            <pre className="overflow-auto rounded-md bg-muted/50 p-4 text-sm">
              {prettyJson(selectedRun.inputs)}
            </pre>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Output</h3>
            <pre className="overflow-auto rounded-md bg-muted/50 p-4 text-sm">
              {prettyJson(selectedRun.outputs)}
            </pre>
          </div>

          {selectedRun.error && (
            <div>
              <h3 className="mb-2 text-sm font-medium text-error-foreground">Error</h3>
              <pre className="overflow-auto rounded-md bg-error/10 p-4 text-sm text-error-foreground">
                {selectedRun.error}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Traces detail view - shows execution tree with nested spans
 * Falls back to simple run details if traces aren't available
 */
export function TracesDetailView({
  flowId,
  initialRunId,
}: TracesDetailViewProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Check if traces API has data
  const { data: tracesData, isLoading, isError } = useGetTracesQuery(
    { flowId: currentFlowId ?? null, params: { page: 1, size: 10 } },
    {
      enabled: !!currentFlowId,
      retry: 0, // Don't retry - backend has timeout handling
      staleTime: 30000, // Consider data stale after 30s
    },
  );

  const hasTraces = tracesData?.traces && tracesData.traces.length > 0;

  // No run selected
  if (!initialRunId) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <IconComponent name="Activity" className="h-12 w-12 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">Select a run</p>
            <p className="mt-1 text-xs">
              Choose a run from the sidebar to view details.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Loading
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-8 w-8 animate-spin" />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  // If traces available, show the TraceView with span tree
  if (hasTraces && !isError) {
    return (
      <div className="h-full w-full">
        <TraceView flowId={currentFlowId} />
      </div>
    );
  }

  // Fallback to simple run details
  return <RunDetailsFallback runId={initialRunId} />;
}
