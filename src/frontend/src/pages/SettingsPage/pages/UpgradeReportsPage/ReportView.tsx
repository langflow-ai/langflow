import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type ReportDetail,
  useExportUpgradeReport,
} from "@/controllers/API/queries/upgrade-reports";
import FlowList from "./FlowList";
import {
  downloadReport,
  reportAge,
  reportAssessment,
  reportTime,
} from "./format";
import RepairControls from "./RepairControls";

export default function ReportView({
  report,
  onUnappliedUpdatesChange,
}: {
  report: ReportDetail;
  onUnappliedUpdatesChange: (unapplied: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const exportReport = useExportUpgradeReport();
  const unknown = t("settings.upgrade.unknown");
  const document = report.document;
  const total =
    document.summary.flows.ok +
    document.summary.flows.warn +
    document.summary.flows.fail;
  const incomplete = document.flows.length < total;
  const assessment = reportAssessment(
    document.errors.length > 0 || incomplete,
    document.summary.flows.fail,
    document.summary.flows.warn,
  );
  const age = reportAge(document.generated_at, i18n.language, unknown);
  const source = document.source.identity?.locator;
  // The summary names the database only. The full path or host stays in the
  // collapsed identity details, since a summary is what ends up in screenshots.
  const sourceName =
    (typeof source?.path === "string" && source.path.split(/[\\/]/).pop()) ||
    (typeof source?.database === "string" && source.database) ||
    unknown;
  const sourceLabel = source
    ? Object.entries(source)
        .filter(([key]) => key !== "search_path_sha256")
        .map(([, value]) => value)
        .filter((value) => value !== null)
        .join(" · ")
    : unknown;
  return (
    <>
      <section
        aria-labelledby="upgrade-report-title"
        className="min-w-0 space-y-5 rounded-lg border p-3 sm:p-5"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h3 id="upgrade-report-title" tabIndex={-1} className="font-medium">
            {t("settings.upgrade.report")}
          </h3>
          <Button
            variant="outline"
            disabled={exportReport.isPending}
            onClick={() =>
              exportReport.mutate(report.id, {
                onSuccess: (blob) => downloadReport(report.id, blob),
              })
            }
            ignoreTitleCase
          >
            {t("settings.upgrade.export")}
          </Button>
        </div>
        {exportReport.isError && (
          <p role="alert">{t("settings.upgrade.exportError")}</p>
        )}
        <div
          className={`space-y-1 rounded-md border-l-4 bg-muted/50 px-4 py-3 ${assessment === "blocked" ? "border-destructive" : assessment === "clear" ? "border-primary" : "border-warning"}`}
          role="note"
        >
          <h4 className="text-base font-semibold">
            {t(`settings.upgrade.assessment.${assessment}`)}
          </h4>
          <p className="text-sm">
            {t(`settings.upgrade.nextStep.${assessment}`)}
          </p>
        </div>
        <dl
          aria-label={t("settings.upgrade.summary")}
          className="grid grid-cols-3 gap-2"
        >
          {(["fail", "warn", "ok"] as const).map((status) => (
            <div
              key={status}
              className="flex min-w-0 flex-col-reverse gap-1 rounded-md bg-muted/50 p-2 sm:p-3"
            >
              <dt className="text-xs text-muted-foreground">
                {t(`settings.upgrade.status.${status}`)}
              </dt>
              <dd className="text-xl font-semibold tabular-nums">
                {document.summary.flows[status].toLocaleString(i18n.language)}
              </dd>
            </div>
          ))}
        </dl>
        <dl className="grid min-w-0 grid-cols-1 gap-3 border-b pb-4 text-sm [overflow-wrap:anywhere] sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">
              {t("settings.upgrade.source")}
            </dt>
            <dd>
              {document.source.dialect} · {sourceName}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">
              {t("settings.upgrade.target")}
            </dt>
            <dd>{document.target.langflow}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">
              {t("settings.upgrade.generated")}
            </dt>
            <dd>
              {reportTime(document.generated_at, i18n.language, unknown)} ·{" "}
              {age}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">
              {t("settings.upgrade.imported")}
            </dt>
            <dd>{reportTime(report.created_at, i18n.language, unknown)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">
              {t("settings.upgrade.sourceRevision")}
            </dt>
            <dd>{document.source.alembic_revision ?? unknown}</dd>
          </div>
        </dl>
        <p role="note">{t("settings.upgrade.reportWarning")}</p>
        {incomplete && (
          <p role="note">
            {t("settings.upgrade.partialReport", {
              shown: document.flows.length,
              total,
            })}
          </p>
        )}
        <details>
          <summary className="cursor-pointer">
            {t("settings.upgrade.resultHelp")}
          </summary>
          <dl className="mt-3 grid grid-cols-[max-content_minmax(0,1fr)] items-baseline gap-x-4 gap-y-3 text-sm">
            {["ok", "warn", "fail", "could_not_verify"].map((status) => (
              <Fragment key={status}>
                <dt>
                  <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium">
                    {t(`settings.upgrade.status.${status}`)}
                  </span>
                </dt>
                <dd className="text-muted-foreground">
                  {t(`settings.upgrade.resultMeaning.${status}`)}
                </dd>
              </Fragment>
            ))}
          </dl>
        </details>
        {document.errors.length > 0 && (
          <section aria-labelledby="upgrade-errors-title">
            <h4 id="upgrade-errors-title" className="font-medium">
              {t("settings.upgrade.reportErrors")}
            </h4>
            <ul>
              {document.errors.map((error, index) => (
                <li key={`${error.kind}-${index}`}>{error.message}</li>
              ))}
            </ul>
          </section>
        )}
        <details>
          <summary className="cursor-pointer">
            {t("settings.upgrade.targetDetails")}
          </summary>
          <div className="space-y-2 break-all text-sm">
            <p>
              {t("settings.upgrade.sourceLocation", { location: sourceLabel })}
            </p>
            <p>
              {t("settings.upgrade.sourceFingerprint", {
                fingerprint: document.source.identity?.sha256 ?? unknown,
              })}
            </p>
            <p>
              {t("settings.upgrade.targetFingerprint", {
                fingerprint: document.target.component_index_sha256,
              })}
            </p>
            <ul>
              {document.target.bundles.map((bundle) => (
                <li key={bundle}>{bundle}</li>
              ))}
            </ul>
          </div>
        </details>
      </section>
      <FlowList
        flows={document.flows}
        selected={selected}
        onSelect={(id, checked) =>
          setSelected((current) => {
            const next = new Set(current);
            if (checked) next.add(id);
            else next.delete(id);
            return next;
          })
        }
      />
      <RepairControls
        reportId={report.id}
        selected={selected}
        flows={document.flows}
        onUnappliedUpdatesChange={onUnappliedUpdatesChange}
      />
    </>
  );
}
