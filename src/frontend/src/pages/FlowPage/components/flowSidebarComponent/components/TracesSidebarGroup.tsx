import { useCallback, useEffect, useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";

interface TracesSidebarGroupProps {
  selectedTraceId: string | null;
  onSelectTrace: (id: string | null) => void;
}

/**
 * Format timestamp to relative time
 */
const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return "";
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  } catch {
    return "";
  }
};

/**
 * Format latency for display
 */
const formatLatency = (ms: number) => {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

/**
 * Format token count
 */
const formatTokens = (tokens: number) => {
  if (tokens === 0) return "0";
  if (tokens < 1000) return `${tokens}`;
  if (tokens < 10000) return `${(tokens / 1000).toFixed(1)}k`;
  return `${Math.round(tokens / 1000)}k`;
};

/**
 * Empty state component
 */
const TracesEmptyState = () => (
  <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center px-4 py-8 text-center">
    <IconComponent
      name="Activity"
      className="mb-3 h-10 w-10 text-muted-foreground opacity-50"
    />
    <p className="text-sm text-muted-foreground">No traces yet</p>
    <p className="mt-1 text-xs text-muted-foreground">
      Run your flow to see execution traces
    </p>
  </div>
);

/**
 * Loading state component
 */
const TracesLoadingState = () => (
  <div className="flex h-full min-h-[100px] w-full items-center justify-center">
    <IconComponent
      name="Loader2"
      className="h-6 w-6 animate-spin text-muted-foreground"
    />
  </div>
);

/**
 * Get status badge styling
 */
const getStatusStyles = (status: string) => {
  switch (status) {
    case "success":
      return "bg-success-background text-success";
    case "error":
      return "bg-destructive/10 text-destructive";
    default:
      return "bg-muted text-muted-foreground";
  }
};

/**
 * Individual trace item in the list - two-row rich layout
 */
const TraceListItem = ({
  trace,
  isSelected,
  onSelect,
}: {
  trace: {
    id: string;
    name: string;
    status: string;
    startTime: string;
    totalLatencyMs: number;
    totalTokens: number;
  };
  isSelected: boolean;
  onSelect: () => void;
}) => (
  <button
    onClick={onSelect}
    className={cn(
      "flex w-full flex-col gap-1 rounded-md px-2 py-2 text-left transition-colors",
      isSelected
        ? "bg-accent text-accent-foreground"
        : "hover:bg-accent/50 text-foreground",
    )}
  >
    {/* Row 1: Name + status badge */}
    <div className="flex w-full items-center justify-between gap-2">
      <span className="truncate text-xs font-medium">{trace.name}</span>
      <span
        className={cn(
          "shrink-0 rounded-full px-1.5 py-0.5 text-[10px]",
          getStatusStyles(trace.status),
        )}
      >
        {trace.status}
      </span>
    </div>
    {/* Row 2: Latency + tokens + timestamp */}
    <div className="flex w-full items-center justify-between gap-2">
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-0.5">
          <IconComponent name="Clock" className="h-3 w-3" />
          {formatLatency(trace.totalLatencyMs)}
        </span>
        {trace.totalTokens > 0 && (
          <span className="flex items-center gap-0.5">
            <IconComponent name="Coins" className="h-3 w-3" />
            {formatTokens(trace.totalTokens)}
          </span>
        )}
      </span>
      <span className="shrink-0 text-[10px] text-muted-foreground">
        {formatTimestamp(trace.startTime)}
      </span>
    </div>
  </button>
);

/**
 * Sidebar group for traces - shows list of traces for the current flow
 */
const TracesSidebarGroup = ({
  selectedTraceId,
  onSelectTrace,
}: TracesSidebarGroupProps) => {
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Fetch traces for the current flow
  const { data: tracesData, isLoading } = useGetTracesQuery(
    { flowId: currentFlowId ?? null, params: { page: 1, size: 50 } },
    { enabled: !!currentFlowId, refetchInterval: 5000 },
  );

  // Traces list (already sorted by backend - newest first)
  const traces = useMemo(() => {
    return tracesData?.traces ?? [];
  }, [tracesData]);

  // Auto-select first trace when data loads
  useEffect(() => {
    if (traces.length > 0 && selectedTraceId === null) {
      onSelectTrace(traces[0].id);
    }
  }, [traces, selectedTraceId, onSelectTrace]);

  const handleClose = useCallback(() => {
    setActiveSection("components");
    if (!open) {
      toggleSidebar();
    }
  }, [setActiveSection, open, toggleSidebar]);

  const hasTraces = traces.length > 0;

  return (
    <SidebarGroup className={`p-3 pr-2${!hasTraces ? " h-full" : ""}`}>
      <SidebarGroupLabel className="flex w-full cursor-default items-center justify-between">
        <span>Traces</span>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClose}
          className="h-6 w-6"
          data-testid="close-traces-sidebar"
        >
          <IconComponent name="X" className="h-4 w-4" />
        </Button>
      </SidebarGroupLabel>
      <SidebarGroupContent className="h-full overflow-y-auto">
        {isLoading && <TracesLoadingState />}
        {!isLoading && !hasTraces && <TracesEmptyState />}
        {!isLoading && hasTraces && (
          <SidebarMenu>
            {traces.map((trace) => (
              <SidebarMenuItem key={trace.id}>
                <TraceListItem
                  trace={trace}
                  isSelected={selectedTraceId === trace.id}
                  onSelect={() => onSelectTrace(trace.id)}
                />
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

export default TracesSidebarGroup;
