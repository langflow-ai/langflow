import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type RepairPreview,
  type RepairResult,
  type ReportFlow,
  useApplyUpgradeRepair,
  useGetUpgradeRepairOutcomes,
  usePreviewUpgradeRepair,
  useUpgradeMaintenance,
} from "@/controllers/API/queries/upgrade-reports";
import { CustomLink } from "@/customization/components/custom-link";
import { reportTime, verifiedStatus } from "./format";
import { scrollToMaintenance } from "./MaintenanceControls";
import { repairReasonKey, repairRequestErrorKey } from "./reasons";

export default function RepairControls({
  reportId,
  selected,
  flows,
  onUnappliedUpdatesChange,
}: {
  reportId: string;
  selected: Set<string>;
  flows: ReportFlow[];
  onUnappliedUpdatesChange: (unapplied: boolean) => void;
}) {
  const { t, i18n } = useTranslation();
  const maintenance = useUpgradeMaintenance();
  const preview = usePreviewUpgradeRepair();
  const apply = useApplyUpgradeRepair();
  const [outcomeOffset, setOutcomeOffset] = useState(0);
  const outcomes = useGetUpgradeRepairOutcomes({
    id: reportId,
    offset: outcomeOffset,
  });
  const [result, setResult] = useState<RepairPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [applied, setApplied] = useState(false);
  const selectionKey = [...selected].sort().join(",");
  const latestSelection = useRef(selectionKey);
  latestSelection.current = selectionKey;
  useEffect(() => {
    setResult(null);
    setConfirmed(false);
    setApplied(false);
  }, [selectionKey, reportId]);
  const ready =
    result?.results.filter(
      (item): item is RepairResult & { data_sha256: string } =>
        item.status === "ready" && typeof item.data_sha256 === "string",
    ) ?? [];
  const hasUnappliedUpdates = ready.length > 0;
  useEffect(() => {
    onUnappliedUpdatesChange(hasUnappliedUpdates);
    return () => onUnappliedUpdatesChange(false);
  }, [hasUnappliedUpdates, onUnappliedUpdatesChange]);
  const status = verifiedStatus(maintenance);
  const canApply = Boolean(
    status?.maintenance && !status.migration && status.running_jobs === 0,
  );
  const busy = preview.isPending || apply.isPending;
  const flowName = (flowId: string) =>
    (
      flows.find((flow) => flow.kind === "flow" && flow.id === flowId) ??
      flows.find((flow) => flow.id === flowId || flow.flow_id === flowId)
    )?.name?.trim() || flowId;
  const flowLink = ({ flow_id: flowId, status }: RepairResult) =>
    status === "not_found" ? (
      flowName(flowId)
    ) : (
      <CustomLink
        to={`/flow/${encodeURIComponent(flowId)}`}
        aria-label={t("settings.upgrade.openFlow", { name: flowName(flowId) })}
        className="text-primary underline"
      >
        {flowName(flowId)}
      </CustomLink>
    );
  const recoveryLink = (item: RepairResult) =>
    item.recovery_version_id && (
      <p>
        <CustomLink
          to={`/flow/${encodeURIComponent(item.flow_id)}?version=${encodeURIComponent(item.recovery_version_id)}`}
          className="text-primary underline"
        >
          {t("settings.upgrade.reviewRecovery", {
            name: flowName(item.flow_id),
          })}
        </CustomLink>
      </p>
    );
  const reasons = (item: RepairResult) => (
    <>
      {item.reason_codes.length > 0 && (
        <ul>
          {item.reason_codes.map((code) => (
            <li key={code}>{t(repairReasonKey(code))}</li>
          ))}
        </ul>
      )}
      {item.reason_detail && <p>{item.reason_detail}</p>}
    </>
  );
  return (
    <section
      aria-labelledby="upgrade-repair-title"
      className="min-w-0 space-y-3 rounded-lg border p-3 sm:p-5"
    >
      <h3 id="upgrade-repair-title" className="font-medium">
        {t("settings.upgrade.repairTitle")}
      </h3>
      <p>{t("settings.upgrade.repairExplanation")}</p>
      <p>
        {t("settings.upgrade.selected", { count: selected.size })} ·{" "}
        {t(
          preview.isPending
            ? "settings.upgrade.previewState.running"
            : result
              ? "settings.upgrade.previewState.done"
              : "settings.upgrade.previewState.required",
        )}
      </p>
      <Button
        variant="outline"
        disabled={!selected.size || busy}
        onClick={() => {
          setConfirmed(false);
          setApplied(false);
          setResult(null);
          apply.reset();
          preview.mutate(
            { flow_ids: [...selected], report_id: reportId },
            {
              onSuccess: (response) => {
                if (latestSelection.current === selectionKey)
                  setResult(response);
              },
            },
          );
        }}
        ignoreTitleCase
      >
        {t("settings.upgrade.preview")}
      </Button>
      {!maintenance.isPending && !canApply && (
        <p role="note">
          {!status
            ? t("settings.upgrade.freezeUnknown")
            : status.migration
              ? t("settings.upgrade.migrationPause")
              : !status.maintenance
                ? t("settings.upgrade.freezeRequired")
                : t("settings.upgrade.runningJobs", {
                    count: status.running_jobs,
                  })}{" "}
          <Button
            variant="link"
            className="h-auto p-0"
            onClick={scrollToMaintenance}
            ignoreTitleCase
          >
            {t("settings.upgrade.maintenance.manage")}
          </Button>
        </p>
      )}
      {(preview.isError || apply.isError) && (
        <p role="alert">
          {t(
            repairRequestErrorKey(apply.isError ? apply.error : preview.error),
          )}
        </p>
      )}
      {busy && <p role="status">{t("settings.upgrade.repairBusy")}</p>}
      {result && (
        <>
          <p role="status">
            {t(
              applied
                ? "settings.upgrade.applyComplete"
                : "settings.upgrade.previewComplete",
            )}
          </p>
          {applied && (
            <div className="space-y-1 rounded-md border-l-4 border-primary bg-muted/50 px-4 py-3 text-sm">
              <p className="font-medium">
                {t("settings.upgrade.applyOutcome", {
                  updated: result.results.filter(
                    (item) => item.status === "updated",
                  ).length,
                  other: result.results.filter(
                    (item) => item.status !== "updated",
                  ).length,
                })}
              </p>
              <p className="text-muted-foreground">
                {t("settings.upgrade.maintenanceStaysOn")}
              </p>
            </div>
          )}
          <dl className="text-sm">
            <dt>{t("settings.upgrade.target")}</dt>
            <dd>{result.target_version ?? t("settings.upgrade.unknown")}</dd>
          </dl>
          <p className="break-all text-sm">
            {t("settings.upgrade.targetFingerprint", {
              fingerprint: result.target_sha256,
            })}
          </p>
          <ul className="space-y-2" aria-label={t("settings.upgrade.results")}>
            {result.results.map((item) => (
              <li key={item.flow_id} className="break-all">
                <p>
                  {flowLink(item)} ·{" "}
                  {t(`settings.upgrade.repairStatus.${item.status}`)}
                </p>
                {reasons(item)}
                {recoveryLink(item)}
              </li>
            ))}
          </ul>
          {ready.length > 0 && (
            <>
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                {t("settings.upgrade.confirmRepair", { count: ready.length })}
              </label>
              <Button
                disabled={!confirmed || !canApply || busy}
                onClick={() => {
                  if (!result) return;
                  apply.mutate(
                    {
                      flows: ready.map((item) => ({
                        flow_id: item.flow_id,
                        version_token: item.version_token,
                        data_sha256: item.data_sha256,
                      })),
                      target_sha256: result.target_sha256,
                      report_id: reportId,
                    },
                    {
                      onSuccess: (response) => {
                        setResult(response);
                        setConfirmed(false);
                        setApplied(true);
                      },
                    },
                  );
                }}
                ignoreTitleCase
              >
                {t("settings.upgrade.apply", { count: ready.length })}
              </Button>
            </>
          )}
        </>
      )}
      <details aria-label={t("settings.upgrade.repairHistory")}>
        <summary className="cursor-pointer">
          {t("settings.upgrade.repairHistory")}
        </summary>
        {outcomes.isError && (
          <p role="alert">{t("settings.upgrade.loadError")}</p>
        )}
        {outcomes.data && (
          <>
            <p>
              {t("settings.upgrade.outcomes", {
                shown: outcomes.data.items.length,
                total: outcomes.data.total,
              })}
            </p>
            <ul className="space-y-2">
              {outcomes.data.items.map((item) => (
                <li key={item.id} className="break-all">
                  {reportTime(
                    item.created_at,
                    i18n.language,
                    t("settings.upgrade.unknown"),
                  )}{" "}
                  · {flowLink(item.result)} ·{" "}
                  {t(`settings.upgrade.repairStatus.${item.result.status}`)}
                  {reasons(item.result)}
                  {recoveryLink(item.result)}
                </li>
              ))}
            </ul>
            <div className="mt-2 flex gap-2">
              <Button
                variant="outline"
                disabled={outcomeOffset === 0}
                onClick={() =>
                  setOutcomeOffset(Math.max(0, outcomeOffset - 50))
                }
                ignoreTitleCase
              >
                {t("settings.upgrade.previous")}
              </Button>
              <Button
                variant="outline"
                disabled={outcomeOffset + 50 >= outcomes.data.total}
                onClick={() => setOutcomeOffset(outcomeOffset + 50)}
                ignoreTitleCase
              >
                {t("settings.upgrade.next")}
              </Button>
            </div>
          </>
        )}
      </details>
    </section>
  );
}
