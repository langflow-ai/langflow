import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { MaintenancePauseStatus } from "@/controllers/API/queries/migration";
import { useSetUpgradeMaintenance } from "@/controllers/API/queries/upgrade-reports";
import { reportTime } from "./format";

export default function MaintenanceControls({
  status,
  busy,
}: {
  status: MaintenancePauseStatus;
  busy: boolean;
}) {
  const { t, i18n } = useTranslation();
  const update = useSetUpgradeMaintenance();
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const enable = !status.maintenance;
  useEffect(() => {
    setOpen(false);
  }, [enable]);
  const action = t(
    enable
      ? "settings.upgrade.turnMaintenanceOn"
      : "settings.upgrade.turnMaintenanceOff",
  );
  return (
    <div className="space-y-2">
      <p>
        {t(
          status.maintenance
            ? "settings.upgrade.maintenanceActive"
            : "settings.upgrade.maintenanceInactive",
        )}
      </p>
      {status.maintenance && status.running_jobs === 0 && (
        <p>{t("settings.upgrade.noRunningJobs")}</p>
      )}
      {status.maintenance && status.set_at && (
        <p>
          {t("settings.upgrade.maintenanceSince", {
            time: reportTime(
              status.set_at,
              i18n.language,
              t("settings.upgrade.unknown"),
            ),
          })}
        </p>
      )}
      {status.maintenance && status.reason && (
        <p className="break-words">{status.reason}</p>
      )}
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (update.isPending) return;
          update.reset();
          setReason("");
          setOpen(next);
        }}
      >
        <DialogTrigger asChild>
          <Button
            ref={trigger}
            variant="outline"
            disabled={busy}
            aria-disabled={update.isPending || undefined}
            ignoreTitleCase
          >
            {action}
          </Button>
        </DialogTrigger>
        <DialogContent
          className="w-[calc(100%_-_2rem)] max-w-md"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            trigger.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>{action}</DialogTitle>
            <DialogDescription>
              {t(
                enable
                  ? "settings.upgrade.maintenanceOnWarning"
                  : "settings.upgrade.maintenanceOffWarning",
              )}
            </DialogDescription>
          </DialogHeader>
          {enable && (
            <label className="grid gap-1">
              {t("settings.upgrade.maintenanceReason")}
              <Input
                maxLength={1024}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
          )}
          {update.isError && (
            <p role="alert">{t("settings.upgrade.maintenanceChangeFailed")}</p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={update.isPending}
              onClick={() => setOpen(false)}
              ignoreTitleCase
            >
              {t("modal.cancelButton")}
            </Button>
            <Button
              disabled={busy || update.isPending}
              onClick={() =>
                update.mutate(
                  { enabled: enable, reason: reason.trim() || undefined },
                  { onSuccess: () => setOpen(false) },
                )
              }
              ignoreTitleCase
            >
              {action}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
