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
import { useSidebar } from "@/components/ui/sidebar";
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { LogsTableView, type RunData } from "./components/LogsTableView";
import { RunDetailPanel } from "./components/RunDetailPanel";

interface LogsMainContentProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

/**
 * Main content area for logs.
 * Header + left-right split: table left, Input/Output right.
 */
export default function LogsMainContent({
  selectedRunId: _selectedRunId,
  onSelectRun: _onSelectRun,
}: LogsMainContentProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const { setActiveSection } = useSidebar();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<
    "all" | "success" | "error"
  >("all");
  const [selectedTableRunId, setSelectedTableRunId] = useState<string | null>(
    null,
  );
  const [dateFilter, setDateFilter] = useState<
    "all" | "today" | "7d" | "30d"
  >("all");

  const { data, isLoading, refetch } = useGetTracesQuery({
    flowId: currentFlowId,
  });

  const allRuns = useMemo<RunData[]>(() => {
    if (!data?.traces) return [];
    return data.traces.map((trace) => ({
      id: trace.id,
      name: trace.name,
      sessionId: trace.sessionId || "default",
      timestamp: trace.startTime,
      status: trace.status === "error" ? "error" : "success",
      latencyMs: trace.totalLatencyMs,
      totalTokens: trace.totalTokens,
    }));
  }, [data]);

  // Summary stats (from all runs, before filtering)
  const summaryStats = useMemo(() => {
    const total = allRuns.length;
    const errors = allRuns.filter((r) => r.status === "error").length;
    return { total, errors };
  }, [allRuns]);

  // Filtered runs (search + status + date)
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
        (r) => new Date(r.timestamp) >= cutoff,
      );
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      filtered = filtered.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.sessionId.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q) ||
          r.status.toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [allRuns, statusFilter, dateFilter, searchQuery]);

  const selectedRun = useMemo(
    () => allRuns.find((r) => r.id === selectedTableRunId) ?? null,
    [allRuns, selectedTableRunId],
  );

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleExport = useCallback(() => {
    const exportData = filteredRuns.map((r) => ({
      id: r.id,
      name: r.name,
      sessionId: r.sessionId,
      timestamp: r.timestamp,
      status: r.status,
      latencyMs: r.latencyMs,
      totalTokens: r.totalTokens,
    }));
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredRuns]);

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-sm font-semibold">Logs</h2>
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
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isLoading}
            className="h-6 w-6"
            title="Refresh"
          >
            <IconComponent
              name="RefreshCw"
              className={cn("h-4 w-4", isLoading && "animate-spin")}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={handleExport}
            disabled={filteredRuns.length === 0}
            title="Export logs"
          >
            <IconComponent name="Download" className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Controls row — full width, same column split */}
      <div className="flex border-b border-border bg-background">
        {/* Left: search controls aligned with table */}
        <div className="flex w-1/3 shrink-0 items-center gap-2 border-r border-border px-3 py-3">
          <Input
            icon="Search"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 flex-1"
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
            <DropdownMenuContent align="start">
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
        </div>
        {/* Right: run details + See Traces */}
        <div className="flex min-w-0 flex-1 items-center justify-between px-4">
          {selectedRun ? (
            <>
              <div className="flex items-center gap-6">
                <span className="font-mono text-xs font-medium">
                  {selectedRun.id.slice(0, 8)}
                </span>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <IconComponent name="Clock" className="h-3 w-3" />
                  {selectedRun.latencyMs < 1000
                    ? `${selectedRun.latencyMs}ms`
                    : `${(selectedRun.latencyMs / 1000).toFixed(1)}s`}
                </span>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <IconComponent name="Coins" className="h-3 w-3" />
                  {selectedRun.totalTokens > 0
                    ? selectedRun.totalTokens < 1000
                      ? selectedRun.totalTokens
                      : `${(selectedRun.totalTokens / 1000).toFixed(1)}k`
                    : "\u2014"}
                </span>
                <span className={cn(
                  "text-xs font-medium",
                  selectedRun.status === "error"
                    ? "text-destructive"
                    : "text-accent-emerald-foreground",
                )}>
                  {selectedRun.status === "success" ? "Success" : "Error"}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 text-xs"
                onClick={() => setActiveSection("traces")}
              >
                See Trace
                <IconComponent name="ArrowRight" className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground">
              Select a run to view details
            </span>
          )}
        </div>
      </div>

      {/* Split content: table left, detail right */}
      <div className="flex flex-1 overflow-hidden">
        {/* Table panel */}
        <div className="flex h-full w-1/3 shrink-0 flex-col border-r border-border">
          <LogsTableView
            runs={filteredRuns}
            isLoading={isLoading}
            selectedRunId={selectedTableRunId}
            onSelectRun={setSelectedTableRunId}
          />
        </div>

        {/* Detail panel */}
        <div className="h-full min-w-0 flex-1">
          <RunDetailPanel traceId={selectedTableRunId} />
        </div>
      </div>
    </div>
  );
}
