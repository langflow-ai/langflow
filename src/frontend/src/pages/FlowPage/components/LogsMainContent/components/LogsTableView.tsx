import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
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
  name: string;
  sessionId: string;
  timestamp: string;
  status: "success" | "error";
  latencyMs: number;
  totalTokens: number;
}

interface SessionGroup {
  sessionId: string;
  runs: RunData[];
  errorCount: number;
}

interface LogsTableViewProps {
  runs: RunData[];
  isLoading: boolean;
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

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

function truncateSessionId(sessionId: string): string {
  if (sessionId === "default") return "default";
  if (sessionId.length <= 6) return sessionId;
  return sessionId.slice(0, 6) + "\u2026";
}

export function LogsTableView({
  runs,
  isLoading,
  selectedRunId,
  onSelectRun,
}: LogsTableViewProps) {
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(
    new Set(),
  );
  const [initialized, setInitialized] = useState(false);

  const sessionGroups = useMemo(() => {
    const groupMap = new Map<string, RunData[]>();
    for (const run of runs) {
      const existing = groupMap.get(run.sessionId);
      if (existing) {
        existing.push(run);
      } else {
        groupMap.set(run.sessionId, [run]);
      }
    }

    const groups: SessionGroup[] = [];
    for (const [sessionId, sessionRuns] of Array.from(groupMap)) {
      sessionRuns.sort(
        (a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
      );
      groups.push({
        sessionId,
        runs: sessionRuns,
        errorCount: sessionRuns.filter((r) => r.status === "error").length,
      });
    }

    groups.sort(
      (a, b) =>
        new Date(b.runs[0].timestamp).getTime() -
        new Date(a.runs[0].timestamp).getTime(),
    );

    if (!initialized && groups.length > 0) {
      setExpandedSessions(new Set(groups.map((g) => g.sessionId)));
      setInitialized(true);
    }

    return groups;
  }, [runs, initialized]);

  const toggleSession = (sessionId: string) => {
    setExpandedSessions((prev) => {
      const next = new Set(prev);
      if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      return next;
    });
  };

  if (isLoading && runs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-8">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-6 w-6 animate-spin" />
          <span className="text-xs">Loading runs...</span>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-8">
        <div className="flex flex-col items-center text-muted-foreground">
          <IconComponent
            name="ScrollText"
            className="mb-3 h-10 w-10 opacity-50"
          />
          <p className="text-sm font-medium">No runs yet</p>
          <p className="mt-1 text-xs">
            Execute your flow to see run history here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="!px-3" style={{ minWidth: 100 }}>Session</TableHead>
            <TableHead className="!px-3" style={{ minWidth: 90 }}>Run</TableHead>
            <TableHead className="!px-3" style={{ minWidth: 100 }}>Time</TableHead>
            <TableHead className="!px-3" style={{ minWidth: 60 }}>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sessionGroups.map((group) => {
            const isExpanded = expandedSessions.has(group.sessionId);
            return (
              <SessionRows
                key={group.sessionId}
                group={group}
                isExpanded={isExpanded}
                onToggle={() => toggleSession(group.sessionId)}
                selectedRunId={selectedRunId}
                onSelectRun={onSelectRun}
              />
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function SessionRows({
  group,
  isExpanded,
  onToggle,
  selectedRunId,
  onSelectRun,
}: {
  group: SessionGroup;
  isExpanded: boolean;
  onToggle: () => void;
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}) {
  return (
    <>
      {/* Session header row */}
      <TableRow
        className="cursor-pointer bg-muted/40 hover:bg-muted/60"
        onClick={onToggle}
      >
        <TableCell className="!px-3">
          <div className="flex items-center gap-1.5">
            <IconComponent
              name="ChevronRight"
              className={cn(
                "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
                isExpanded && "rotate-90",
              )}
            />
            <span className="text-xs font-medium">
              {truncateSessionId(group.sessionId)}
            </span>
          </div>
        </TableCell>
        <TableCell className="!px-3 text-xs text-muted-foreground">
          {group.runs.length} run{group.runs.length !== 1 ? "s" : ""}
        </TableCell>
        <TableCell className="!px-3" />
        <TableCell className="!px-3">
          {group.errorCount > 0 && (
            <Badge variant="errorStatic" size="sm">
              {group.errorCount} err
            </Badge>
          )}
        </TableCell>
      </TableRow>

      {/* Run rows */}
      {isExpanded &&
        group.runs.map((run) => (
          <TableRow
            key={run.id}
            className={cn(
              "cursor-pointer",
              selectedRunId === run.id ? "bg-accent" : "hover:bg-muted/30",
            )}
            onClick={() =>
              onSelectRun(selectedRunId === run.id ? null : run.id)
            }
          >
            <TableCell className="!px-3 !pl-8" />
            <TableCell className="!px-3 font-mono text-xs text-muted-foreground">
              {run.id.slice(0, 8)}
            </TableCell>
            <TableCell className="!px-3 text-xs text-muted-foreground">
              {formatTimestamp(run.timestamp)}
            </TableCell>
            <TableCell className="!px-3">
              <Badge
                variant={
                  run.status === "success" ? "successStatic" : "errorStatic"
                }
                size="sm"
              >
                {run.status === "success" ? "OK" : "ERR"}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
    </>
  );
}
