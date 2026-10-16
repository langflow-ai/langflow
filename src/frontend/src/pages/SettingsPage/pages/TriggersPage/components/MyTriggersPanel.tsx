import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  filterTriggers,
  type TriggerStateFilter,
} from "@/components/core/triggers/helpers/filter-triggers";
import { needsAttention } from "@/components/core/triggers/helpers/trigger-presentation";
import type { TriggerUiAction } from "@/components/core/triggers/hooks/use-trigger-action-runner";
import TriggerActionMenu from "@/components/core/triggers/TriggerActionMenu";
import TriggerTestButton from "@/components/core/triggers/TriggerTestButton";
import { useGetConnections } from "@/controllers/API/queries/connections";
import {
  type TriggerRead,
  useTriggersQuery,
} from "@/controllers/API/queries/triggers";
import TriggersListState from "./TriggersListState";
import TriggersTable from "./TriggersTable";
import TriggersToolbar from "./TriggersToolbar";

/** The owner list is one page of the newest triggers the caller can read. */
const MY_PAGE_SIZE = 200;

export interface MyTriggersPanelProps {
  busyId: string | null;
  onAction: (trigger: TriggerRead, action: TriggerUiAction) => void;
}

/** B2: triggers on every flow the caller can read. */
export function MyTriggersPanel({ busyId, onAction }: MyTriggersPanelProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [state, setState] = useState<TriggerStateFilter>("all");

  const query = useTriggersQuery({ limit: MY_PAGE_SIZE });
  const connections = useGetConnections({});
  const triggers = query.data ?? [];
  const visible = useMemo(
    () => filterTriggers(triggers, { search, state }),
    [triggers, search, state],
  );
  const connectionNames = useMemo(
    () =>
      new Map(
        (connections.data ?? []).map((row) => [row.id, row.display_name]),
      ),
    [connections.data],
  );

  return (
    <div className="flex flex-col gap-4">
      <TriggersToolbar
        search={search}
        onSearchChange={setSearch}
        state={state}
        onStateChange={setState}
        attentionCount={triggers.filter(needsAttention).length}
        searchPlaceholderKey="triggers.search"
      />
      <TriggersListState
        query={query}
        total={triggers.length}
        visible={visible.length}
        emptyKey="triggers.empty.mine"
      >
        <TriggersTable
          triggers={visible}
          mode="mine"
          connectionNames={connectionNames}
          busyId={busyId}
          onFix={onAction}
          renderTest={(trigger) => (
            <TriggerTestButton
              trigger={trigger}
              busy={busyId === trigger.id}
              onTest={(row) => onAction(row, "test")}
            />
          )}
          renderActions={(trigger) => (
            <TriggerActionMenu
              trigger={trigger}
              busy={busyId === trigger.id}
              onAction={onAction}
            />
          )}
        />
      </TriggersListState>
      {triggers.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {t("triggers.count", { count: triggers.length })}
        </p>
      )}
    </div>
  );
}

export default MyTriggersPanel;
