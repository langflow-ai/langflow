import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Switch } from "@/components/ui/switch";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import {
  useGetConnections,
  useUpdateConnectionMutation,
} from "@/controllers/API/queries/connections";
import {
  type TriggerRead,
  useDisableTriggerMutation,
  useEnableTriggerMutation,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import { isTriggerEnabled } from "./helpers/trigger-enabled";
import {
  availabilityOf,
  blockedReasonKey,
} from "./helpers/trigger-presentation";
import { useNodeTrigger } from "./hooks/use-node-trigger";
import WebhookIngressPanel from "./WebhookIngressPanel";

/**
 * Trigger node body: the Enabled switch (enable/disable) and, for a source
 * that runs with a user connection, the B9 "Allow background runs" consent
 * for that connection. Consent is explicit and off by default; enabling a
 * trigger never sets it.
 */
export function TriggerNodeControls({ nodeId }: { nodeId: string }) {
  const { trigger, isLoading } = useNodeTrigger(nodeId);
  const { t } = useTranslation();
  if (isLoading) return null;
  if (!trigger) {
    return (
      <p
        className="border-t px-4 py-3 text-xs text-muted-foreground"
        data-testid="trigger-node-unsaved"
      >
        {t("triggers.node.unsaved")}
      </p>
    );
  }
  return <TriggerNodeControlsBody trigger={trigger} />;
}

function TriggerNodeControlsBody({ trigger }: { trigger: TriggerRead }) {
  const { t } = useTranslation();
  const enabledLabelId = useId();
  const enabledHintId = useId();
  const consentLabelId = useId();
  const consentHintId = useId();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const enable = useEnableTriggerMutation();
  const disable = useDisableTriggerMutation();
  const updateConnection = useUpdateConnectionMutation();
  const [enableRequested, setEnableRequested] = useState(false);

  // Once the state leaves `pending` the wire is unambiguous again.
  useEffect(() => {
    if (trigger.state !== "pending") setEnableRequested(false);
  }, [trigger.state]);

  const connections = useGetConnections(
    {},
    { enabled: Boolean(trigger.connection_id) },
  );
  // Only the caller's own connections are listed: exactly the ones they may
  // grant consent on.
  const connection = trigger.connection_id
    ? connections.data?.find((row) => row.id === trigger.connection_id)
    : undefined;
  const needsConsent =
    connection !== undefined && !connection.allow_non_interactive;

  const enabled = isTriggerEnabled(trigger, enableRequested);
  const toggle = availabilityOf(trigger, enabled ? "pause" : "resume");
  const blockedReason = toggle?.blockedReason;
  const busy = enable.isPending || disable.isPending;
  // Blocked stays focusable (aria-disabled) so the reason reaches keyboard
  // and screen-reader users; only an in-flight request truly disables it.
  const switchBlocked = Boolean(blockedReason) || (!enabled && needsConsent);
  const hint =
    needsConsent && !enabled
      ? t("triggers.node.consentFirst")
      : blockedReason
        ? t(blockedReasonKey(blockedReason))
        : null;

  const onToggle = async (next: boolean) => {
    try {
      if (next) {
        setEnableRequested(true);
        await enable.mutateAsync(trigger.id);
      } else {
        setEnableRequested(false);
        await disable.mutateAsync(trigger.id);
      }
    } catch (error) {
      setEnableRequested(false);
      setErrorData({
        title: next
          ? t("triggers.alerts.resumeFailed", { name: trigger.name })
          : t("triggers.alerts.pauseFailed", { name: trigger.name }),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    }
  };

  const onConsent = async (next: boolean) => {
    if (!connection) return;
    try {
      await updateConnection.mutateAsync({
        id: connection.id,
        patch: { allow_non_interactive: next },
      });
    } catch (error) {
      setErrorData({
        title: t("triggers.alerts.consentFailed"),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    }
  };

  return (
    <div
      className="flex flex-col gap-3 border-t px-4 py-3"
      data-testid="trigger-node-controls"
    >
      {trigger.kind === "inbound_webhook" && (
        <WebhookIngressPanel trigger={trigger} />
      )}
      {trigger.connection_id && (
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col">
            <span id={consentLabelId} className="text-sm font-medium">
              {t("triggers.consent.label")}
            </span>
            <span id={consentHintId} className="text-xs text-muted-foreground">
              {connection
                ? t("triggers.consent.hint", { name: connection.display_name })
                : t("triggers.consent.notOwner")}
            </span>
          </div>
          {connection && (
            <Switch
              checked={connection.allow_non_interactive}
              disabled={updateConnection.isPending}
              onCheckedChange={(next) => void onConsent(next)}
              aria-labelledby={consentLabelId}
              aria-describedby={consentHintId}
              data-testid="trigger-node-consent"
            />
          )}
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col">
          <span id={enabledLabelId} className="text-sm font-medium">
            {t("triggers.node.enabled")}
          </span>
          {hint && (
            <span id={enabledHintId} className="text-xs text-muted-foreground">
              {hint}
            </span>
          )}
        </div>
        {toggle && (
          <Switch
            checked={enabled}
            disabled={busy}
            aria-disabled={switchBlocked || undefined}
            className={
              switchBlocked ? "cursor-not-allowed opacity-50" : undefined
            }
            onCheckedChange={(next) => {
              if (!switchBlocked) void onToggle(next);
            }}
            aria-labelledby={enabledLabelId}
            aria-describedby={hint ? enabledHintId : undefined}
            data-testid="trigger-node-enabled"
          />
        )}
      </div>
    </div>
  );
}

export default TriggerNodeControls;
