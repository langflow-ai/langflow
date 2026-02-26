import { useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Accordion } from "@/components/ui/accordion";
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
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import { parseApiTimestamp } from "@/utils/dateTime";
import { TraceAccordionItem } from "./TraceAccordionItem";
import type { TraceViewProps } from "./traceViewTypes";

/**
 * Main TraceView component showing multiple traces as accordions
 * Each trace can be expanded to show its trace tree and details
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
  const [groupBy, setGroupBy] = useState<"none" | "session" | "flow">("none");

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
      const traceDate = parseApiTimestamp(trace.startTime);
      if (!traceDate) return false;
      const startDate = new Date(startDateFilter);
      if (traceDate < startDate) {
        return false;
      }
    }

    if (endDateFilter) {
      const traceDate = parseApiTimestamp(trace.startTime);
      if (!traceDate) return false;
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

  // Group traces by session_id or flow_id
  const groupedTraces: Record<string, typeof traces> = {};
  if (groupBy === "none") {
    groupedTraces["all"] = traces;
  } else {
    traces.forEach((trace) => {
      const key =
        (groupBy === "session" ? trace.sessionId : trace.flowId) ?? "unknown";
      if (!groupedTraces[key]) {
        groupedTraces[key] = [];
      }
      groupedTraces[key].push(trace);
    });
  }

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
              {/* Group By Filter */}
              <div className="space-y-1">
                <label className="mr-2 text-xs font-medium text-muted-foreground">
                  Group By
                </label>
                <Select
                  value={groupBy}
                  onValueChange={(value) =>
                    setGroupBy(value as "none" | "session" | "flow")
                  }
                >
                  <SelectTrigger className="h-8 w-32 text-xs">
                    <SelectValue placeholder="No grouping" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No Grouping</SelectItem>
                    <SelectItem value="session">Session ID</SelectItem>
                    <SelectItem value="flow">Flow ID</SelectItem>
                  </SelectContent>
                </Select>
              </div>

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
                  <IconComponent name="Coins" className="mr-1 h-3 w-3" />
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
          // Accordion list of traces (grouped or ungrouped)
          <div className="space-y-4">
            {Object.entries(groupedTraces).map(([groupKey, groupTraces]) => (
              <div key={groupKey}>
                {groupBy !== "none" && (
                  <div className="sticky top-0 z-10 bg-background px-4 py-2 border-b border-border">
                    <div className="flex items-center gap-2">
                      <IconComponent
                        name={groupBy === "session" ? "Hash" : "Workflow"}
                        className="h-4 w-4 text-muted-foreground"
                      />
                      <span className="text-sm font-semibold">
                        {groupBy === "session" ? "Session" : "Flow"}: {groupKey}
                      </span>
                      <Badge variant="secondary" size="sm">
                        {groupTraces.length} trace
                        {groupTraces.length !== 1 ? "s" : ""}
                      </Badge>
                    </div>
                  </div>
                )}
                <Accordion
                  type="single"
                  collapsible
                  value={expandedTraceId}
                  onValueChange={setExpandedTraceId}
                >
                  {groupTraces.map((trace) => (
                    <TraceAccordionItem
                      key={trace.id}
                      traceId={trace.id}
                      traceName={trace.name}
                      traceStatus={trace.status}
                      traceStartTime={trace.startTime}
                      totalLatencyMs={trace.totalLatencyMs}
                      totalTokens={trace.totalTokens}
                      totalCost={trace.totalCost}
                      sessionId={trace.sessionId ?? "N/A"}
                      input={trace.input}
                      output={trace.output}
                      isExpanded={expandedTraceId === trace.id}
                    />
                  ))}
                </Accordion>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
