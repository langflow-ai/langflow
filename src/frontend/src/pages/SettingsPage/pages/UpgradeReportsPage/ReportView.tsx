import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type ReportDetail,
  useExportUpgradeReport,
} from "@/controllers/API/queries/upgrade-reports";
import FlowList from "./FlowList";
import { downloadReport, reportTime } from "./format";
import RepairControls from "./RepairControls";

export default function ReportView({ report }: { report: ReportDetail }) {
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
  const assessment =
    document.errors.length > 0 || incomplete
      ? "incomplete"
      : document.summary.flows.fail > 0
        ? "blocked"
        : document.summary.flows.warn > 0
          ? "review"
          : "clear";
  const ageHours = Math.floor(
    (Date.now() - Date.parse(document.generated_at)) / 3600000,
  );
  const age = new Intl.RelativeTimeFormat(i18n.language, {
    numeric: "auto",
  }).format(-ageHours, "hour");
  const source = document.source.identity?.locator;
  const sourceLabel = source
    ? Object.entries(source)
        .filter(([key]) => key !== "search_path_sha256")
        .map(([, value]) => value)
        .filter((value) => value !== null)
        .join(" · ")
    : unknown;
  return (
    <section aria-labelledby="upgrade-report-title" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 id="upgrade-report-title" className="font-medium">
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
      <div className="space-y-2 rounded border p-4" role="note">
        <h4 className="font-medium">
          {t(`settings.upgrade.assessment.${assessment}`)}
        </h4>
        <p className="text-sm">
          {t(`settings.upgrade.nextStep.${assessment}`)}
        </p>
      </div>
      <dl className="grid min-w-0 grid-cols-1 gap-3 rounded border p-4 text-sm [overflow-wrap:anywhere] sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">
            {t("settings.upgrade.source")}
          </dt>
          <dd>
            {document.source.dialect} · {sourceLabel}
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
            {reportTime(document.generated_at, i18n.language, unknown)} · {age}
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
            {t("settings.upgrade.summary")}
          </dt>
          <dd>{t("settings.upgrade.counts", document.summary.flows)}</dd>
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
        <dl className="mt-2 space-y-2 text-sm">
          {["ok", "warn", "fail", "could_not_verify"].map((status) => (
            <div key={status}>
              <dt className="font-medium">
                {t(`settings.upgrade.status.${status}`)}
              </dt>
              <dd>{t(`settings.upgrade.resultMeaning.${status}`)}</dd>
            </div>
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
      />
    </section>
  );
}
