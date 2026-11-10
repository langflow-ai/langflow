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
import { reportTime } from "./format";
import { repairReasonKey } from "./reasons";

export default function RepairControls({
  reportId,
  selected,
  flows,
}: {
  reportId: string;
  selected: Set<string>;
  flows: ReportFlow[];
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
  const canApply = Boolean(
    !maintenance.isError &&
      maintenance.data?.maintenance &&
      !maintenance.data?.migration,
  );
  const busy = preview.isPending || apply.isPending;
  return (
    <section
      aria-labelledby="upgrade-repair-title"
      className="space-y-3 rounded border p-4"
    >
      <h3 id="upgrade-repair-title" className="font-medium">
        {t("settings.upgrade.repairTitle")}
      </h3>
      <p>{t("settings.upgrade.repairExplanation")}</p>
      <p>{t("settings.upgrade.selected", { count: selected.size })}</p>
      <Button
        variant="outline"
        disabled={!selected.size || busy}
        onClick={() => {
          setConfirmed(false);
          setApplied(false);
          setResult(null);
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
      {!canApply && <p role="note">{t("settings.upgrade.freezeRequired")}</p>}
      {maintenance.isError && (
        <p role="alert">{t("settings.upgrade.freezeUnknown")}</p>
      )}
      {(preview.isError || apply.isError) && (
        <p role="alert">{t("settings.upgrade.repairError")}</p>
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
                  {flows.find((flow) => flow.id === item.flow_id)?.name ??
                    item.flow_id}{" "}
                  · {t(`settings.upgrade.repairStatus.${item.status}`)}
                </p>
                {item.reason_codes.length > 0 && (
                  <ul>
                    {item.reason_codes.map((code) => (
                      <li key={code}>{t(repairReasonKey(code))}</li>
                    ))}
                  </ul>
                )}
                {item.recovery_version_id && (
                  <p>
                    {t("settings.upgrade.recoveryVersion", {
                      id: item.recovery_version_id,
                    })}
                  </p>
                )}
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
                  · {item.result.flow_id} ·{" "}
                  {t(`settings.upgrade.repairStatus.${item.result.status}`)}
                  {item.result.recovery_version_id && (
                    <p>
                      {t("settings.upgrade.recoveryVersion", {
                        id: item.result.recovery_version_id,
                      })}
                    </p>
                  )}
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
