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
import type { ConnectionRead } from "@/controllers/API/queries/connections";

export interface BackgroundRunsConsentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Undefined while the connection list loads, or when it is not the caller's. */
  connection: ConnectionRead | undefined;
  busy: boolean;
  onConfirm: () => void;
}

/**
 * B9: explicit, per-connection consent for unattended use. Granting it is the
 * fix for `consent_required`; it is never set as a side effect of picking a
 * connection or enabling a trigger.
 */
export function BackgroundRunsConsentDialog({
  open,
  onOpenChange,
  connection,
  busy,
  onConfirm,
}: BackgroundRunsConsentDialogProps) {
  const { t } = useTranslation();
  const name = connection?.display_name ?? "";
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="trigger-consent-dialog">
        <DialogHeader>
          <DialogTitle>{t("triggers.consent.title")}</DialogTitle>
          <DialogDescription>
            {connection
              ? t("triggers.consent.description", { name })
              : t("triggers.consent.unavailable")}
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          {t("triggers.consent.scope")}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("triggers.common.cancel")}
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!connection || busy}
            loading={busy}
            data-testid="trigger-consent-confirm"
          >
            {t("triggers.consent.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default BackgroundRunsConsentDialog;
