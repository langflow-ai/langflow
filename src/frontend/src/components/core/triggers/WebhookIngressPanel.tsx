import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  type TriggerRead,
  useTriggerIngressQuery,
} from "@/controllers/API/queries/triggers";
import CopyField from "./CopyField";
import { availabilityOf } from "./helpers/trigger-presentation";
import SigningSecretDialog from "./SigningSecretDialog";

/**
 * B7 on the webhook node: where senders post, and whether a signing secret
 * is set. The secret itself is only ever shown by the dialog, once.
 */
export function WebhookIngressPanel({ trigger }: { trigger: TriggerRead }) {
  const { t } = useTranslation();
  const ingress = useTriggerIngressQuery(trigger.id);
  const [secretOpen, setSecretOpen] = useState(false);
  const rotate = availabilityOf(trigger, "rotate_secret");
  const hasSecret = ingress.data?.has_signing_secret ?? false;

  return (
    <div className="flex flex-col gap-3" data-testid="trigger-webhook-panel">
      {ingress.data?.ingress_url && (
        <CopyField
          id={`trigger-endpoint-${trigger.id}`}
          label={t("triggers.secret.endpoint")}
          value={ingress.data.ingress_url}
          copyLabel={t("triggers.secret.copyEndpoint")}
          testId="trigger-node-endpoint"
        />
      )}
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-sm font-medium">
            {t("triggers.secret.title")}
          </span>
          <span className="text-xs text-muted-foreground">
            {hasSecret
              ? t("triggers.secret.isSet")
              : t("triggers.secret.notSet")}
          </span>
        </div>
        {rotate && !rotate.blockedReason && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSecretOpen(true)}
            data-testid="trigger-node-secret"
          >
            {hasSecret
              ? t("triggers.secret.rotate")
              : t("triggers.secret.create")}
          </Button>
        )}
      </div>
      <SigningSecretDialog
        trigger={secretOpen ? trigger : null}
        onOpenChange={setSecretOpen}
      />
    </div>
  );
}

export default WebhookIngressPanel;
