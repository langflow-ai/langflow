import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import Loading from "@/components/ui/loading";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import { SpanDetail } from "./SpanDetail";
import { SpanTree } from "./SpanTree";
import { formatTotalLatency, getStatusIconProps } from "./traceViewHelpers";
import { TraceDetailViewProps } from "./traceViewTypes";
import { Span } from "./types";

/**
 * Single-trace detail view used in the right-side panel.
 * Matches the "Trace Detail" layout (header + span list + span details).
 */
export function TraceDetailView({ traceId, flowName }: TraceDetailViewProps) {
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  const { data: trace, isLoading } = useGetTraceQuery(
    { traceId: traceId ?? "" },
    { enabled: !!traceId },
  );

  useEffect(() => {
    setSelectedSpan(null);
  }, [traceId]);

  const summarySpan = useMemo<Span | null>(() => {
    if (!trace) return null;

    const status = trace.status as Span["status"];
    const name =
      status === "ok"
        ? "Successful Run"
        : status === "error"
          ? "Failed Run"
          : "Run Summary";

    return {
      id: trace.id,
      name,
      type: "none",
      status,
      startTime: trace.startTime,
      endTime: trace.endTime,
      latencyMs: trace.totalLatencyMs,
      inputs: trace.input ?? {},
      outputs: trace.output ?? {},
      tokenUsage:
        trace.totalTokens > 0
          ? {
              promptTokens: 0,
              completionTokens: 0,
              totalTokens: trace.totalTokens,
              cost: trace.totalCost,
            }
          : undefined,
      children: trace.spans ?? [],
    };
  }, [trace]);

  const treeSpans = useMemo(() => {
    if (!trace || !summarySpan) return [] as Span[];
    return [summarySpan];
  }, [trace, summarySpan]);

  useEffect(() => {
    if (!summarySpan) return;
    setSelectedSpan((prev) => prev ?? summarySpan);
  }, [summarySpan]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  if (!traceId) {
    return (
      <div
        className="flex h-full items-center justify-center text-sm text-muted-foreground"
        data-testid="trace-detail-view-empty"
      >
        No trace available for this run.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div
        className="flex h-full items-center justify-center"
        data-testid="trace-detail-view-loading"
      >
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loading size={32} className="text-primary" />
          <span className="text-sm">Loading trace...</span>
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div
        className="flex h-full items-center justify-center text-sm text-muted-foreground"
        data-testid="trace-detail-view-error"
      >
        Failed to load trace details.
      </div>
    );
  }

  const headerTitle = `${trace.name || flowName || "Trace"}`;
  const { colorClass, iconName, shouldSpin } = getStatusIconProps(trace.status);

  return (
    <div
      className="flex h-full flex-col overflow-hidden"
      data-testid="trace-detail-view"
    >
      <div className="border-b border-border px-4 py-3 pr-12">
        <div className="flex flex-nowrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap">
            <span className="shrink-0 text-sm font-medium">Trace Details</span>
            <span className="shrink-0 text-sm text-muted-foreground">—</span>
            <span className="min-w-0 truncate text-sm text-muted-foreground">
              {headerTitle}
            </span>
          </div>

          <div className="flex shrink-0 items-center gap-3 whitespace-nowrap">
            <Badge
              variant="outline"
              size="sm"
              className="max-w-[280px] truncate font-mono text-xs"
              title={trace.id}
            >
              <IconComponent name="Hash" className="mr-1 h-3 w-3" />
              {trace.id}
            </Badge>

            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <IconComponent name="Clock" className="h-3 w-3" />
                {formatTotalLatency(trace.totalLatencyMs)}
              </span>
              {trace.totalTokens > 0 && (
                <span className="flex items-center gap-1">
                  <IconComponent name="Coins" className="h-3 w-3" />
                  {trace.totalTokens.toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-[320px] min-w-[280px] overflow-y-auto border-r border-border p-2">
          <SpanTree
            spans={treeSpans}
            selectedSpanId={selectedSpan?.id ?? null}
            onSelectSpan={handleSelectSpan}
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <SpanDetail span={selectedSpan} />
        </div>
      </div>
    </div>
  );
}
