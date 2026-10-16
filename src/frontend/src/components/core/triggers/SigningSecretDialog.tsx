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
  type TriggerRead,
  useRotateSigningSecretMutation,
  useTriggerIngressQuery,
} from "@/controllers/API/queries/triggers";
import CopyField from "./CopyField";

export interface SigningSecretDialogProps {
  trigger: TriggerRead | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * B7: create or rotate an inbound webhook's signing secret. The secret is
 * shown once, from the mutation's response, and is gone when the dialog
 * closes; rotation takes effect immediately with no grace period.
 */
export function SigningSecretDialog({
  trigger,
  onOpenChange,
}: SigningSecretDialogProps) {
  const { t } = useTranslation();
  const ingress = useTriggerIngressQuery(trigger?.id, trigger !== null);
  const rotate = useRotateSigningSecretMutation();
  const { reset } = rotate;

  // Drop the plaintext the moment the dialog closes.
  useEffect(() => {
    if (trigger === null) reset();
  }, [trigger, reset]);

  const revealed = rotate.data;
  const hasSecret = ingress.data?.has_signing_secret ?? false;
  const url = revealed?.ingress_url ?? ingress.data?.ingress_url ?? null;

  return (
    <Dialog open={trigger !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="trigger-secret-dialog">
        <DialogHeader>
          <DialogTitle>{t("triggers.secret.title")}</DialogTitle>
          <DialogDescription>
            {revealed
              ? t("triggers.secret.showOnce")
              : hasSecret
                ? t("triggers.secret.rotateWarning")
                : t("triggers.secret.createIntro")}
          </DialogDescription>
        </DialogHeader>
        {url && (
          <CopyField
            id="trigger-secret-url"
            label={t("triggers.secret.endpoint")}
            value={url}
            copyLabel={t("triggers.secret.copyEndpoint")}
            testId="trigger-secret-url"
          />
        )}
        {revealed && (
          <CopyField
            id="trigger-secret-value"
            label={t("triggers.secret.secret")}
            value={revealed.signing_secret}
            copyLabel={t("triggers.secret.copySecret")}
            testId="trigger-secret-value"
          />
        )}
        {rotate.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getAxiosErrorDetail(rotate.error, t("triggers.errors.unknown"))}
          </p>
        )}
        <DialogFooter>
          {revealed ? (
            <Button onClick={() => onOpenChange(false)}>
              {t("triggers.secret.done")}
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t("triggers.common.cancel")}
              </Button>
              <Button
                onClick={() => trigger && rotate.mutate(trigger.id)}
                loading={rotate.isPending}
                disabled={ingress.isLoading}
                variant={hasSecret ? "destructive" : "default"}
                data-testid="trigger-secret-rotate"
              >
                {hasSecret
                  ? t("triggers.secret.rotate")
                  : t("triggers.secret.create")}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SigningSecretDialog;
