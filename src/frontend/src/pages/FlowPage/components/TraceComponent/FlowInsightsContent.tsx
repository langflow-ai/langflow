import type { CellClickedEvent } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import PaginatorComponent from "@/components/common/paginatorComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetTracesQuery } from "@/controllers/API/queries/traces";
import { TraceListItem } from "@/controllers/API/queries/traces/types";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { createFlowTracesColumns } from "./config/flowTraceColumns";
import { TraceDetailView } from "./TraceDetailView";
import { downloadJson, endOfDay, startOfDay } from "./traceViewHelpers";

export function FlowInsightsContent({
  flowId,
  initialTraceId,
  refreshOnMount,
  showFlowActivityHeader,
}: {
  flowId?: string | null;
  initialTraceId?: string | null;
  refreshOnMount?: boolean;
  showFlowActivityHeader?: boolean;
}): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [rows, setRows] = useState<TraceListItem[]>([]);
  const [searchParams] = useSearchParams();
  const [tracePanelOpen, setTracePanelOpen] = useState(false);
  const [tracePanelTraceId, setTracePanelTraceId] = useState<string | null>(
    null,
  );

  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [startDate, setStartDate] = useState<string>("");
  const [endDateValue, setEndDateValue] = useState<string>("");
  const [groupBySession, setGroupBySession] = useState<boolean>(false);
  const flowIdFromUrl = searchParams.get("id");
  const resolvedFlowId = flowId ?? currentFlowId ?? flowIdFromUrl;

  const resolvedFlowName = useFlowsManagerStore((state) => {
    if (!resolvedFlowId) return state.currentFlow?.name;
    return state.getFlowById(resolvedFlowId)?.name ?? state.currentFlow?.name;
  });

  const columns = useMemo(
    () =>
      createFlowTracesColumns({
        flowId: resolvedFlowId,
        flowName: resolvedFlowName,
      }),
    [resolvedFlowId, resolvedFlowName],
  );

  const {
    data: tracesData,
    isLoading,
    refetch,
  } = useGetTracesQuery(
    {
      flowId: resolvedFlowId ?? null,
      params: {
        query: searchText.trim() ? searchText.trim() : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        start_time: startDate
          ? startOfDay(new Date(startDate)).toISOString()
          : undefined,
        end_time: endDateValue
          ? endOfDay(new Date(endDateValue)).toISOString()
          : undefined,
        page: pageIndex,
        size: pageSize,
      },
    },
    { enabled: !!resolvedFlowId },
  );

  useEffect(() => {
    if (!refreshOnMount) return;
    refetch();
  }, [refreshOnMount, refetch]);

  useEffect(() => {
    if (!initialTraceId) return;
    setTracePanelTraceId(initialTraceId);
    setTracePanelOpen(true);
  }, [initialTraceId]);

  useEffect(() => {
    if (!tracesData) return;

    setRows(tracesData.traces ?? []);
  }, [tracesData]);

  const groupedRows = useMemo(() => {
    if (!groupBySession) return [] as Array<[string, TraceListItem[]]>;
    const groups = new Map<string, TraceListItem[]>();
    rows.forEach((row) => {
      const key = row.sessionId ?? "unknown";
      const existing = groups.get(key);
      if (existing) {
        existing.push(row);
      } else {
        groups.set(key, [row]);
      }
    });
    return Array.from(groups.entries());
  }, [groupBySession, rows]);

  const expandedSessionIds = useMemo(
    () => groupedRows.map(([sessionId]) => sessionId),
    [groupedRows],
  );

  const handlePageChange = useCallback(
    (newPageIndex: number, newPageSize: number) => {
      setPageIndex(newPageIndex);
      setPageSize(newPageSize);
    },
    [],
  );

  const handleCellClicked = useCallback((event: CellClickedEvent) => {
    event.event?.preventDefault?.();
    event.event?.stopPropagation?.();

    const rowData = event.data as TraceListItem | undefined;
    setTracePanelTraceId(rowData?.id ?? null);
    setTracePanelOpen(true);
  }, []);

  const totalRuns = tracesData?.total ?? rows.length;
  const totalPages =
    tracesData?.pages ?? Math.max(1, Math.ceil(totalRuns / pageSize));

  useEffect(() => {
    if (pageIndex > totalPages) {
      setPageIndex(totalPages);
    }
  }, [pageIndex, totalPages]);

  useEffect(() => {
    setPageIndex(1);
  }, [searchText, statusFilter, startDate, endDateValue]);

  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        {showFlowActivityHeader && (
          <div
            className="border-b border-border px-4 py-3"
            data-testid="flow-activity-header"
          >
            <h2 className="text-base font-semibold">Flow Activity</h2>
          </div>
        )}
        <div className="flex flex-nowrap items-center justify-between gap-2 border-b px-4 py-2">
          <div className="flex min-w-0 items-center gap-3 whitespace-nowrap">
            <div className="flex items-center gap-3 text-sm">
              <span className="font-medium">Runs</span>
              <span className="text-muted-foreground">Total {totalRuns}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-8 gap-2 px-2 text-muted-foreground",
                groupBySession && "bg-muted text-foreground",
              )}
              onClick={() => setGroupBySession((prev) => !prev)}
              aria-pressed={groupBySession}
            >
              <IconComponent name="Layers" className="h-4 w-4" />
              Group by Session
            </Button>
          </div>

          <div className="flex min-w-0 flex-nowrap items-center gap-2">
            <div className="relative w-[220px] min-w-[180px]">
              <IconComponent
                name="Search"
                className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search runs..."
                className="h-8 text-sm"
              />
            </div>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-8 w-[130px]">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="ok">Success</SelectItem>
                <SelectItem value="error">Error</SelectItem>
              </SelectContent>
            </Select>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Date range">
                  <IconComponent name="Calendar" className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-[260px] p-3">
                <div className="flex flex-col gap-2">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">
                      Start date
                    </span>
                    <Input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="h-8 text-sm [color-scheme:light] dark:[color-scheme:white] dark:[&::-webkit-calendar-picker-indicator]:invert dark:[&::-webkit-calendar-picker-indicator]:opacity-80"
                      aria-label="Start date"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">
                      End date
                    </span>
                    <Input
                      type="date"
                      value={endDateValue}
                      onChange={(e) => setEndDateValue(e.target.value)}
                      className="h-8 text-sm [color-scheme:light] dark:[color-scheme:white] dark:[&::-webkit-calendar-picker-indicator]:invert dark:[&::-webkit-calendar-picker-indicator]:opacity-80"
                      aria-label="End date"
                    />
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => refetch()}
              aria-label="Reload"
            >
              <IconComponent name="RefreshCcw" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() =>
                downloadJson(`runs-${resolvedFlowId ?? "unknown"}.json`, rows)
              }
              aria-label="Download"
            >
              <IconComponent name="Download" className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {groupBySession ? (
            <Accordion
              type="multiple"
              defaultValue={expandedSessionIds}
              className="h-full overflow-y-auto"
            >
              {groupedRows.map(([sessionId, sessionRows]) => (
                <AccordionItem key={sessionId} value={sessionId}>
                  <AccordionTrigger className="px-4 text-sm">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-medium text-foreground">
                        Session
                      </span>
                      <span className="font-mono text-xs">{sessionId}</span>
                      <span className="text-xs">{sessionRows.length} runs</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-4 pb-4">
                    <TableComponent
                      key={`Executions-${sessionId}`}
                      readOnlyEdit
                      className="h-auto w-full"
                      domLayout="autoHeight"
                      pagination={false}
                      columnDefs={columns}
                      autoSizeStrategy={{ type: "fitGridWidth" }}
                      rowData={sessionRows}
                      headerHeight={sessionRows.length === 0 ? 0 : undefined}
                      onCellClicked={handleCellClicked}
                    />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          ) : (
            <TableComponent
              key="Executions"
              readOnlyEdit
              className="h-max-full h-full w-full"
              data-testid="flow-insights-trace-table"
              pagination={false}
              columnDefs={columns}
              autoSizeStrategy={{ type: "fitGridWidth" }}
              rowData={rows}
              headerHeight={rows.length === 0 ? 0 : undefined}
              onCellClicked={handleCellClicked}
            />
          )}
        </div>
        <div className="flex justify-end px-3 py-4">
          <PaginatorComponent
            pageIndex={pageIndex}
            pageSize={pageSize}
            totalRowsCount={tracesData?.total ?? 0}
            paginate={handlePageChange}
            pages={totalPages}
          />
        </div>
      </div>

      <Dialog
        open={tracePanelOpen}
        onOpenChange={(open) => {
          setTracePanelOpen(open);
          if (!open) setTracePanelTraceId(null);
        }}
      >
        <DialogContent
          className={
            "right-0 top-0 h-[100dvh] w-full max-w-none rounded-l-xl rounded-r-none p-0 sm:w-[70vw] " +
            "data-[state=open]:animate-in data-[state=closed]:animate-out " +
            "data-[state=open]:slide-in-from-right-1/2 data-[state=closed]:slide-out-to-right-1/2"
          }
          data-testid="flow-insights-trace-panel"
        >
          <div className="flex h-full flex-col overflow-hidden">
            <div className="flex-1 overflow-hidden">
              <TraceDetailView
                traceId={tracePanelTraceId}
                flowName={resolvedFlowName}
              />
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
