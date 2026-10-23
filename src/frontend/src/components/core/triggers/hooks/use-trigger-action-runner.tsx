import { type ReactNode, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import {
  useGetConnections,
  useUpdateConnectionMutation,
} from "@/controllers/API/queries/connections";
import {
  type TriggerAction,
  type TriggerRead,
  useDeleteTriggerMutation,
  useDisableTriggerMutation,
  useEnableTriggerMutation,
  useTestTriggerMutation,
} from "@/controllers/API/queries/triggers";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import BackgroundRunsConsentDialog from "../BackgroundRunsConsentDialog";

/** Client-only actions that sit beside the server's vocabulary. */
export type TriggerUiAction = TriggerAction | "view_events" | "open_flow";

export interface TriggerActionRunnerOptions {
  onViewEvents?: (trigger: TriggerRead) => void;
  onRotateSecret?: (trigger: TriggerRead) => void;
}

export interface TriggerActionRunner {
  run: (trigger: TriggerRead, action: TriggerUiAction) => void;
  /** Trigger currently running a mutation; its controls disable meanwhile. */
  busyId: string | null;
  /** Confirmation and consent dialogs; render once wherever the runner is used. */
  dialogs: ReactNode;
}

/**
 * One place that turns a trigger action into its route, alert and follow-up,
 * so the node popover, the table row and the events drawer behave the same.
 * The server already decided whether the action is allowed; this only runs it.
 */
export function useTriggerActionRunner(
  options: TriggerActionRunnerOptions = {},
): TriggerActionRunner {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const enable = useEnableTriggerMutation();
  const disable = useDisableTriggerMutation();
  const remove = useDeleteTriggerMutation();
  const test = useTestTriggerMutation();
  const updateConnection = useUpdateConnectionMutation();

  const [busyId, setBusyId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<TriggerRead | null>(null);
  const [consentFor, setConsentFor] = useState<TriggerRead | null>(null);

  // Only the caller's own connections are listed, which is exactly the set
  // they may grant consent on; the server blocks reconnect for anyone else.
  const connections = useGetConnections({}, { enabled: consentFor !== null });
  const consentConnection = consentFor
    ? connections.data?.find((row) => row.id === consentFor.connection_id)
    : undefined;

  const withBusy = useCallback(
    async (
      trigger: TriggerRead,
      work: () => Promise<unknown>,
      success: string,
      failure: string,
    ) => {
      setBusyId(trigger.id);
      try {
        await work();
        setSuccessData({ title: success });
      } catch (error) {
        setErrorData({
          title: failure,
          list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
        });
      } finally {
        setBusyId(null);
      }
    },
    [setErrorData, setSuccessData, t],
  );

  const run = useCallback(
    (trigger: TriggerRead, action: TriggerUiAction) => {
      const name = trigger.name;
      switch (action) {
        case "view_events":
          options.onViewEvents?.(trigger);
          return;
        case "open_flow":
          navigate(`/flow/${trigger.flow_id}`);
          return;
        case "rotate_secret":
          options.onRotateSecret?.(trigger);
          return;
        case "delete":
          setDeleting(trigger);
          return;
        case "reconnect":
          // Missing consent is fixed by the consent switch, not an OAuth loop.
          if (trigger.reason === "consent_required") {
            setConsentFor(trigger);
          } else {
            navigate("/settings/connections");
          }
          return;
        case "pause":
          void withBusy(
            trigger,
            () => disable.mutateAsync(trigger.id),
            t("triggers.alerts.paused", { name }),
            t("triggers.alerts.pauseFailed", { name }),
          );
          return;
        case "resume":
          void withBusy(
            trigger,
            () => enable.mutateAsync(trigger.id),
            t("triggers.alerts.resumed", { name }),
            t("triggers.alerts.resumeFailed", { name }),
          );
          return;
        case "test":
          void withBusy(
            trigger,
            () => test.mutateAsync(trigger.id),
            t("triggers.alerts.testSent", { name }),
            t("triggers.alerts.testFailed", { name }),
          );
          return;
        case "replay":
          // Replay targets one event, so it lives in the events drawer.
          options.onViewEvents?.(trigger);
          return;
      }
    },
    [disable, enable, navigate, options, t, test, withBusy],
  );

  const confirmConsent = useCallback(async () => {
    const trigger = consentFor;
    if (!trigger || !consentConnection) return;
    setBusyId(trigger.id);
    try {
      await updateConnection.mutateAsync({
        id: consentConnection.id,
        patch: { allow_non_interactive: true },
      });
      // The server rechecks credentials and policy on enable; a refusal keeps
      // the trigger blocked and says why.
      await enable.mutateAsync(trigger.id);
      setSuccessData({
        title: t("triggers.alerts.resumed", { name: trigger.name }),
      });
      setConsentFor(null);
    } catch (error) {
      setErrorData({
        title: t("triggers.alerts.consentFailed"),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    } finally {
      setBusyId(null);
    }
  }, [
    consentConnection,
    consentFor,
    enable,
    setErrorData,
    setSuccessData,
    t,
    updateConnection,
  ]);

  const dialogs = (
    <>
      <DeleteConfirmationModal
        open={deleting !== null}
        setOpen={(open) => {
          if (!open) setDeleting(null);
        }}
        description={t("triggers.delete.description", {
          name: deleting?.name ?? "",
        })}
        onConfirm={() => {
          const trigger = deleting;
          setDeleting(null);
          if (!trigger) return;
          void withBusy(
            trigger,
            () => remove.mutateAsync(trigger.id),
            t("triggers.alerts.deleted", { name: trigger.name }),
            t("triggers.alerts.deleteFailed", { name: trigger.name }),
          );
        }}
      />
      <BackgroundRunsConsentDialog
        open={consentFor !== null}
        onOpenChange={(open) => {
          if (!open) setConsentFor(null);
        }}
        connection={consentConnection}
        busy={busyId !== null && busyId === consentFor?.id}
        onConfirm={() => void confirmConsent()}
      />
    </>
  );

  return { run, busyId, dialogs };
}
