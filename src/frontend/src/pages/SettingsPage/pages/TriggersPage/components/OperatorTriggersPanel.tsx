import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  filterTriggers,
  providersOf,
  type TriggerStateFilter,
} from "@/components/core/triggers/helpers/filter-triggers";
import { needsAttention } from "@/components/core/triggers/helpers/trigger-presentation";
import { Button } from "@/components/ui/button";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import {
  type TriggerBulkAction,
  type TriggerRead,
  useBulkTriggersMutation,
  useTriggersQuery,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import BulkTriggersDialog from "./BulkTriggersDialog";
import OperatorRowMenu from "./OperatorRowMenu";
import TriggersListState from "./TriggersListState";
import TriggersTable from "./TriggersTable";
import TriggersToolbar from "./TriggersToolbar";

const NO_CONNECTION_NAMES = new Map<string, string>();

/** B3: every user's triggers, a provider filter, and bulk pause or resume. */
export function OperatorTriggersPanel() {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [search, setSearch] = useState("");
  const [state, setState] = useState<TriggerStateFilter>("all");
  const [provider, setProvider] = useState<string | undefined>();
  const [bulkAction, setBulkAction] = useState<TriggerBulkAction | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const bulk = useBulkTriggersMutation();

  const query = useTriggersQuery({ scope: "all" }, { allPages: true });
  const triggers = query.data ?? [];
  const providers = useMemo(() => providersOf(triggers), [triggers]);
  const visible = useMemo(
    () => filterTriggers(triggers, { search, state, provider }),
    [triggers, search, state, provider],
  );
  const providerName = provider
    ? t(`triggers.provider.${provider}`, { defaultValue: provider })
    : "";

  const runOne = async (trigger: TriggerRead, action: TriggerBulkAction) => {
    setBusyId(trigger.id);
    try {
      const result = await bulk.mutateAsync({
        action,
        body: { trigger_ids: [trigger.id] },
      });
      if (result.failed.length > 0) {
        setErrorData({
          title: t(`triggers.bulk.${action}.failed`),
          list: result.failed.map((failure) => failure.detail),
        });
      } else if (result.changed.length === 0) {
        setSuccessData({
          title: t(`triggers.operator.${action}NotEligible`, {
            name: trigger.name,
          }),
        });
      } else {
        setSuccessData({
          title: t(
            `triggers.alerts.${action === "pause" ? "paused" : "resumed"}`,
            {
              name: trigger.name,
            },
          ),
        });
      }
    } catch (error) {
      setErrorData({
        title: t(`triggers.bulk.${action}.failed`),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <TriggersToolbar
          search={search}
          onSearchChange={setSearch}
          state={state}
          onStateChange={setState}
          attentionCount={triggers.filter(needsAttention).length}
          providers={providers}
          provider={provider}
          onProviderChange={setProvider}
          searchPlaceholderKey="triggers.searchOperator"
        />
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={!provider}
            onClick={() => setBulkAction("resume")}
            data-testid="triggers-bulk-resume"
          >
            {provider
              ? t("triggers.operator.resumeAll", { provider: providerName })
              : t("triggers.operator.resumeAllNoProvider")}
          </Button>
          <Button
            disabled={!provider}
            onClick={() => setBulkAction("pause")}
            data-testid="triggers-bulk-pause"
          >
            {provider
              ? t("triggers.operator.pauseAll", { provider: providerName })
              : t("triggers.operator.pauseAllNoProvider")}
          </Button>
        </div>
      </div>
      <TriggersListState
        query={query}
        total={triggers.length}
        visible={visible.length}
        emptyKey="triggers.empty.operator"
      >
        <TriggersTable
          triggers={visible}
          mode="all"
          connectionNames={NO_CONNECTION_NAMES}
          busyId={busyId}
          onFix={() => undefined}
          renderActions={(trigger) => (
            <OperatorRowMenu
              trigger={trigger}
              busy={busyId === trigger.id}
              onBulk={(row, action) => void runOne(row, action)}
            />
          )}
        />
      </TriggersListState>
      {provider && bulkAction && (
        <BulkTriggersDialog
          open
          onOpenChange={(open) => {
            if (!open) setBulkAction(null);
          }}
          action={bulkAction}
          provider={provider}
        />
      )}
    </div>
  );
}

export default OperatorTriggersPanel;
