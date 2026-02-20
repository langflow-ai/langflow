import { useCallback, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { RunsTable, type RunData } from "./components/RunsTable";
import { RunTracePanel } from "./components/RunTracePanel";

/**
 * Summarize an I/O record into a short preview string.
 * Tries to extract a meaningful text value from the record.
 */
function summarizeIO(
  data: Record<string, unknown> | null | undefined,
): string | undefined {
  if (!data) return undefined;
  const values = Object.values(data);
  if (values.length === 0) return undefined;
  // If there's a single string value, use it directly
  if (values.length === 1 && typeof values[0] === "string") {
    return values[0];
  }
  // Try to find a "text", "message", "content", or "input"/"output" key
  for (const key of ["text", "message", "content", "input", "output", "result"]) {
    if (typeof data[key] === "string") {
      return data[key] as string;
    }
  }
  // Fallback: JSON stringify
  try {
    return JSON.stringify(data);
  } catch {
    return undefined;
  }
}

export default function RunsMainContent() {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "success" | "error"
  >("all");
  const [dateFilter, setDateFilter] = useState<
    "all" | "today" | "7d" | "30d"
  >("all");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [groupBySession, setGroupBySession] = useState(true);

  const { data, isLoading, refetch } = useGetTracesQuery({
    flowId: currentFlowId,
  });

  const allRuns = useMemo<RunData[]>(() => {
    if (!data?.traces) return [];
    return data.traces.map((trace) => ({
      id: trace.id,
      name: trace.name,
      sessionId: trace.sessionId || "default",
      status: trace.status === "error" ? "error" : "success",
      startTime: trace.startTime,
      latencyMs: trace.totalLatencyMs,
      totalTokens: trace.totalTokens,
      totalCost: trace.totalCost,
      input: summarizeIO(trace.input),
      output: summarizeIO(trace.output),
    }));
  }, [data]);

  const summaryStats = useMemo(() => {
    const total = allRuns.length;
    const errors = allRuns.filter((r) => r.status === "error").length;
    return { total, errors };
  }, [allRuns]);

  const filteredRuns = useMemo(() => {
    let filtered = allRuns;
    if (statusFilter !== "all") {
      filtered = filtered.filter((r) => r.status === statusFilter);
    }
    if (dateFilter !== "all") {
      const now = new Date();
      let cutoff: Date;
      if (dateFilter === "today") {
        cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      } else if (dateFilter === "7d") {
        cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      } else {
        cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      }
      filtered = filtered.filter(
        (r) => new Date(r.startTime) >= cutoff,
      );
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      filtered = filtered.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.sessionId.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [allRuns, statusFilter, dateFilter, searchQuery]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleExport = useCallback(() => {
    const exportData = filteredRuns.map((r) => ({
      id: r.id,
      name: r.name,
      sessionId: r.sessionId,
      startTime: r.startTime,
      status: r.status,
      latencyMs: r.latencyMs,
      totalTokens: r.totalTokens,
      totalCost: r.totalCost,
      input: r.input,
      output: r.output,
    }));
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `runs-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredRuns]);

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header + Toolbar */}
      <div className="flex h-[52px] shrink-0 items-center gap-3 border-b border-border bg-background px-6">
        {/* Title + stats */}
        <h2 className="text-sm font-semibold">Runs</h2>
        <span className="text-xs text-muted-foreground">&middot;</span>
        <span className="text-xs text-muted-foreground">
          Total {summaryStats.total}
        </span>
        {summaryStats.errors > 0 && (
          <>
            <span className="text-xs text-muted-foreground">&middot;</span>
            <span className="text-xs font-medium text-destructive">
              {summaryStats.errors} error
              {summaryStats.errors !== 1 ? "s" : ""}
            </span>
          </>
        )}

        {/* Separator */}
        <div className="mx-1 h-4 w-px bg-border" />

        {/* Group by Session toggle */}
        <Button
          variant={groupBySession ? "secondary" : "ghost"}
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs"
          onClick={() => setGroupBySession((v) => !v)}
          title={groupBySession ? "Hide sessions" : "Group by session"}
        >
          <IconComponent name="Layers" className="h-3.5 w-3.5" />
          Group by Session
        </Button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search + Filters + Actions */}
        <Input
          icon="Search"
          placeholder="Search runs..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-8 max-w-xs"
        />
        <Select
          value={statusFilter}
          onValueChange={(v) =>
            setStatusFilter(v as "all" | "success" | "error")
          }
        >
          <SelectTrigger className="h-8 w-[130px] shrink-0 whitespace-nowrap">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="error">Errors</SelectItem>
          </SelectContent>
        </Select>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant={dateFilter !== "all" ? "secondary" : "ghost"}
              size="icon"
              className="h-8 w-8 shrink-0"
            >
              <IconComponent name="Calendar" className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setDateFilter("all")}>
              All time
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDateFilter("today")}>
              Today
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDateFilter("7d")}>
              Last 7 days
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDateFilter("30d")}>
              Last 30 days
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* Separator */}
        <div className="mx-0.5 h-4 w-px bg-border" />

        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={isLoading}
          className="h-7 w-7"
          title="Refresh"
        >
          <IconComponent
            name="RefreshCw"
            className={cn("h-3.5 w-3.5", isLoading && "animate-spin")}
          />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleExport}
          disabled={filteredRuns.length === 0}
          title="Export runs"
        >
          <IconComponent name="Download" className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Full-width table */}
      <div className="flex flex-1 overflow-hidden">
        <RunsTable
          runs={filteredRuns}
          isLoading={isLoading}
          selectedRunId={selectedRunId}
          onSelectRun={setSelectedRunId}
          groupBySession={groupBySession}
        />
      </div>

      {/* Slide-in trace panel */}
      <RunTracePanel
        selectedRunId={selectedRunId}
        onClose={() => setSelectedRunId(null)}
      />
    </div>
  );
}
