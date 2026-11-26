import { useIsMutating } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { MaintenancePauseStatus } from "@/controllers/API/queries/migration";
import {
  useSetUpgradeMaintenance,
  useUpgradeMaintenance,
} from "@/controllers/API/queries/upgrade-reports";
import { DOCS_LINK } from "@/customization/config-constants";
import { reportTime } from "./format";

export const MAINTENANCE_SECTION_ID = "upgrade-maintenance";

type VerifiedStatus = MaintenancePauseStatus & {
  maintenance: boolean;
  migration: boolean;
  running_jobs: number;
};

/** The maintenance status, or null when the server answer cannot be trusted. */
export function verifiedStatus({
  data,
  isError,
}: {
  data?: MaintenancePauseStatus;
  isError: boolean;
}): VerifiedStatus | null {
  const jobs = data?.running_jobs;
  return !isError &&
    typeof data?.maintenance === "boolean" &&
    typeof data.migration === "boolean" &&
    typeof jobs === "number" &&
    Number.isSafeInteger(jobs) &&
    jobs >= 0
    ? (data as VerifiedStatus)
    : null;
}

export function scrollToMaintenance() {
  const heading = document.getElementById(`${MAINTENANCE_SECTION_ID}-title`);
  heading?.scrollIntoView({ behavior: "smooth", block: "start" });
  heading?.focus({ preventScroll: true });
}

const TONES = {
  neutral: "border-border",
  warning: "border-warning",
  ready: "border-primary",
  error: "border-destructive",
};

function StateRow({
  tone,
  title,
  detail,
  action,
}: {
  tone: keyof typeof TONES;
  title?: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex flex-col gap-3 rounded-md border-l-4 bg-muted/50 px-4 py-3 text-sm sm:flex-row sm:items-center ${TONES[tone]}`}
    >
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && <p className="font-medium">{title}</p>}
        <p className={title ? "text-muted-foreground" : undefined}>{detail}</p>
      </div>
      {action}
    </div>
  );
}

export default function MaintenanceControls() {
  const { t, i18n } = useTranslation();
  const query = useUpgradeMaintenance();
  const status = verifiedStatus(query);
  const update = useSetUpgradeMaintenance();
  const repairBusy =
    useIsMutating({ mutationKey: ["usePreviewUpgradeRepair"] }) +
      useIsMutating({ mutationKey: ["useApplyUpgradeRepair"] }) >
    0;
  const [dialog, setDialog] = useState<"enable" | "disable" | null>(null);
  const [failed, setFailed] = useState<"enable" | "disable" | null>(null);
  const [reason, setReason] = useState("");
  const toggle = useRef<HTMLButtonElement>(null);

  // A failed request that the server applied anyway is no longer a failure.
  useEffect(() => {
    if (failed && status && status.maintenance === (failed === "enable"))
      setFailed(null);
  }, [failed, status?.maintenance]);

  const { hash } = useLocation();
  useEffect(() => {
    if (hash === `#${MAINTENANCE_SECTION_ID}`) scrollToMaintenance();
  }, [hash]);

  // The dialog asks about the status it was opened for, so close it when that status changes.
  useEffect(() => {
    if (!update.isPending) setDialog(null);
  }, [status?.maintenance, status?.migration]);

  const next = status?.maintenance ? "disable" : "enable";
  const label = (kind: "enable" | "disable") =>
    kind === "enable"
      ? t("settings.upgrade.maintenance.enable")
      : t("settings.upgrade.maintenance.disable");
  const blocked = !status || status.migration || repairBusy;
  const openDialog = () => {
    update.reset();
    setDialog(next);
  };
  const submit = (kind: "enable" | "disable") =>
    update.mutate(
      { enabled: kind === "enable", reason: reason.trim() || undefined },
      {
        onSuccess: () => {
          setFailed(null);
          setReason("");
        },
        onError: () => setFailed(kind),
        onSettled: () => setDialog(null),
      },
    );
  const retryStatus = (
    <Button
      variant="outline"
      className="shrink-0"
      disabled={query.isFetching}
      onClick={() => query.refetch()}
      ignoreTitleCase
    >
      {t(
        query.isFetching
          ? "settings.upgrade.maintenance.checking"
          : "settings.upgrade.maintenance.retryStatus",
      )}
    </Button>
  );
  const toggleButton = (label: string) => (
    <Button
      ref={toggle}
      variant="outline"
      className="shrink-0"
      disabled={blocked}
      onClick={openDialog}
      ignoreTitleCase
    >
      {label}
    </Button>
  );
  const showFailure =
    failed && (!status || status.maintenance === (failed === "disable"));

  const row = showFailure ? (
    <StateRow
      tone="error"
      title={
        failed === "enable"
          ? t("settings.upgrade.maintenance.enableFailedTitle")
          : t("settings.upgrade.maintenance.disableFailedTitle")
      }
      detail={
        !status
          ? t("settings.upgrade.maintenance.verifyFirst")
          : failed === "enable"
            ? t("settings.upgrade.maintenance.enableFailedDetail")
            : t("settings.upgrade.maintenance.disableFailedDetail")
      }
      action={
        status
          ? toggleButton(
              t(
                failed === "enable"
                  ? "settings.upgrade.maintenance.retryEnable"
                  : "settings.upgrade.maintenance.retryDisable",
              ),
            )
          : retryStatus
      }
    />
  ) : !status ? (
    query.isPending ? (
      <p role="status">{t("common.loading")}</p>
    ) : (
      <StateRow
        tone="error"
        title={t("settings.upgrade.maintenance.unknownTitle")}
        detail={t("settings.upgrade.maintenance.unknownDetail")}
        action={retryStatus}
      />
    )
  ) : !status.maintenance ? (
    <StateRow
      tone="neutral"
      detail={t("settings.upgrade.maintenance.offDetail")}
    />
  ) : status.running_jobs > 0 ? (
    <StateRow
      tone="warning"
      title={t("settings.upgrade.maintenance.runningTitle")}
      detail={t("settings.upgrade.maintenance.runningDetail")}
    />
  ) : (
    <StateRow
      tone="ready"
      title={t("settings.upgrade.maintenance.readyTitle")}
      detail={t("settings.upgrade.maintenance.readyDetail")}
    />
  );

  return (
    <section
      id={MAINTENANCE_SECTION_ID}
      aria-labelledby={`${MAINTENANCE_SECTION_ID}-title`}
      className="min-w-0 space-y-3 rounded-lg border p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h3
            id={`${MAINTENANCE_SECTION_ID}-title`}
            tabIndex={-1}
            className="font-medium"
          >
            {t("settings.upgrade.maintenance.title")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("settings.upgrade.maintenance.description")}
          </p>
        </div>
        {status && !showFailure && toggleButton(label(next))}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm [overflow-wrap:anywhere] lg:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">
            {t("settings.upgrade.maintenance.status")}
          </dt>
          <dd className="font-medium">
            {!status
              ? query.isPending
                ? "—"
                : t("settings.upgrade.maintenance.unknown")
              : status.maintenance
                ? t("settings.upgrade.maintenance.on")
                : t("settings.upgrade.maintenance.off")}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t("settings.upgrade.maintenance.reason")}
          </dt>
          <dd>
            {status?.maintenance
              ? status.reason || t("settings.upgrade.maintenance.noReason")
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t("settings.upgrade.maintenance.enabledAt")}
          </dt>
          <dd>
            {status?.maintenance && status.set_at
              ? reportTime(
                  status.set_at,
                  i18n.language,
                  t("settings.upgrade.unknown"),
                )
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">
            {t("settings.upgrade.maintenance.runningJobs")}
          </dt>
          <dd className="tabular-nums">
            {status?.maintenance ? status.running_jobs : "—"}
          </dd>
        </div>
      </dl>
      {row}
      {status?.migration && (
        <p role="note" className="text-sm">
          {t("settings.upgrade.migrationPause")}
        </p>
      )}
      <details className="text-sm">
        <summary className="cursor-pointer">
          {t("settings.upgrade.maintenance.terminal")}
        </summary>
        <div className="mt-2 space-y-2">
          <p>{t("settings.upgrade.maintenanceHelp")}</p>
          <pre className="whitespace-pre-wrap break-all rounded bg-muted p-3">
            <code>
              {
                'langflow maintenance on --reason "Flow upgrade"\nlangflow maintenance status\nlangflow maintenance off'
              }
            </code>
          </pre>
          <p>{t("settings.upgrade.maintenanceDrainHelp")}</p>
          <a
            href={`${DOCS_LINK}/maintenance-mode`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline"
          >
            {t("settings.upgrade.maintenanceGuide")}
          </a>
        </div>
      </details>
      <Dialog
        open={dialog !== null && !blocked}
        onOpenChange={(next) => {
          if (!next && !update.isPending) setDialog(null);
        }}
      >
        <DialogContent
          className="w-[calc(100%_-_2rem)] max-w-md"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            (
              toggle.current ??
              document.getElementById(`${MAINTENANCE_SECTION_ID}-title`)
            )?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {t(
                dialog === "enable"
                  ? "settings.upgrade.maintenance.enableTitle"
                  : "settings.upgrade.maintenance.disableTitle",
              )}
            </DialogTitle>
            <DialogDescription>
              {t(
                dialog === "enable"
                  ? "settings.upgrade.maintenanceOnWarning"
                  : "settings.upgrade.maintenanceOffWarning",
              )}
            </DialogDescription>
          </DialogHeader>
          {dialog === "enable" && (
            <label className="grid gap-1">
              {t("settings.upgrade.maintenanceReason")}
              <Input
                maxLength={1024}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={update.isPending}
              onClick={() => setDialog(null)}
              ignoreTitleCase
            >
              {t("modal.cancelButton")}
            </Button>
            <Button
              disabled={blocked || update.isPending}
              onClick={() => dialog && submit(dialog)}
              ignoreTitleCase
            >
              {dialog && label(dialog)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
