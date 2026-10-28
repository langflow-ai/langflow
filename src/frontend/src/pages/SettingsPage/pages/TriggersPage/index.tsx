import { useState } from "react";
import { useTranslation } from "react-i18next";
import TriggerEventsDrawer from "@/components/core/triggers/eventsDrawer";
import { useTriggerActionRunner } from "@/components/core/triggers/hooks/use-trigger-action-runner";
import SigningSecretDialog from "@/components/core/triggers/SigningSecretDialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import useAuthStore from "@/stores/authStore";
import MyTriggersPanel from "./components/MyTriggersPanel";
import OperatorTriggersPanel from "./components/OperatorTriggersPanel";

/** Settings › Triggers: flows that start on their own. */
export default function TriggersPage() {
  const { t } = useTranslation();
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  const [view, setView] = useState("mine");
  const [eventsFor, setEventsFor] = useState<TriggerRead | null>(null);
  const [secretFor, setSecretFor] = useState<TriggerRead | null>(null);
  const runner = useTriggerActionRunner({
    onViewEvents: setEventsFor,
    onRotateSecret: setSecretFor,
  });

  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex flex-col">
        <h2 className="text-lg font-semibold">{t("triggers.title")}</h2>
        <p className="text-sm text-muted-foreground">
          {t("triggers.subtitle")}
        </p>
      </div>

      {/* Radix keeps unselected panels mounted and `hidden`; panel bodies bring
          their own layout so TabsContent carries no display utility. */}
      <Tabs
        value={view}
        onValueChange={setView}
        className="flex w-full flex-col gap-6"
      >
        <TabsList aria-label={t("triggers.tabs.label")} className="w-fit">
          <TabsTrigger value="mine">{t("triggers.tabs.mine")}</TabsTrigger>
          {isSuperuser && (
            <TabsTrigger value="all">{t("triggers.tabs.all")}</TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="mine" className="mt-0">
          {view === "mine" && (
            <MyTriggersPanel busyId={runner.busyId} onAction={runner.run} />
          )}
        </TabsContent>
        {isSuperuser && (
          <TabsContent value="all" className="mt-0">
            {view === "all" && <OperatorTriggersPanel />}
          </TabsContent>
        )}
      </Tabs>

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
