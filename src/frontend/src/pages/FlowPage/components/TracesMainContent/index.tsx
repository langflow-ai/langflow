import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Loading } from "@/components/ui/loading";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import { SpanTree } from "@/modals/flowLogsModal/components/TraceView/SpanTree";
import { SpanDetail } from "@/modals/flowLogsModal/components/TraceView/SpanDetail";
import type { Span } from "@/modals/flowLogsModal/components/TraceView/types";
import { cn } from "@/utils/utils";

interface TracesMainContentProps {
  selectedTraceId?: string | null;
}

const statusColors: Record<string, string> = {
  running: "text-muted-foreground",
  success: "text-emerald-600",
  error: "text-destructive",
};

const formatLatency = (ms: number) => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

const formatTokens = (tokens: number) => {
  if (!tokens) return "0";
  return tokens.toLocaleString();
};

const formatCost = (cost: number) => {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
};

/**
 * Recursively walk spans to compute aggregate prompt/completion tokens
 */
function aggregateTokenUsage(spans: Span[]): {
  promptTokens: number;
  completionTokens: number;
} {
  let prompt = 0;
  let completion = 0;
  for (const span of spans) {
    const childAgg = span.children?.length
      ? aggregateTokenUsage(span.children)
      : { promptTokens: 0, completionTokens: 0 };
    const childrenHaveTokens =
      childAgg.promptTokens > 0 || childAgg.completionTokens > 0;

    if (childrenHaveTokens) {
      // Children have their own token data — use that to avoid double-counting
      prompt += childAgg.promptTokens;
      completion += childAgg.completionTokens;
    } else if (span.tokenUsage) {
      // Leaf token-bearing span
      prompt += span.tokenUsage.promptTokens;
      completion += span.tokenUsage.completionTokens;
    }
  }
  return { promptTokens: prompt, completionTokens: completion };
}

/**
 * Summary card component
 */
const SummaryCard = ({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: string;
}) => (
  <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-background px-5 py-3">
    <span className="text-[11px] text-muted-foreground">{label}</span>
    <span className="flex items-center gap-1.5 text-sm font-semibold">
      <IconComponent name={icon} className="h-3.5 w-3.5 text-muted-foreground" />
      {value}
    </span>
  </div>
);

/**
 * Empty state when no trace is selected
 */
const NoTraceSelected = () => (
  <div className="flex h-full w-full flex-col items-center justify-center text-center">
    <IconComponent
      name="Activity"
      className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
    />
    <p className="text-sm text-muted-foreground">No trace selected</p>
    <p className="mt-1 text-xs text-muted-foreground">
      Select a trace from the sidebar to view details
    </p>
  </div>
);

/**
 * Main content area for traces - replaces the canvas when traces section is active
 * Shows summary cards and SpanTree + SpanDetail split panel
 */
export default function TracesMainContent({
  selectedTraceId,
}: TracesMainContentProps) {
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  // Fetch the selected trace with full span tree
  const { data: trace, isLoading } = useGetTraceQuery(
    { traceId: selectedTraceId ?? null },
    { enabled: !!selectedTraceId },
  );

  // Reset selected span when trace changes
  useEffect(() => {
    if (trace?.spans && trace.spans.length > 0) {
      setSelectedSpan(trace.spans[0]);
    } else {
      setSelectedSpan(null);
    }
  }, [trace?.id]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  // Compute prompt/completion aggregates
  const tokenAggregates = useMemo(() => {
    if (!trace?.spans) return { promptTokens: 0, completionTokens: 0 };
    return aggregateTokenUsage(trace.spans);
  }, [trace?.spans]);

  if (!selectedTraceId) {
    return <NoTraceSelected />;
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading size={64} className="text-primary" />
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center text-center">
        <IconComponent
          name="Activity"
          className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
        />
        <p className="text-sm text-muted-foreground">Trace not found</p>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background px-6 py-5">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">{trace.name}</h2>
          <span className="text-xs text-muted-foreground">&middot;</span>
          <span
            className={cn(
              "flex items-center gap-1 text-xs capitalize",
              statusColors[trace.status] ?? "text-muted-foreground",
            )}
          >
            {trace.status === "success" && (
              <IconComponent name="CheckCircle" className="h-3 w-3" />
            )}
            {trace.status === "error" && (
              <IconComponent name="XCircle" className="h-3 w-3" />
            )}
            {trace.status}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-3 overflow-auto p-4">
        {/* Summary cards row */}
        <div className="flex items-stretch gap-3">
          <SummaryCard
            label="Latency"
            value={formatLatency(trace.totalLatencyMs)}
            icon="Clock"
          />
          <SummaryCard
            label="Tokens"
            value={formatTokens(tokenAggregates.promptTokens + tokenAggregates.completionTokens)}
            icon="Coins"
          />
          <SummaryCard
            label="Prompt"
            value={formatTokens(tokenAggregates.promptTokens)}
            icon="ArrowUp"
          />
          <SummaryCard
            label="Completion"
            value={formatTokens(tokenAggregates.completionTokens)}
            icon="ArrowDown"
          />
          {trace.totalCost > 0 && (
            <SummaryCard
              label="Cost"
              value={formatCost(trace.totalCost)}
              icon="DollarSign"
            />
          )}
        </div>

        {/* Split panel: SpanTree + SpanDetail */}
        <div className="flex flex-1 overflow-hidden rounded-lg border border-border bg-background">
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
    </div>
  );
}
