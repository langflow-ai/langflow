import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Loading } from "@/components/ui/loading";
import { cn } from "@/utils/utils";
import type { Span, Trace } from "./types";
import { SpanTree } from "./SpanTree";
import { SpanDetail } from "./SpanDetail";
import { useGetTracesQuery, useGetTraceQuery } from "@/controllers/API/queries/traces";

function buildRootSpan(trace: Trace): Span {
  const spans = trace.spans;

  // Collect inputs from first span with data, outputs from last span with data
  let rootInputs: Record<string, unknown> = {};
  let rootOutputs: Record<string, unknown> = {};
  for (const span of spans) {
    if (Object.keys(span.inputs).length > 0 && Object.keys(rootInputs).length === 0) {
      rootInputs = span.inputs;
    }
  }
  for (let i = spans.length - 1; i >= 0; i--) {
    if (Object.keys(spans[i].outputs).length > 0) {
      rootOutputs = spans[i].outputs;
      break;
    }
  }

  // Aggregate token usage from leaf spans
  let promptTokens = 0;
  let completionTokens = 0;
  const sumLeafTokens = (s: Span) => {
    if (s.children.length === 0 && s.tokenUsage) {
      promptTokens += s.tokenUsage.promptTokens;
      completionTokens += s.tokenUsage.completionTokens;
    }
    s.children.forEach(sumLeafTokens);
  };
  spans.forEach(sumLeafTokens);

  return {
    id: `root-${trace.id}`,
    name: trace.name,
    type: "run",
    status: trace.status,
    startTime: trace.startTime,
    endTime: trace.endTime,
    latencyMs: trace.totalLatencyMs,
    inputs: rootInputs,
    outputs: rootOutputs,
    tokenUsage: trace.totalTokens > 0
      ? { totalTokens: trace.totalTokens, promptTokens, completionTokens, cost: trace.totalCost }
      : undefined,
    children: trace.spans,
  };
}

interface TraceViewProps {
  flowId?: string | null;
  initialTraceId?: string | null;
}

function formatTotalCost(cost: number): string {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

function formatTotalLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function TraceView({ flowId, initialTraceId }: TraceViewProps) {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(initialTraceId ?? null);
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  useEffect(() => {
    if (initialTraceId) {
      setSelectedTraceId(initialTraceId);
      setSelectedSpan(null);
    }
  }, [initialTraceId]);

  const { data: tracesData, isLoading: isLoadingTraces } = useGetTracesQuery(
    { flowId: flowId ?? null, params: { page: 1, size: 10 } },
    { enabled: !!flowId && !initialTraceId },
  );

  useEffect(() => {
    if (!initialTraceId && tracesData?.traces && tracesData.traces.length > 0 && !selectedTraceId) {
      setSelectedTraceId(tracesData.traces[0].id);
    }
  }, [tracesData, selectedTraceId, initialTraceId]);

  const { data: trace, isLoading: isLoadingTrace } = useGetTraceQuery(
    { traceId: selectedTraceId },
    { enabled: !!selectedTraceId },
  );

  useEffect(() => {
    if (trace?.spans && trace.spans.length > 0) {
      setSelectedSpan(trace.spans[0]);
    }
  }, [trace?.id]);

  const rootSpan = useMemo(() => {
    if (!trace) return null;
    return buildRootSpan(trace);
  }, [trace]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  const isLoading = isLoadingTraces || isLoadingTrace;

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center bg-muted/30">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loading size={32} className="text-primary" />
          <span className="text-xs">Loading traces...</span>
        </div>
      </div>
    );
  }

  if (!trace || !trace.spans || trace.spans.length === 0) {
    return (
      <div className="flex h-full items-center justify-center bg-muted/30">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <IconComponent name="Activity" className="h-10 w-10 opacity-40" />
          <div className="text-center">
            <p className="text-sm font-medium">No traces available</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Run your flow to see execution traces here.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-muted/30">
      {/* Trace summary bar */}
      <div className="flex h-[52px] shrink-0 items-center justify-between border-b border-border bg-background pl-6 pr-12">
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Trace Detail</span>
          <span className="text-xs text-border">|</span>
          <span className="text-xs font-semibold">{trace.name}</span>
          <div
            className={cn(
              "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
              trace.status === "success" && "bg-emerald-500/10 text-emerald-500",
              trace.status === "error" && "bg-destructive/10 text-destructive",
              trace.status === "running" && "bg-muted text-muted-foreground",
            )}
          >
            {trace.status === "success" && (
              <IconComponent name="CheckCircle2" className="h-3 w-3" />
            )}
            {trace.status === "error" && (
              <IconComponent name="XCircle" className="h-3 w-3" />
            )}
            {trace.status === "running" && (
              <IconComponent name="Loader2" className="h-3 w-3 animate-spin" />
            )}
            {trace.status}
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <IconComponent name="Clock" className="h-3.5 w-3.5" />
            {formatTotalLatency(trace.totalLatencyMs)}
          </span>
          {trace.totalTokens > 0 && (
            <span className="flex items-center gap-1.5">
              <IconComponent name="Coins" className="h-3.5 w-3.5" />
              {trace.totalTokens.toLocaleString()}
            </span>
          )}
          {trace.totalCost > 0 && (
            <span className="flex items-center gap-1.5">
              <IconComponent name="DollarSign" className="h-3.5 w-3.5" />
              {formatTotalCost(trace.totalCost)}
            </span>
          )}
        </div>
      </div>

      {/* Split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Span tree */}
        <div className="w-[320px] min-w-[280px] overflow-y-auto border-r border-border bg-background p-1.5">
          <SpanTree
            spans={rootSpan ? [rootSpan] : []}
            selectedSpanId={selectedSpan?.id ?? null}
            onSelectSpan={handleSelectSpan}
          />
        </div>

        {/* Right: Span detail */}
        <div className="flex-1 overflow-hidden bg-background">
          <SpanDetail span={selectedSpan} />
        </div>
      </div>
    </div>
  );
}
