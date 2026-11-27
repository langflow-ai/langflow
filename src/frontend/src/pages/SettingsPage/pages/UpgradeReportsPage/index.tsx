import { keepPreviousData } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  UPGRADE_REPORTS_PAGE_SIZE,
  useGetUpgradeReport,
  useGetUpgradeReports,
} from "@/controllers/API/queries/upgrade-reports";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { reportAssessment, reportTime } from "./format";
import ImportReport from "./ImportReport";
import MaintenanceControls from "./MaintenanceControls";
import ReportView from "./ReportView";
import RunCheck from "./RunCheck";

export default function UpgradeReportsPage() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.userData);
  if (user === null) return <p role="status">{t("common.loading")}</p>;
  return user.is_superuser ? (
    <UpgradeReports />
  ) : (
    <CustomNavigate replace to="/" />
  );
}

function UpgradeReports() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const [pickAfterPageLoad, setPickAfterPageLoad] = useState<
    "first" | "last" | null
  >(null);
  const [importOpen, setImportOpen] = useState(false);
  const [unappliedUpdates, setUnappliedUpdates] = useState(false);
  const history = useGetUpgradeReports(
    { offset },
    { placeholderData: keepPreviousData },
  );
  const items = history.data?.items ?? [];
  const total = history.data?.total ?? 0;
  const id = params.get("report") ?? items[0]?.id ?? "";
  const report = useGetUpgradeReport({ id });
  const [focusReport, setFocusReport] = useState<string | null>(null);
  useEffect(() => {
    if (!focusReport || id !== focusReport || report.data?.id !== id) return;
    const heading = document.getElementById("upgrade-report-title");
    heading?.scrollIntoView({ behavior: "smooth", block: "start" });
    heading?.focus({ preventScroll: true });
    setFocusReport(null);
  }, [id, report.data?.id, focusReport]);
  useEffect(() => {
    if (!pickAfterPageLoad || history.isFetching || !history.data) return;
    const pick =
      pickAfterPageLoad === "first" ? items[0] : items[items.length - 1];
    setPickAfterPageLoad(null);
    if (pick) setParams({ report: pick.id });
  }, [pickAfterPageLoad, history.isFetching, history.data]);
  const select = (reportId: string, focus = false) => {
    setPickAfterPageLoad(null);
    setFocusReport(focus ? reportId : null);
    setParams({ report: reportId });
  };
  const index = items.findIndex((item) => item.id === id);
  const position = index >= 0 ? offset + index + 1 : null;
  const firstOnPage = position === null ? offset === 0 : position <= 1;
  const lastOnPage =
    position === null
      ? offset + UPGRADE_REPORTS_PAGE_SIZE >= total
      : position >= total;
  const step = (by: -1 | 1) => {
    if (history.isFetching) return;
    const next = items[index + by];
    if (next) return select(next.id);
    setOffset(offset + by * UPGRADE_REPORTS_PAGE_SIZE);
    setPickAfterPageLoad(by < 0 ? "last" : "first");
  };
  const importLink = (label: string) => (
    <Button
      variant="link"
      className="h-auto p-0"
      onClick={() => setImportOpen(true)}
      ignoreTitleCase
    >
      {label}
    </Button>
  );

  return (
    <div
      className="relative flex min-w-0 flex-col gap-6 pb-8"
      data-testid="upgrade-reports-page"
    >
      <div>
        <h2 className="text-lg font-semibold tracking-tight">
          {t("settings.upgrade.title")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("settings.upgrade.description")}
        </p>
      </div>
      <MaintenanceControls unappliedUpdates={unappliedUpdates} />
      <RunCheck
        onSelectReport={(reportId, focus) => {
          setOffset(0);
          select(reportId, focus);
        }}
      >
        <p className="text-sm">
          {t("settings.upgrade.importPrompt")}{" "}
          {importLink(t("settings.upgrade.import"))}
        </p>
      </RunCheck>
      <ImportReport
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={(reportId) => {
          setOffset(0);
          select(reportId, true);
        }}
      />
      <section
        aria-labelledby="upgrade-history-title"
        className="min-w-0 space-y-3 rounded-lg border p-4"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <h3 id="upgrade-history-title" className="font-medium">
              {t("settings.upgrade.history")}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t("settings.upgrade.historyHelp")}
            </p>
          </div>
          {items.length > 0 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                aria-label={t("settings.upgrade.previousReport")}
                disabled={firstOnPage}
                onClick={() => step(-1)}
                ignoreTitleCase
              >
                {t("settings.upgrade.previous")}
              </Button>
              {position !== null && (
                <span className="text-sm tabular-nums text-muted-foreground">
                  {t("settings.upgrade.position", { position, total })}
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                aria-label={t("settings.upgrade.nextReport")}
                disabled={lastOnPage}
                onClick={() => step(1)}
                ignoreTitleCase
              >
                {t("settings.upgrade.next")}
              </Button>
            </div>
          )}
        </div>
        {history.isLoading && <p role="status">{t("common.loading")}</p>}
        {history.isError && (
          <p role="alert">
            {t("settings.upgrade.loadError")}{" "}
            <Button
              variant="outline"
              onClick={() => history.refetch()}
              ignoreTitleCase
            >
              {t("common.retry")}
            </Button>
          </p>
        )}
        {history.data?.total === 0 && (
          <div className="space-y-1 rounded-md border border-dashed p-6 text-center text-sm">
            <p className="font-medium">{t("settings.upgrade.empty")}</p>
            <p className="text-muted-foreground">
              {t("settings.upgrade.emptyHelp")}
            </p>
            {importLink(t("settings.upgrade.importExisting"))}
          </div>
        )}
        {items.length > 0 && (
          <label className="flex flex-col gap-1 text-sm">
            {t("settings.upgrade.chooseReport")}
            <select
              className="max-w-full rounded border border-control bg-background p-2"
              value={items.some((item) => item.id === id) ? id : ""}
              onChange={(event) => select(event.target.value)}
            >
              <option value="" disabled>
                {t("settings.upgrade.chooseReport")}
              </option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.duplicate &&
                    `${t("settings.upgrade.duplicateImport")} · `}
                  {t("settings.upgrade.historyEntry", {
                    source:
                      item.source_database?.split(/[\\/]/).pop() ||
                      t("settings.upgrade.unknown"),
                    assessment: t(
                      `settings.upgrade.assessment.${reportAssessment(Boolean(item.incomplete), item.failing_count, item.warning_count)}`,
                    ),
                    target: item.target_version,
                    time: reportTime(
                      item.created_at,
                      i18n.language,
                      t("settings.upgrade.unknown"),
                    ),
                    count: item.flow_count,
                    id: item.id,
                  })}
                </option>
              ))}
            </select>
          </label>
        )}
        {report.isLoading && id && <p role="status">{t("common.loading")}</p>}
        {report.isError && (
          <p role="alert">
            {t("settings.upgrade.loadError")}{" "}
            <Button
              variant="outline"
              onClick={() => report.refetch()}
              ignoreTitleCase
            >
              {t("common.retry")}
            </Button>
          </p>
        )}
      </section>
      {report.data && (
        <ReportView
          key={report.data.id}
          report={report.data}
          onUnappliedUpdatesChange={setUnappliedUpdates}
        />
      )}
    </div>
  );
}
