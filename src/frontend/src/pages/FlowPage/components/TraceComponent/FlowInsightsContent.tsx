import type { CellClickedEvent } from "ag-grid-community";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useDeleteTracesMutation,
  useGetTracesQuery,
} from "@/controllers/API/queries/traces";
import { TraceListItem } from "@/controllers/API/queries/traces/types";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import { createFlowTracesColumns } from "./config/flowTraceColumns";
import { DateRangePopover } from "./DateRangePopover";
import { TraceDetailView } from "./TraceDetailView";
import { downloadJson, toUtcIsoForDate } from "./traceViewHelpers";
import { RenderGroupedSessionType } from "./types";

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
  const { t } = useTranslation();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [pageIndex, setPageIndex] = useState(1);
  const [pageSize, setPageSize] = useState(20);
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
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const flowIdFromUrl = searchParams.get("id");
  const resolvedFlowId = flowId ?? currentFlowId ?? flowIdFromUrl;

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutate: deleteTraces } = useDeleteTracesMutation({
    onSuccess: () => {
      setSuccessData({ title: t("trace.clearedSuccess") });
      refetch();
    },
    onError: (error) => {
      setErrorData({
        title: t("trace.clearError"),
        list: [error.message],
      });
    },
  });

  const handleClearAll = useCallback(() => {
    const trustedFlowId = flowId ?? currentFlowId;
    if (trustedFlowId) {
      deleteTraces({ flow_id: trustedFlowId });
    }
  }, [flowId, currentFlowId, deleteTraces]);

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
        start_time:
          startDate && !(endDateValue && endDateValue < startDate)
            ? toUtcIsoForDate(startDate, false)
            : undefined,
        end_time:
          endDateValue && !(startDate && endDateValue < startDate)
            ? toUtcIsoForDate(endDateValue, true)
            : undefined,
        page: pageIndex,
        size: pageSize,
      },
    },
    {
      enabled: !!resolvedFlowId,
      refetchOnMount: refreshOnMount ? "always" : true,
    },
  );

  const rows = tracesData?.traces ?? [];

  useEffect(() => {
    if (!initialTraceId) return;
    setTracePanelTraceId(initialTraceId);
    setTracePanelOpen(true);
  }, [initialTraceId]);

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
  }, [groupBySession, tracesData]);

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
  const totalPages = Math.max(
    1,
    tracesData?.pages ?? Math.ceil(totalRuns / pageSize),
  );

  useEffect(() => {
    if (pageIndex > totalPages) {
      setPageIndex(totalPages);
    }
  }, [pageIndex, totalPages]);

  useEffect(() => {
    setPageIndex(1);
  }, [searchText, statusFilter, startDate, endDateValue]);

  function renderGroupedSessionContent({
    groupedRows,
    isLoading,
    columns,
    expandedSessionIds,
    handleCellClicked,
  }: RenderGroupedSessionType) {
    if (groupedRows.length === 0 && !isLoading) {
      return (
        <div className="flex h-full w-full items-center justify-center rounded-md border">
          <Alert variant="default" className="w-fit">
            <IconComponent
              name="AlertCircle"
              className="h-5 w-5 text-primary"
            />
            <AlertTitle>{t("table.noDataTitle")}</AlertTitle>
            <AlertDescription>{t("table.noDataMessage")}</AlertDescription>
          </Alert>
        </div>
      );
    }
    return (
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
                  {t("trace.session")}
                </span>
                <span className="font-mono text-xs">{sessionId}</span>
                <span className="text-xs">
                  {t("trace.runsCount", { count: sessionRows.length })}
                </span>
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
    );
  }

  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        {showFlowActivityHeader && (
          <div
            className="border-b border-border px-4 py-3"
            data-testid="flow-activity-header"
          >
            <h2 className="text-base font-semibold">
              {t("trace.flowActivity")}
            </h2>
          </div>
        )}
        <div className="flex flex-nowrap items-center justify-between gap-2 border-b px-4 py-2">
          <div className="flex min-w-0 items-center gap-3 whitespace-nowrap">
            <div className="flex items-center gap-3 text-sm">
              <span className="font-medium">{t("trace.runs")}</span>
              <span className="text-muted-foreground">
                {t("trace.total", { count: totalRuns })}
              </span>
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
              {t("trace.groupBySession")}
            </Button>
          </div>

          <div className="flex min-w-0 flex-nowrap items-center gap-2">
            <div className="w-[220px] min-w-[180px]">
              <Input
                icon="Search"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder={t("trace.searchRuns")}
                inputClassName="h-8 text-sm"
              />
            </div>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="h-8 w-[130px] [&>span]:truncate">
                <SelectValue placeholder={t("trace.allStatus")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("trace.allStatus")}</SelectItem>
                <SelectItem value="ok">{t("trace.success")}</SelectItem>
                <SelectItem value="error">{t("trace.error")}</SelectItem>
              </SelectContent>
            </Select>

            <DateRangePopover
              startDate={startDate}
              endDate={endDateValue}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDateValue}
            />

            {totalRuns > 0 && (
              <Button
                variant="ghost"
                className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
                aria-label={t("trace.clearAll")}
                onClick={(e) => {
                  (e.currentTarget as HTMLButtonElement).blur();
                  setClearConfirmOpen(true);
                }}
              >
                <IconComponent name="Trash2" className="h-4 w-4" />
              </Button>
            )}
            <Dialog open={clearConfirmOpen} onOpenChange={setClearConfirmOpen}>
              <DialogContent className="max-w-sm">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <IconComponent
                      name="Trash2"
                      className="h-5 w-5 text-destructive"
                    />
                    {t("trace.clearAllRecords")}
                  </DialogTitle>
                </DialogHeader>
                <p className="text-sm text-muted-foreground">
                  {t("trace.clearAllConfirm")}
                </p>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setClearConfirmOpen(false)}
                  >
                    {t("trace.cancel")}
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => {
                      handleClearAll();
                      setClearConfirmOpen(false);
                    }}
                  >
                    {t("trace.clearAll")}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => refetch()}
              aria-label={t("trace.reload")}
            >
              <IconComponent name="RefreshCcw" className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() =>
                downloadJson(`runs-${resolvedFlowId ?? "unknown"}.json`, rows)
              }
              aria-label={t("trace.download")}
            >
              <IconComponent name="Download" className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="ag-flush-mode flex-1 overflow-hidden">
          {groupBySession ? (
            renderGroupedSessionContent({
              groupedRows,
              isLoading,
              columns,
              expandedSessionIds,
              handleCellClicked,
            })
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
        <div className="flex justify-end border-t px-3 py-4">
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
            "right-0 top-0 h-dvh w-full max-w-none rounded-none p-0 sm:w-[65vw] " +
            "data-[state=open]:animate-in data-[state=closed]:animate-out " +
            "data-[state=open]:slide-in-from-right-1/2 data-[state=closed]:slide-out-to-right-1/2"
          }
          closeButtonClassName="top-1"
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
