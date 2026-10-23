import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import {
  type TriggerBulkAction,
  useBulkTriggersDryRunMutation,
  useBulkTriggersMutation,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";

export interface BulkTriggersDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  action: TriggerBulkAction;
  provider: string;
}

/**
 * Operator pause or resume of every trigger on one provider. The counts come
 * from a server dry run, so the dialog states exactly what the confirm will do.
 */
export function BulkTriggersDialog({
  open,
  onOpenChange,
  action,
  provider,
}: BulkTriggersDialogProps) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const dryRun = useBulkTriggersDryRunMutation();
  const bulk = useBulkTriggersMutation();
  const providerName = t(`triggers.provider.${provider}`, {
    defaultValue: provider,
  });

  const { mutate: preview, reset: resetPreview } = dryRun;
  useEffect(() => {
    if (open) preview({ action, body: { provider } });
    else resetPreview();
  }, [open, action, provider, preview, resetPreview]);

  const counts = dryRun.data;
  const changed = counts?.changed.length ?? 0;

  const confirm = async () => {
    try {
      const result = await bulk.mutateAsync({ action, body: { provider } });
      if (result.failed.length > 0) {
        setErrorData({
          title: t(`triggers.bulk.${action}.partial`, {
            count: result.changed.length,
            failed: result.failed.length,
          }),
          list: result.failed.map((failure) => failure.detail),
        });
      } else {
        setSuccessData({
          title: t(`triggers.bulk.${action}.done`, {
            count: result.changed.length,
          }),
        });
      }
      onOpenChange(false);
    } catch (error) {
      setErrorData({
        title: t(`triggers.bulk.${action}.failed`),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="triggers-bulk-dialog">
        <DialogHeader>
          <DialogTitle>
            {counts
              ? t(`triggers.bulk.${action}.title`, {
                  count: changed,
                  provider: providerName,
                })
              : t(`triggers.bulk.${action}.titleLoading`, {
                  provider: providerName,
                })}
          </DialogTitle>
          <DialogDescription>
            {t(`triggers.bulk.${action}.description`)}
          </DialogDescription>
        </DialogHeader>
        <dl
          className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-2 rounded-md border p-3 text-sm"
          aria-busy={dryRun.isPending}
        >
          <dt className="text-muted-foreground">
            {t(`triggers.bulk.${action}.changes`)}
          </dt>
          <dd className="text-right font-medium">{counts ? changed : "–"}</dd>
          <dt className="text-muted-foreground">
            {t("triggers.bulk.unchanged")}
          </dt>
          <dd className="text-right font-medium">
            {counts ? counts.unchanged.length : "–"}
          </dd>
          <dt className="text-muted-foreground">{t("triggers.bulk.owners")}</dt>
          <dd className="text-right font-medium">
            {counts ? counts.owners : "–"}
          </dd>
        </dl>
        {dryRun.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getAxiosErrorDetail(dryRun.error, t("triggers.errors.unknown"))}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("triggers.common.cancel")}
          </Button>
          <Button
            onClick={() => void confirm()}
            disabled={!counts || changed === 0 || bulk.isPending}
            loading={bulk.isPending}
            variant={action === "pause" ? "destructive" : "default"}
            data-testid="triggers-bulk-confirm"
          >
            {t(`triggers.bulk.${action}.confirm`, { count: changed })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default BulkTriggersDialog;
