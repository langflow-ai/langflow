import { useState } from "react";
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
import { reportTime } from "./format";
import ReportView from "./ReportView";

export default function UpgradeReportsPage() {
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  return isSuperuser ? <UpgradeReports /> : <CustomNavigate replace to="/" />;
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
  const imported = useImportUpgradeReport();
  const upload = () => {
    if (!file) return;
    setFileError(false);
    imported.mutate(file, {
      onSuccess: (response) => {
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
      <section
        aria-labelledby="upgrade-import-title"
        className="space-y-3 rounded border p-4"
      >
        <h3 id="upgrade-import-title" className="font-medium">
          {t("settings.upgrade.importTitle")}
        </h3>
        <label className="flex flex-col gap-2">
          {t("settings.upgrade.file")}
          <input
            type="file"
            accept="application/json,.json"
            className="min-w-0 max-w-full"
            onChange={(event) => {
              const chosen = event.target.files?.[0] ?? null;
              setFileError(Boolean(chosen && chosen.size > 20 * 1024 * 1024));
              setFile(
                chosen && chosen.size <= 20 * 1024 * 1024 ? chosen : null,
              );
            }}
          />
        </label>
        <p className="text-sm text-muted-foreground">
          {t("settings.upgrade.importHelp")}
        </p>
        <Button
          disabled={!file || imported.isPending}
          onClick={upload}
          ignoreTitleCase
        >
          {t("settings.upgrade.import")}
        </Button>
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
      </section>
      <section aria-labelledby="upgrade-history-title" className="space-y-3">
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
                className="max-w-full rounded border bg-background p-2"
                value={
                  history.data.items.some((item) => item.id === id) ? id : ""
                }
                onChange={(event) => setParams({ report: event.target.value })}
              >
                <option value="" disabled>
                  {t("settings.upgrade.chooseReport")}
                </option>
                {history.data.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {t("settings.upgrade.historyEntry", {
                      target: item.target_version,
                      time: reportTime(
                        item.generated_at,
                        i18n.language,
                        t("settings.upgrade.unknown"),
                      ),
                      count: item.flow_count,
                    })}
                  </option>
                ))}
              </select>
            </label>
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
          </>
        )}
      </section>
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
