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
  status: "success" | "error" | "warning";
  startTime: string;
  latencyMs: number;
  totalTokens: number;
  totalCost: number;
  input?: string;
  output?: string;
}

interface SessionGroup {
  sessionId: string;
  runs: RunData[];
  errorCount: number;
}

interface RunsTableProps {
  runs: RunData[];
  isLoading: boolean;
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  groupBySession?: boolean;
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  if (isToday) {
    return date.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
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

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(tokens: number): string {
  if (!tokens) return "--";
  if (tokens < 1000) return String(tokens);
  return `${(tokens / 1000).toFixed(1)}k`;
}

export function RunsTable({
  runs,
  isLoading,
  selectedRunId,
  onSelectRun,
  groupBySession = true,
}: RunsTableProps) {
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
          new Date(b.startTime).getTime() - new Date(a.startTime).getTime(),
      );
      groups.push({
        sessionId,
        runs: sessionRuns,
        errorCount: sessionRuns.filter((r) => r.status === "error").length,
      });
    }

    groups.sort(
      (a, b) =>
        new Date(b.runs[0].startTime).getTime() -
        new Date(a.runs[0].startTime).getTime(),
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
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-6 w-6 animate-spin" />
          <span className="text-sm">Loading runs...</span>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="flex flex-col items-center text-muted-foreground">
          <IconComponent
            name="Activity"
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

  if (!groupBySession) {
    return (
      <div className="flex-1 overflow-auto px-4">
        <FlatRunsTable
          runs={runs}
          selectedRunId={selectedRunId}
          onSelectRun={onSelectRun}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="flex flex-col">
        {sessionGroups.map((group) => {
          const isExpanded = expandedSessions.has(group.sessionId);
          return (
            <SessionCard
              key={group.sessionId}
              group={group}
              isExpanded={isExpanded}
              onToggle={() => toggleSession(group.sessionId)}
              selectedRunId={selectedRunId}
              onSelectRun={onSelectRun}
            />
          );
        })}
      </div>
    </div>
  );
}

function SessionCard({
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
  onSelectRun: (runId: string) => void;
}) {
  return (
    <div className="pb-1 pt-2">
      {/* Session label */}
      <button
        type="button"
        className="flex items-center gap-2 px-4 py-1.5 text-left"
        onClick={onToggle}
      >
        <IconComponent
          name="ChevronRight"
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground/60 transition-transform",
            isExpanded && "rotate-90",
          )}
        />
        <span
          className="truncate font-mono text-xs text-muted-foreground"
          title={group.sessionId}
        >
          {group.sessionId}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground/70">
          {group.runs.length} run{group.runs.length !== 1 ? "s" : ""}
        </span>
        {group.errorCount > 0 && (
          <Badge variant="errorStatic" size="sm">
            {group.errorCount} err
          </Badge>
        )}
      </button>

      {/* Runs table card indented inside session */}
      {isExpanded && (
        <div className="ml-8 mr-3 mt-1.5 overflow-hidden rounded-md border border-border bg-background px-3">
          <Table className="w-full table-fixed">
            <colgroup>
              <col style={{ width: "18%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "22%" }} />
              <col style={{ width: "22%" }} />
              <col style={{ width: "7%" }} />
              <col style={{ width: "8%" }} />
              <col style={{ width: "5%" }} />
            </colgroup>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Run</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Timestamp</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Input</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Output</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Tokens</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Latency</TableHead>
                <TableHead className="!px-3 !py-1.5 text-xs text-muted-foreground">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {group.runs.map((run) => (
                <TableRow
                  key={run.id}
                  className={cn(
                    "cursor-pointer transition-colors",
                    selectedRunId === run.id
                      ? "bg-primary/5"
                      : "hover:bg-muted/20",
                  )}
                  onClick={() => onSelectRun(run.id)}
                >
                  <TableCell className="!px-3 !py-2 overflow-hidden">
                    <span
                      className="block truncate text-xs font-medium"
                      title={run.name}
                    >
                      {run.name}
                    </span>
                  </TableCell>
                  <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
                    {formatTimestamp(run.startTime)}
                  </TableCell>
                  <TableCell className="!px-3 !py-2 overflow-hidden">
                    <span
                      className="block truncate text-xs text-muted-foreground"
                      title={run.input || ""}
                    >
                      {run.input || "--"}
                    </span>
                  </TableCell>
                  <TableCell className="!px-3 !py-2 overflow-hidden">
                    <span
                      className="block truncate text-xs text-muted-foreground"
                      title={run.output || ""}
                    >
                      {run.output || "--"}
                    </span>
                  </TableCell>
                  <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
                    {formatTokens(run.totalTokens)}
                  </TableCell>
                  <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
                    {formatLatency(run.latencyMs)}
                  </TableCell>
                  <TableCell className="!px-3 !py-2">
                    <StatusIndicator status={run.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function StatusIndicator({ status }: { status: RunData["status"] }) {
  return (
    <div className="flex items-center justify-center">
      <IconComponent
        name={
          status === "success"
            ? "CheckCircle2"
            : status === "error"
              ? "XCircle"
              : "AlertCircle"
        }
        className={cn(
          "h-4 w-4",
          status === "success" && "text-emerald-500",
          status === "error" && "text-destructive",
          status === "warning" && "text-yellow-500",
        )}
      />
    </div>
  );
}

function FlatRunsTable({
  runs,
  selectedRunId,
  onSelectRun,
}: {
  runs: RunData[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}) {
  return (
    <Table className="w-full table-fixed">
      <colgroup>
        <col style={{ width: "18%" }} />
        <col style={{ width: "12%" }} />
        <col style={{ width: "22%" }} />
        <col style={{ width: "22%" }} />
        <col style={{ width: "7%" }} />
        <col style={{ width: "8%" }} />
        <col style={{ width: "5%" }} />
      </colgroup>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="!px-3 text-xs text-muted-foreground">Run</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Timestamp</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Input</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Output</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Tokens</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Latency</TableHead>
          <TableHead className="!px-3 text-xs text-muted-foreground">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow
            key={run.id}
            className={cn(
              "cursor-pointer transition-colors",
              selectedRunId === run.id
                ? "bg-primary/5"
                : "hover:bg-muted/30",
            )}
            onClick={() => onSelectRun(run.id)}
          >
            <TableCell className="!px-3 !py-2 overflow-hidden">
              <span
                className="block truncate text-xs font-medium"
                title={run.name}
              >
                {run.name}
              </span>
            </TableCell>
            <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
              {formatTimestamp(run.startTime)}
            </TableCell>
            <TableCell className="!px-3 !py-2 overflow-hidden">
              <span
                className="block truncate text-xs text-muted-foreground"
                title={run.input || ""}
              >
                {run.input || "--"}
              </span>
            </TableCell>
            <TableCell className="!px-3 !py-2 overflow-hidden">
              <span
                className="block truncate text-xs text-muted-foreground"
                title={run.output || ""}
              >
                {run.output || "--"}
              </span>
            </TableCell>
            <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
              {formatTokens(run.totalTokens)}
            </TableCell>
            <TableCell className="!px-3 !py-2 text-xs text-muted-foreground">
              {formatLatency(run.latencyMs)}
            </TableCell>
            <TableCell className="!px-3 !py-2">
              <StatusIndicator status={run.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
