import { useCallback, useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { Span, Trace } from "./types";
import { SpanTree } from "./SpanTree";
import { SpanDetail } from "./SpanDetail";
import { useGetTracesQuery, useGetTraceQuery } from "@/controllers/API/queries/traces";

interface TraceViewProps {
  flowId?: string | null;
}

/**
 * Format total cost as currency
 */
function formatTotalCost(cost: number): string {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

/**
 * Format total latency
 */
function formatTotalLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * Main TraceView component showing hierarchical execution traces
 * Split panel layout: span tree on left, detail panel on right
 */
export function TraceView({ flowId }: TraceViewProps) {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  // Fetch list of traces for this flow
  const { data: tracesData, isLoading: isLoadingTraces } = useGetTracesQuery(
    { flowId: flowId ?? null, params: { page: 1, size: 10 } },
    { enabled: !!flowId },
  );

  // Auto-select the first trace when data loads
  useEffect(() => {
    if (tracesData?.traces && tracesData.traces.length > 0 && !selectedTraceId) {
      setSelectedTraceId(tracesData.traces[0].id);
    }
  }, [tracesData, selectedTraceId]);

  // Fetch the selected trace with full span tree
  const { data: trace, isLoading: isLoadingTrace } = useGetTraceQuery(
    { traceId: selectedTraceId },
    { enabled: !!selectedTraceId },
  );

  // Set initial selected span when trace changes
  useEffect(() => {
    if (trace?.spans && trace.spans.length > 0) {
      setSelectedSpan(trace.spans[0]);
    }
  }, [trace?.id]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  const isLoading = isLoadingTraces || isLoadingTrace;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-8 w-8 animate-spin" />
          <span className="text-sm">Loading traces...</span>
        </div>
      </div>
    );
  }

  // Empty state - no traces available
  if (!trace || !trace.spans || trace.spans.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <IconComponent name="Activity" className="h-12 w-12 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">No traces available</p>
            <p className="mt-1 text-xs">
              Run your flow to see execution traces here.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Trace summary header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <IconComponent name="Activity" className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{trace.name}</span>
          </div>
          <span
            className={cn(
              "flex items-center gap-1 text-xs",
              trace.status === "success" && "text-accent-emerald-foreground",
              trace.status === "error" && "text-error-foreground",
              trace.status === "running" && "text-muted-foreground",
            )}
          >
            {trace.status === "success" && (
              <IconComponent name="CheckCircle" className="h-3 w-3" />
            )}
            {trace.status === "error" && (
              <IconComponent name="XCircle" className="h-3 w-3" />
            )}
            {trace.status === "running" && (
              <IconComponent name="Loader2" className="h-3 w-3 animate-spin" />
            )}
            {trace.status}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <IconComponent name="Clock" className="h-3 w-3" />
            {formatTotalLatency(trace.totalLatencyMs)}
          </span>
          {trace.totalTokens > 0 && (
            <span className="flex items-center gap-1">
              <IconComponent name="Hash" className="h-3 w-3" />
              {trace.totalTokens.toLocaleString()} tokens
            </span>
          )}
          {trace.totalCost > 0 && (
            <span className="flex items-center gap-1">
              <IconComponent name="DollarSign" className="h-3 w-3" />
              {formatTotalCost(trace.totalCost)}
            </span>
          )}
        </div>
      </div>

      {/* Main content: split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Span tree */}
        <div className="w-1/3 min-w-[280px] overflow-y-auto border-r border-border p-2">
          <SpanTree
            spans={trace.spans ?? []}
            selectedSpanId={selectedSpan?.id ?? null}
            onSelectSpan={handleSelectSpan}
          />
        </div>

        {/* Right panel: Span details */}
        <div className="flex-1 overflow-hidden">
          <SpanDetail span={selectedSpan} />
        </div>
      </div>
    </div>
  );
}
