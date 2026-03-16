import { useCallback, useEffect, useMemo, useState } from "react";
import Loading from "@/components/ui/loading";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import { SpanDetail } from "./SpanDetail";
import { SpanTree } from "./SpanTree";
import { Span, TraceDetailViewProps } from "./types";

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

    const status = trace.status;
    const name = trace.name || flowName || "Run Summary";

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
            <span className="shrink-0 text-sm font-medium">{trace.id}</span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-[380px] min-w-[320px] overflow-y-auto border-r border-border p-2">
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
