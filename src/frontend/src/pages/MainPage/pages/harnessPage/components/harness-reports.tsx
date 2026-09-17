/* Hallmark · component: report workbench · genre: modern-minimal · design-system: DESIGN.md
 * pre-emit critique: P4 H5 E4 S5 R5 V4 · desktop: verified */
import { isAxiosError } from "axios";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  downloadProjectReport,
  type ReportSummary,
  type SourcedReport,
  useProjectReport,
  useProjectReports,
} from "@/controllers/API/queries/folders/use-project-reports";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { cn } from "@/utils/utils";
import { ReportConfigurations } from "./report-configurations";
import { ReportDependencies } from "./report-dependencies";
import { ReportEvidence } from "./report-evidence";
import { ReportMarkdown, reportCitations } from "./report-markdown";

type ReportBrowserProps = { projectId: string; onOpenFlow?: () => void };

export function HarnessReports({ projectId, onOpenFlow }: ReportBrowserProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button ref={trigger} variant="outline" size="sm">
          {t("reports.open")}
        </Button>
      </DialogTrigger>
      <DialogContent
        className="h-[90vh] w-[96vw] max-w-[1440px] gap-0 overflow-hidden p-0"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          trigger.current?.focus();
        }}
      >
        <div className="border-b border-border px-6 py-4 pr-14">
          <DialogTitle>{t("reports.title")}</DialogTitle>
          <DialogDescription className="mt-1">
            {t("reports.description")}
          </DialogDescription>
        </div>
        {open && (
          <ReportBrowser
            key={projectId}
            projectId={projectId}
            onOpenFlow={onOpenFlow}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function ReportBrowser({ projectId, onOpenFlow }: ReportBrowserProps) {
  const { t, i18n } = useTranslation();
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const [selected, setSelected] = useState<ReportSummary>();
  const list = useProjectReports({
    projectId,
    cursor: cursors[cursors.length - 1],
  });
  const current = selected ?? list.data?.items[0];
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)]">
      <nav
        aria-label={t("reports.title")}
        className="flex min-h-0 flex-col border-r border-border"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <span className="text-xs font-medium text-muted-foreground">
            {t("reports.newestFirst")}
          </span>
          <Button
            ignoreTitleCase
            size="sm"
            variant="ghost"
            disabled={list.isFetching}
            loading={list.isFetching}
            onClick={() => {
              setSelected(undefined);
              if (cursors.length > 1) setCursors([undefined]);
              else void list.refetch();
            }}
          >
            {t("reports.refresh")}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {list.isLoading ? (
            <LoadingReport />
          ) : list.isError ? (
            <ReportError
              message={t("reports.listError")}
              retry={() => void list.refetch()}
            />
          ) : (
            <>
              {!!list.data?.unavailable_count && (
                <p
                  role="status"
                  className="border-b border-border p-4 text-xs text-muted-foreground"
                >
                  {t("reports.skipped", { count: list.data.unavailable_count })}
                </p>
              )}
              {list.data?.items.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  aria-current={current?.id === item.id ? "true" : undefined}
                  className={cn(
                    "w-full space-y-2 border-b border-border p-4 text-left hover:bg-muted focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                    current?.id === item.id &&
                      "border-l-2 border-l-foreground bg-muted",
                  )}
                  onClick={() => setSelected(item)}
                >
                  <span className="block break-words text-sm font-medium">
                    {item.title}
                  </span>
                  <time
                    className="block text-xs text-muted-foreground"
                    dateTime={item.created_at}
                  >
                    {new Date(item.created_at).toLocaleString(i18n.language)}
                  </time>
                  <span className="block text-xs text-muted-foreground">
                    {t("reports.sourceCount", { count: item.source_count })}
                  </span>
                </button>
              ))}
            </>
          )}
        </div>
        {(cursors.length > 1 || list.data?.next_cursor) && (
          <div className="flex justify-between gap-1 border-t border-border p-3">
            <Button
              variant="ghost"
              size="sm"
              disabled={cursors.length === 1 || list.isFetching}
              onClick={() => {
                setSelected(undefined);
                setCursors((values) => values.slice(0, -1));
              }}
            >
              {t("reports.newer")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={!list.data?.next_cursor || list.isFetching}
              onClick={() => {
                if (list.data?.next_cursor) {
                  setSelected(undefined);
                  setCursors((values) => [...values, list.data!.next_cursor!]);
                }
              }}
            >
              {t("reports.older")}
            </Button>
          </div>
        )}
      </nav>
      {list.isError ? (
        <div />
      ) : current ? (
        <ReportReader
          key={current.id}
          projectId={projectId}
          summary={current}
          onOpenFlow={onOpenFlow}
        />
      ) : list.isLoading ? (
        <LoadingReport />
      ) : (
        <div className="m-auto max-w-sm space-y-3 p-6 text-center">
          <h2 className="text-lg font-semibold">{t("reports.emptyTitle")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("reports.emptyHelp")}
          </p>
        </div>
      )}
    </div>
  );
}

function ReportReader({
  projectId,
  summary,
  onOpenFlow,
}: ReportBrowserProps & {
  summary: ReportSummary;
}) {
  const { t } = useTranslation();
  const report = useProjectReport({
    projectId,
    flowId: summary.execution.flow_id,
    reportId: summary.id,
  });
  if (report.isLoading) return <LoadingReport />;
  if (report.isError) {
    const status = isAxiosError(report.error)
      ? report.error.response?.status
      : undefined;
    const key =
      status === 409
        ? "reports.invalidReport"
        : status === 404
          ? "reports.notFound"
          : "reports.detailError";
    return <ReportError message={t(key)} retry={() => void report.refetch()} />;
  }
  return report.data ? (
    <ReportContent
      projectId={projectId}
      report={report.data}
      onOpenFlow={onOpenFlow}
    />
  ) : null;
}

function ReportContent({
  projectId,
  report,
  onOpenFlow,
}: ReportBrowserProps & {
  report: SourcedReport;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useCustomNavigate();
  const citations = reportCitations(report.markdown);
  const sourceIds = [
    ...new Set([...citations, ...report.sources.map((source) => source.id)]),
  ];
  const [selectedSource, setSelectedSource] = useState(sourceIds[0] ?? "");
  const sourcePicker = useRef<HTMLSelectElement>(null);
  const [downloading, setDownloading] = useState<"markdown" | "json">();
  const [downloadError, setDownloadError] = useState(false);
  const unresolved = citations.filter(
    (id) =>
      !report.sources.some(
        (source) => source.id === id && source.availability === "available",
      ),
  );
  async function download(format: "markdown" | "json") {
    setDownloading(format);
    setDownloadError(false);
    try {
      await downloadProjectReport(
        { projectId, flowId: report.execution.flow_id, reportId: report.id },
        format,
      );
    } catch {
      setDownloadError(true);
    } finally {
      setDownloading(undefined);
    }
  }
  return (
    <div
      className="grid min-h-0 min-w-0 grid-cols-[minmax(0,1fr)_minmax(280px,38%)]"
      data-testid="report-reader"
    >
      <article className="min-w-0 overflow-y-auto p-6">
        <div className="mb-6 space-y-4 border-b border-border pb-5">
          <time
            className="text-xs text-muted-foreground"
            dateTime={report.created_at}
          >
            {new Date(report.created_at).toLocaleString(i18n.language)}
          </time>
          <h2 className="break-words text-2xl font-semibold tracking-tight">
            {report.title}
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button
              ignoreTitleCase
              size="sm"
              variant="outline"
              disabled={!!downloading}
              loading={downloading === "markdown"}
              onClick={() => void download("markdown")}
            >
              {t("reports.downloadMarkdown")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!downloading}
              ignoreTitleCase
              loading={downloading === "json"}
              onClick={() => void download("json")}
            >
              {t("reports.downloadEvidence")}
            </Button>
          </div>
          {downloadError && (
            <p role="alert" className="text-sm text-destructive">
              {t("reports.downloadError")}
            </p>
          )}
          <div className="space-y-1 text-xs text-muted-foreground">
            <p
              className={
                unresolved.length
                  ? "font-medium text-destructive"
                  : "font-medium text-foreground"
              }
            >
              {t(
                !citations.length
                  ? "reports.noCitations"
                  : unresolved.length
                    ? "reports.unresolved"
                    : "reports.resolved",
                { count: unresolved.length || citations.length },
              )}
            </p>
            <p>{t("reports.claimsNotEvaluated")}</p>
          </div>
        </div>
        <ReportMarkdown
          markdown={report.markdown}
          onCitation={(id) => {
            setSelectedSource(id);
            sourcePicker.current?.focus();
          }}
        />
        <ReportDependencies
          uses={report.tool_dependencies ?? []}
          harnessId={projectId}
          onOpen={onOpenFlow}
        />
        <ReportConfigurations
          key={report.id}
          configurations={report.configurations ?? []}
          onOpen={onOpenFlow}
        />
        <details className="mt-8 border-t border-border pt-4 text-xs">
          <summary className="cursor-pointer font-medium">
            {t("reports.execution")}
          </summary>
          <dl className="my-4 grid gap-2 break-all font-mono text-muted-foreground">
            <div>
              <dt className="font-sans">{t("reports.run")}</dt>
              <dd>{report.execution.run_id}</dd>
            </div>
            <div>
              <dt className="font-sans">{t("reports.output")}</dt>
              <dd>{report.execution.node_id}</dd>
            </div>
          </dl>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              onOpenFlow?.();
              navigate(`/flow/${report.execution.flow_id}`);
            }}
          >
            {t("reports.openFlow")}
          </Button>
        </details>
      </article>
      <ReportEvidence
        report={report}
        sourceIds={sourceIds}
        selectedId={selectedSource}
        onSelect={setSelectedSource}
        selectRef={sourcePicker}
      />
    </div>
  );
}

function LoadingReport() {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-label={t("reports.loading")}
      className="space-y-4 p-5"
    >
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

function ReportError({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div role="alert" className="space-y-3 p-5 text-sm">
      <p>{message}</p>
      <Button variant="outline" size="sm" onClick={retry}>
        {t("reports.retry")}
      </Button>
    </div>
  );
}
