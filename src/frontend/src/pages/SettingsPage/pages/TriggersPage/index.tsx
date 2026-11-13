import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import TriggerEventsDrawer from "@/components/core/triggers/eventsDrawer";
import type { TriggerStateFilter } from "@/components/core/triggers/helpers/filter-triggers";
import { useTriggerActionRunner } from "@/components/core/triggers/hooks/use-trigger-action-runner";
import SigningSecretDialog from "@/components/core/triggers/SigningSecretDialog";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import useAuthStore from "@/stores/authStore";
import MyTriggersPanel from "./components/MyTriggersPanel";
import OperatorTriggersPanel from "./components/OperatorTriggersPanel";
import type { TriggerScope } from "./components/TriggersToolbar";

/** Settings › Triggers: flows that start on their own. */
export default function TriggersPage() {
  const { t } = useTranslation();
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  const [scope, setScope] = useState<TriggerScope>("mine");
  const previousScope = useRef(scope);
  const scopeTriggerRef = useRef<HTMLButtonElement>(null);
  const [search, setSearch] = useState("");
  const [state, setState] = useState<TriggerStateFilter>("all");
  const [eventsFor, setEventsFor] = useState<TriggerRead | null>(null);
  const [secretFor, setSecretFor] = useState<TriggerRead | null>(null);
  const runner = useTriggerActionRunner({
    onViewEvents: setEventsFor,
    onRotateSecret: setSecretFor,
  });
  useEffect(() => {
    if (previousScope.current !== scope) {
      scopeTriggerRef.current?.focus();
      previousScope.current = scope;
    }
  }, [scope]);

  const filters = {
    search,
    onSearchChange: setSearch,
    state,
    onStateChange: setState,
    scope,
    onScopeChange: isSuperuser ? setScope : undefined,
    scopeTriggerRef,
  };

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex flex-col">
        <h2 className="text-lg font-semibold">{t("triggers.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("triggers.subtitle")}
        </p>
      </div>

      {isSuperuser && scope === "all" ? (
        <OperatorTriggersPanel {...filters} />
      ) : (
        <MyTriggersPanel
          {...filters}
          busyId={runner.busyId}
          onAction={runner.run}
        />
      )}

      <TriggerEventsDrawer
        trigger={eventsFor}
        onOpenChange={(open) => {
          if (!open) setEventsFor(null);
        }}
      />
      <SigningSecretDialog
        trigger={secretFor}
        onOpenChange={(open) => {
          if (!open) setSecretFor(null);
        }}
      />
      {runner.dialogs}
    </div>
  );
}
