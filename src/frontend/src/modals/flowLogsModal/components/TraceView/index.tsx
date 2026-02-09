import { useCallback, useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loading } from "@/components/ui/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useGetTraceQuery,
  useGetTracesQuery,
} from "@/controllers/API/queries/traces";
import { cn } from "@/utils/utils";
import { SpanDetail } from "./SpanDetail";
import { SpanTree } from "./SpanTree";
import type { Span, Trace } from "./types";

interface TraceViewProps {
  flowId?: string | null;
  initialTraceId?: string | null;
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
 * Format timestamp to readable format
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

/**
 * Single trace accordion item with span tree and detail panel
 * Fetches full trace details only when expanded
 */
interface TraceAccordionItemProps {
  traceId: string;
  traceName: string;
  traceStatus: string;
  traceStartTime: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCost: number;
  isExpanded: boolean;
}

function TraceAccordionItem({
  traceId,
  traceName,
  traceStatus,
  traceStartTime,
  totalLatencyMs,
  totalTokens,
  totalCost,
  isExpanded,
}: TraceAccordionItemProps) {
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  // Only fetch full trace details (with spans) when expanded
  const { data: trace, isLoading } = useGetTraceQuery(
    { traceId },
    { enabled: isExpanded },
  );

  // Set initial selected span when trace loads
  useEffect(() => {
    if (trace?.spans && trace.spans.length > 0 && !selectedSpan) {
      setSelectedSpan(trace.spans[0]);
    }
  }, [trace?.spans, selectedSpan]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  return (
    <AccordionItem
      value={traceId}
      className={cn(
        "border-b border-border",
        traceStatus === "error" && "bg-error/5",
      )}
    >
      <AccordionTrigger
        className={cn(
          "px-4 py-3 hover:bg-muted/50",
          traceStatus === "error" && "hover:bg-error/10",
        )}
      >
        <div className="flex w-full items-center justify-between pr-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <IconComponent
                name="Activity"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="text-sm font-medium">{traceName}</span>
            </div>
            <Badge
              variant={
                traceStatus === "success"
                  ? "successStatic"
                  : traceStatus === "error"
                    ? "errorStatic"
                    : "secondaryStatic"
              }
              size="sm"
            >
              {traceStatus}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <IconComponent name="Calendar" className="h-3 w-3" />
              {formatTimestamp(traceStartTime)}
            </span>
            <span className="flex items-center gap-1">
              <IconComponent name="Clock" className="h-3 w-3" />
              {formatTotalLatency(totalLatencyMs)}
            </span>
            {totalTokens > 0 && (
              <span className="flex items-center gap-1">
                <IconComponent name="Hash" className="h-3 w-3" />
                {totalTokens.toLocaleString()} tokens
              </span>
            )}
            {totalCost > 0 && (
              <span className="flex items-center gap-1">
                <IconComponent name="DollarSign" className="h-3 w-3" />
                {formatTotalCost(totalCost)}
              </span>
            )}
          </div>
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-0 pb-0">
        {isLoading ? (
          <div className="flex h-[500px] items-center justify-center">
            <Loading size={24} className="text-primary" />
          </div>
        ) : trace ? (
          <div className="flex h-[500px] overflow-hidden border-t border-border">
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
        ) : (
          <div className="flex h-[500px] items-center justify-center text-sm text-muted-foreground">
            Failed to load trace details
          </div>
        )}
      </AccordionContent>
    </AccordionItem>
  );
}

/**
 * Main TraceView component showing multiple traces as accordions
 * Each trace can be expanded to show its span tree and details
 */
export function TraceView({ flowId, initialTraceId }: TraceViewProps) {
  const [expandedTraceId, setExpandedTraceId] = useState<string>(
    initialTraceId ?? "",
  );

  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [startDateFilter, setStartDateFilter] = useState<string>("");
  const [endDateFilter, setEndDateFilter] = useState<string>("");
  const [minTokens, setMinTokens] = useState<string>("");
  const [maxTokens, setMaxTokens] = useState<string>("");
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [showDateFilters, setShowDateFilters] = useState<boolean>(false);
  const [showTokenFilters, setShowTokenFilters] = useState<boolean>(false);

  // Sync expandedTraceId when initialTraceId changes
  useEffect(() => {
    if (initialTraceId) {
      setExpandedTraceId(initialTraceId);
    }
  }, [initialTraceId]);

  // Fetch list of traces for this flow (summary only, no spans)
  const { data: tracesData, isLoading: isLoadingTraces } = useGetTracesQuery(
    { flowId: flowId ?? null, params: { page: 1, size: 50 } },
    { enabled: !!flowId },
  );

  const allTraces = tracesData?.traces ?? [];

  // Apply filters
  const traces = allTraces.filter((trace) => {
    // Status filter
    if (statusFilter !== "all" && trace.status !== statusFilter) {
      return false;
    }

    // Date range filter
    if (startDateFilter) {
      const traceDate = new Date(trace.startTime);
      const startDate = new Date(startDateFilter);
      if (traceDate < startDate) {
        return false;
      }
    }

    if (endDateFilter) {
      const traceDate = new Date(trace.startTime);
      const endDate = new Date(endDateFilter);
      if (traceDate > endDate) {
        return false;
      }
    }

    // Token usage range filter
    if (minTokens) {
      const minTokenCount = parseInt(minTokens, 10);
      if (!isNaN(minTokenCount) && trace.totalTokens < minTokenCount) {
        return false;
      }
    }

    if (maxTokens) {
      const maxTokenCount = parseInt(maxTokens, 10);
      if (!isNaN(maxTokenCount) && trace.totalTokens > maxTokenCount) {
        return false;
      }
    }

    return true;
  });

  const handleClearFilters = () => {
    setStatusFilter("all");
    setStartDateFilter("");
    setEndDateFilter("");
    setMinTokens("");
    setMaxTokens("");
  };

  const hasActiveFilters =
    statusFilter !== "all" ||
    startDateFilter ||
    endDateFilter ||
    minTokens ||
    maxTokens;

  // Loading state
  if (isLoadingTraces) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loading size={32} className="text-primary" />
          <span className="text-sm">Loading traces...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border">
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-2">
            <IconComponent
              name="Activity"
              className="h-4 w-4 text-muted-foreground"
            />
            <span className="text-sm font-medium">
              Traces ({traces.length}
              {allTraces.length !== traces.length && ` of ${allTraces.length}`})
            </span>
          </div>
          <div className="flex items-center gap-2">
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearFilters}
                className="h-7 text-xs"
              >
                <IconComponent name="X" className="mr-1 h-3 w-3" />
                Clear Filters
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className="h-7 text-xs"
            >
              <IconComponent name="Filter" className="mr-1 h-3 w-3" />
              {showFilters ? "Hide" : "Show"} Filters
            </Button>
          </div>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="border-t border-border bg-muted/30 px- py-3">
            <div className="grid grid-cols-12 mr-2 pb-3" dir="rtl">
              {/* Status Filter */}
              <div className="space-y-1">
                <label className="mr-2 text-xs font-medium text-muted-foreground">
                  Status
                </label>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="h-8 w-32 text-xs">
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="success">Success</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Date Range Filter Button */}
              <div className="space-y-1">
                <label className="mr-2 text-xs font-medium text-muted-foreground">
                  Date Range
                </label>
                <Button
                  variant={
                    startDateFilter || endDateFilter ? "default" : "outline"
                  }
                  size="sm"
                  onClick={() => {
                    setShowDateFilters(!showDateFilters);
                    setShowTokenFilters(false);
                  }}
                  className="h-8 w-32 text-xs"
                >
                  <IconComponent name="Calendar" className="mr-1 h-3 w-3" />
                  {startDateFilter || endDateFilter ? "Active" : "Date Range"}
                </Button>
              </div>

              {/* Token Range Filter Button */}
              <div className="space-y-1">
                <label className="mr-2 text-xs font-medium text-muted-foreground">
                  Token Range
                </label>
                <Button
                  variant={minTokens || maxTokens ? "default" : "outline"}
                  size="sm"
                  onClick={() => {
                    setShowTokenFilters(!showTokenFilters);
                    setShowDateFilters(false);
                  }}
                  className="h-8 w-32 text-xs"
                >
                  <IconComponent name="Hash" className="mr-1 h-3 w-3" />
                  {minTokens || maxTokens ? "Active" : "Token Range"}
                </Button>
              </div>
            </div>

            {/* Date Range Inputs */}
            {showDateFilters && (
              <div className="p-3 grid grid-cols-1 gap-3 border-t border-border bg-muted/50 pt-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Start Date & Time
                  </label>
                  <Input
                    type="datetime-local"
                    value={startDateFilter}
                    onChange={(e) => setStartDateFilter(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    End Date & Time
                  </label>
                  <Input
                    type="datetime-local"
                    value={endDateFilter}
                    onChange={(e) => setEndDateFilter(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            )}

            {/* Token Range Inputs */}
            {showTokenFilters && (
              <div className="p-3 grid grid-cols-1 gap-3 border-t border-border bg-muted/50 pt-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Min Tokens
                  </label>
                  <Input
                    type="number"
                    min="0"
                    placeholder="Minimum tokens"
                    value={minTokens}
                    onChange={(e) => setMinTokens(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Max Tokens
                  </label>
                  <Input
                    type="number"
                    min="0"
                    placeholder="Maximum tokens"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content area - either traces or empty state */}
      <div className="flex-1 overflow-y-auto">
        {traces.length === 0 ? (
          // Empty state - distinguish between no traces at all vs filtered out
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-muted-foreground">
              <IconComponent
                name={hasActiveFilters ? "Filter" : "Activity"}
                className="h-12 w-12 opacity-50"
              />
              <div className="text-center">
                <p className="text-sm font-medium">
                  {hasActiveFilters
                    ? "No traces match your filters"
                    : allTraces.length === 0
                      ? "No traces available"
                      : "No traces to display"}
                </p>
                <p className="mt-1 text-xs">
                  {hasActiveFilters ? (
                    <>
                      Try adjusting your filters or{" "}
                      <button
                        onClick={handleClearFilters}
                        className="text-primary underline hover:no-underline"
                      >
                        clear all filters
                      </button>
                    </>
                  ) : (
                    "Run your flow to see execution traces here."
                  )}
                </p>
              </div>
            </div>
          </div>
        ) : (
          // Accordion list of traces
          <Accordion
            type="single"
            collapsible
            value={expandedTraceId}
            onValueChange={setExpandedTraceId}
          >
            {traces.map((trace) => (
              <TraceAccordionItem
                key={trace.id}
                traceId={trace.id}
                traceName={trace.name}
                traceStatus={trace.status}
                traceStartTime={trace.startTime}
                totalLatencyMs={trace.totalLatencyMs}
                totalTokens={trace.totalTokens}
                totalCost={trace.totalCost}
                isExpanded={expandedTraceId === trace.id}
              />
            ))}
          </Accordion>
        )}
      </div>
    </div>
  );
}

// Made with Bob
