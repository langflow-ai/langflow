import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/ui/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";

export interface RunData {
  id: string;
  sessionId: string;
  timestamp: string;
  input: string;
  output: string;
  status: "success" | "error";
  latencyMs: number;
  error?: string;
}

interface LogsTableViewProps {
  runs: RunData[];
  isLoading: boolean;
  onViewTrace: (runId: string) => void;
  onRefresh: () => void;
  onLoadMore?: () => void;
  hasMore?: boolean;
}

/**
 * Format timestamp to readable string
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  if (isToday) {
    return date.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * Format latency
 */
function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text: string, maxLength: number = 50): string {
  if (!text) return "-";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Logs table view - flat list of all runs
 */
export function LogsTableView({
  runs,
  isLoading,
  onViewTrace,
  onRefresh,
  onLoadMore,
  hasMore,
}: LogsTableViewProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">(
    "all",
  );

  // Filter and sort runs
  const filteredRuns = useMemo(() => {
    const filtered =
      statusFilter === "all"
        ? runs
        : runs.filter((r) => r.status === statusFilter);

    // Sort by timestamp (newest first)
    return [...filtered].sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
  }, [runs, statusFilter]);

  if (isLoading && runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loading size={32} className="text-primary" />
          <span className="text-sm">Loading runs...</span>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <IconComponent name="ScrollText" className="h-12 w-12 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">No runs yet</p>
            <p className="mt-1 text-xs">
              Execute your flow to see run history here.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Filter bar */}
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <Select
            value={statusFilter}
            onValueChange={(v) =>
              setStatusFilter(v as "all" | "success" | "error")
            }
          >
            <SelectTrigger className="h-8 w-[130px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="success">Success</SelectItem>
              <SelectItem value="error">Errors</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-sm text-muted-foreground">
            {filteredRuns.length} run{filteredRuns.length !== 1 ? "s" : ""}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          disabled={isLoading}
        >
          <IconComponent
            name="RefreshCw"
            className={cn("mr-1.5 h-3.5 w-3.5", isLoading && "animate-spin")}
          />
          Refresh
        </Button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Status</TableHead>
              <TableHead className="w-24">Run ID</TableHead>
              <TableHead className="w-28">Time</TableHead>
              <TableHead>Input</TableHead>
              <TableHead>Output</TableHead>
              <TableHead className="w-20">Latency</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRuns.map((run) => (
              <TableRow key={run.id} className="group">
                <TableCell>
                  <Badge
                    variant={
                      run.status === "success" ? "successStatic" : "errorStatic"
                    }
                    size="sm"
                  >
                    {run.status === "success" ? "OK" : "ERR"}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {run.id.slice(0, 8)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatTimestamp(run.timestamp)}
                </TableCell>
                <TableCell
                  className="max-w-[200px] truncate text-sm"
                  title={run.input}
                >
                  {truncateText(run.input, 50)}
                </TableCell>
                <TableCell
                  className={cn(
                    "max-w-[200px] truncate text-sm",
                    run.error && "text-error-foreground",
                  )}
                  title={run.error || run.output}
                >
                  {run.error
                    ? truncateText(run.error, 50)
                    : truncateText(run.output, 50)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatLatency(run.latencyMs)}
                </TableCell>
                <TableCell>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => onViewTrace(run.id)}
                  >
                    View Trace
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Load more */}
      {hasMore && (
        <div className="flex justify-center border-t border-border py-3">
          <Button variant="outline" size="sm" onClick={onLoadMore}>
            Load More
          </Button>
        </div>
      )}
    </div>
  );
}
