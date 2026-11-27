import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  useGetUpgradeReport,
  useGetUpgradeReports,
  useImportUpgradeReport,
} from "@/controllers/API/queries/upgrade-reports";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { reportAssessment, reportTime } from "./format";
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
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState(false);
  const history = useGetUpgradeReports({ offset });
  const id = params.get("report") ?? history.data?.items[0]?.id ?? "";
  const report = useGetUpgradeReport({ id });
  const [focusReport, setFocusReport] = useState<string | null>(null);
  useEffect(() => {
    if (!focusReport || id !== focusReport || report.data?.id !== id) return;
    const heading = document.getElementById("upgrade-report-title");
    heading?.scrollIntoView({ behavior: "smooth", block: "start" });
    heading?.focus({ preventScroll: true });
    setFocusReport(null);
  }, [id, report.data?.id, focusReport]);
  const imported = useImportUpgradeReport();
  const upload = () => {
    if (!file) return;
    setFileError(false);
    imported.mutate(file, {
      onSuccess: (response) => {
        setFocusReport(null);
        setOffset(0);
        setParams({ report: response.id });
      },
    });
  };

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
      <details
        key={history.data?.total === 0 ? "empty" : "history"}
        open={history.data?.total === 0}
        aria-labelledby="upgrade-workflow-title"
        className="space-y-3 rounded-lg border p-4"
      >
        <summary
          id="upgrade-workflow-title"
          className="cursor-pointer font-medium"
        >
          {t("settings.upgrade.workflowTitle")}
        </summary>
        <ol className="list-decimal space-y-2 pl-5 text-sm">
          <li>{t("settings.upgrade.workflowAssess")}</li>
          <li>{t("settings.upgrade.workflowReview")}</li>
          <li>{t("settings.upgrade.workflowRepair")}</li>
        </ol>
        <p className="text-sm">{t("settings.upgrade.commandHelp")}</p>
        <pre className="whitespace-pre-wrap break-all rounded bg-muted p-3 text-sm">
          <code>
            {
              "langflow upgrade-check --database-url <source-database-url> --output upgrade-report.json"
            }
          </code>
        </pre>
      </details>
      <RunCheck
        onSelectReport={(reportId, focus) => {
          setOffset(0);
          setParams({ report: reportId });
          setFocusReport(focus ? reportId : null);
        }}
      />
      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <section
          aria-labelledby="upgrade-import-title"
          className="min-w-0 space-y-3 rounded-lg border p-4"
        >
          <h3 id="upgrade-import-title" className="font-medium">
            {t("settings.upgrade.importTitle")}
          </h3>
          <label className="flex flex-col gap-2">
            {t("settings.upgrade.file")}
            <input
              type="file"
              aria-describedby="upgrade-import-help upgrade-import-feedback"
              aria-invalid={fileError || imported.isError}
              accept="application/json,.json"
              className="w-full min-w-0 max-w-full rounded-md border border-input bg-background p-2 text-sm file:mr-2 file:rounded file:border-0 file:bg-muted file:px-2 file:py-1 file:text-foreground"
              onChange={(event) => {
                imported.reset();
                const chosen = event.target.files?.[0] ?? null;
                setFileError(Boolean(chosen && chosen.size > 20 * 1024 * 1024));
                setFile(
                  chosen && chosen.size <= 20 * 1024 * 1024 ? chosen : null,
                );
              }}
            />
          </label>
          <p id="upgrade-import-help" className="text-sm text-muted-foreground">
            {t("settings.upgrade.importHelp")}
          </p>
          <Button
            disabled={!file || imported.isPending}
            onClick={upload}
            ignoreTitleCase
          >
            {t("settings.upgrade.import")}
          </Button>
          <div id="upgrade-import-feedback">
            {(fileError || imported.isError) && (
              <p role="alert">
                {t(
                  imported.error?.response?.data?.detail?.code ===
                    "unsupported_upgrade_report_format"
                    ? "settings.upgrade.unsupportedFormat"
                    : "settings.upgrade.importError",
                )}
              </p>
            )}
            {imported.isPending && (
              <p role="status">{t("settings.upgrade.importing")}</p>
            )}
            {imported.isSuccess && !imported.isPending && !fileError && (
              <p role="status">{t("settings.upgrade.importSuccess")}</p>
            )}
          </div>
        </section>
        <section
          aria-labelledby="upgrade-history-title"
          className="min-w-0 space-y-3 rounded-lg border p-4"
        >
          <h3 id="upgrade-history-title" className="font-medium">
            {t("settings.upgrade.history")}
          </h3>
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
          {history.data?.total === 0 && <p>{t("settings.upgrade.empty")}</p>}
          {history.data && history.data.items.length > 0 && (
            <>
              <label className="flex flex-col gap-1">
                {t("settings.upgrade.chooseReport")}
                <select
                  className="max-w-full rounded border border-control bg-background p-2"
                  value={
                    history.data.items.some((item) => item.id === id) ? id : ""
                  }
                  onChange={(event) => {
                    setFocusReport(null);
                    setParams({ report: event.target.value });
                  }}
                >
                  <option value="" disabled>
                    {t("settings.upgrade.chooseReport")}
                  </option>
                  {history.data.items.map((item) => (
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
              {history.data.total > 20 && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - 20))}
                    ignoreTitleCase
                  >
                    {t("settings.upgrade.previous")}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={offset + 20 >= history.data.total}
                    onClick={() => setOffset(offset + 20)}
                    ignoreTitleCase
                  >
                    {t("settings.upgrade.next")}
                  </Button>
                </div>
              )}
            </>
          )}
        </section>
      </div>
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
      {report.data && <ReportView key={report.data.id} report={report.data} />}
    </div>
  );
}
