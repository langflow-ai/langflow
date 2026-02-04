import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";

type LogsTab = "logs" | "traces";

interface LogsSidebarGroupProps {
  activeTab: LogsTab;
  onTabChange: (tab: LogsTab) => void;
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

/**
 * Format time for display
 */
function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/**
 * Sidebar group for logs section
 * - Logs tab: Just shows tabs (main content has the full table)
 * - Traces tab: Shows tabs + run selector (to pick which run to view trace for)
 */
const LogsSidebarGroup = ({
  activeTab,
  onTabChange,
  selectedRunId,
  onSelectRun,
}: LogsSidebarGroupProps) => {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  // Fetch transactions for run list (only needed for Traces tab)
  const { data: transactionsData, isLoading } = useGetTransactionsQuery({
    id: currentFlowId,
    params: { page: 1, size: 50 },
    mode: "union",
  });

  // Sort runs by timestamp (newest first)
  const runs = useMemo(() => {
    if (!transactionsData?.rows) return [];
    return [...transactionsData.rows].sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
  }, [transactionsData]);

  // Auto-select first run when switching to Traces tab
  useEffect(() => {
    if (activeTab === "traces" && runs.length > 0 && !selectedRunId) {
      onSelectRun(runs[0].id || runs[0].vertex_id);
    }
  }, [activeTab, runs, selectedRunId, onSelectRun]);

  return (
    <SidebarGroup className="flex h-full flex-col p-3 pr-2">
      {/* Tabs */}
      <SidebarGroupLabel className="mb-3 flex w-full cursor-default items-center justify-center">
        <Tabs
          value={activeTab}
          onValueChange={(v) => onTabChange(v as LogsTab)}
          className="w-full"
        >
          <TabsList className="w-full">
            <TabsTrigger value="logs" className="flex-1">
              Logs
            </TabsTrigger>
            <TabsTrigger value="traces" className="flex-1">
              Traces
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </SidebarGroupLabel>

      <SidebarGroupContent className="flex-1 overflow-auto">
        {activeTab === "logs" ? (
          // Logs tab: Just show explanation - table is in main content
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <IconComponent
              name="ScrollText"
              className="mb-2 h-8 w-8 text-muted-foreground opacity-50"
            />
            <p className="text-sm text-muted-foreground">
              View all runs in the table
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Click a row to see its trace
            </p>
          </div>
        ) : (
          // Traces tab: Show run selector
          <>
            <div className="mb-2 px-1 text-xs font-medium text-muted-foreground">
              Select a run
            </div>

            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <IconComponent
                  name="Loader2"
                  className="h-5 w-5 animate-spin text-muted-foreground"
                />
              </div>
            )}

            {!isLoading && runs.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <IconComponent
                  name="Activity"
                  className="mb-2 h-8 w-8 text-muted-foreground opacity-50"
                />
                <p className="text-sm text-muted-foreground">No runs yet</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Run your flow to see traces
                </p>
              </div>
            )}

            {!isLoading && runs.length > 0 && (
              <SidebarMenu>
                {runs.map((run, idx) => {
                  const runId = run.id || run.vertex_id;
                  const isSelected = selectedRunId === runId;
                  return (
                    <SidebarMenuItem key={runId}>
                      <div
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors hover:bg-muted/50",
                          isSelected && "bg-muted",
                        )}
                        onClick={() => onSelectRun(runId)}
                      >
                        <Badge
                          variant={
                            run.status === "error"
                              ? "errorStatic"
                              : "successStatic"
                          }
                          size="xq"
                          className="h-5 w-5 shrink-0 p-0"
                        >
                          <IconComponent
                            name={run.status === "error" ? "X" : "Check"}
                            className="h-3 w-3"
                          />
                        </Badge>
                        <span className="flex-1 font-mono text-xs">
                          {runId.slice(0, 8)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatTime(run.timestamp)}
                        </span>
                        {idx === 0 && (
                          <Badge variant="outline" size="xq" className="ml-1">
                            latest
                          </Badge>
                        )}
                      </div>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            )}
          </>
        )}
      </SidebarGroupContent>
    </SidebarGroup>
  );
};

export default LogsSidebarGroup;
