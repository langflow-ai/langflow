import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { getAxiosErrorDetail } from "@/controllers/API/helpers/get-axios-error-message";
import {
  type TriggerEventRead,
  type TriggerRead,
  useReplayTriggerEventMutation,
  useTriggerEventsQuery,
  useTriggerQuery,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { sourceKeyOf } from "../helpers/trigger-presentation";
import TriggerStateBadge from "../TriggerStateBadge";
import TriggerTransportLabel from "../TriggerTransportLabel";
import {
  matchesEventFilter,
  TRIGGER_EVENT_FILTERS,
  type TriggerEventFilter,
} from "./event-helpers";
import ReplayConfirmDialog from "./ReplayConfirmDialog";
import TriggerEventDetail from "./TriggerEventDetail";
import TriggerEventList from "./TriggerEventList";
import TriggerRunDialog from "./trigger-run-dialog";

export interface TriggerEventsDrawerProps {
  trigger: TriggerRead | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * B4/B5: the trigger's ledger with filters, the selected event's normalized
 * payload and run link, and replay that shows the new linked event.
 */
export function TriggerEventsDrawer({
  trigger: opened,
  onOpenChange,
}: TriggerEventsDrawerProps) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [filter, setFilter] = useState<TriggerEventFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runFor, setRunFor] = useState<TriggerEventRead | null>(null);
  const [replayTarget, setReplayTarget] = useState<TriggerEventRead | null>(
    null,
  );
  const replay = useReplayTriggerEventMutation();

  // The opener hands over a snapshot; the drawer keeps it live.
  const live = useTriggerQuery(opened?.id);
  // The single-trigger route omits list-only fields such as flow_name.
  const trigger = opened
    ? live.data
      ? {
          ...opened,
          ...live.data,
          flow_name: live.data.flow_name ?? opened.flow_name,
        }
      : opened
    : null;
  const triggerId = trigger?.id;
  useEffect(() => {
    setFilter("all");
    setSelectedId(null);
    setRunFor(null);
    setReplayTarget(null);
  }, [triggerId]);

  const eventsQuery = useTriggerEventsQuery(triggerId);
  const events = eventsQuery.data ?? [];
  const visible = useMemo(
    () => events.filter((event) => matchesEventFilter(event, filter)),
    [events, filter],
  );
  const selected =
    visible.find((event) => event.id === selectedId) ?? visible[0] ?? null;

  const confirmReplay = async () => {
    if (!trigger || !replayTarget) return;
    try {
      const created = await replay.mutateAsync({
        triggerId: trigger.id,
        eventId: replayTarget.id,
      });
      setSuccessData({ title: t("triggers.replay.done") });
      setFilter("all");
      setSelectedId(created.id);
      setReplayTarget(null);
    } catch (error) {
      setErrorData({
        title: t("triggers.replay.failed"),
        list: [getAxiosErrorDetail(error, t("triggers.errors.unknown"))],
      });
    }
  };

  return (
    <Dialog open={opened !== null} onOpenChange={onOpenChange}>
      <DialogContent
        className="right-0 top-0 h-full max-h-screen w-full max-w-5xl gap-0 overflow-hidden rounded-none p-0 sm:rounded-l-xl"
        data-testid="trigger-events-drawer"
      >
        {trigger && (
          <div className="flex h-full min-h-0 flex-col">
            <header className="flex flex-col gap-1 border-b px-6 py-4 pr-12">
              <DialogTitle>
                {t("triggers.events.title", {
                  name: trigger.flow_name ?? trigger.name,
                })}
              </DialogTitle>
              <DialogDescription asChild>
                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <span>
                    {trigger.name} · {t(sourceKeyOf(trigger))} ·{" "}
                    <TriggerTransportLabel trigger={trigger} />
                  </span>
                  <TriggerStateBadge
                    state={trigger.state}
                    reason={trigger.reason}
                  />
                </div>
              </DialogDescription>
            </header>
            <div className="flex items-center gap-3 border-b px-6 py-3">
              <div
                role="group"
                aria-label={t("triggers.events.filterLabel")}
                className="flex gap-1 rounded-lg bg-muted p-1"
              >
                {TRIGGER_EVENT_FILTERS.map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={filter === option}
                    onClick={() => setFilter(option)}
                    className={cn(
                      "h-7 rounded-md px-3 text-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      filter === option &&
                        "bg-background font-medium text-foreground shadow-sm",
                    )}
                    data-testid={`trigger-events-filter-${option}`}
                  >
                    {t(`triggers.events.filters.${option}`)}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[22rem_1fr]">
              <div className="min-h-0 overflow-y-auto border-b p-3 md:border-b-0 md:border-r">
                {eventsQuery.isLoading ? (
                  <p
                    className="p-3 text-sm text-muted-foreground"
                    role="status"
                  >
                    {t("triggers.events.loading")}
                  </p>
                ) : eventsQuery.isError && events.length === 0 ? (
                  <p className="p-3 text-sm text-destructive" role="alert">
                    {getAxiosErrorDetail(
                      eventsQuery.error,
                      t("triggers.errors.load"),
                    )}
                  </p>
                ) : visible.length === 0 ? (
                  <p
                    className="p-3 text-sm text-muted-foreground"
                    data-testid="trigger-events-empty"
                  >
                    {filter === "all"
                      ? t("triggers.events.empty")
                      : t("triggers.events.emptyFiltered")}
                  </p>
                ) : (
                  <TriggerEventList
                    events={visible}
                    selectedId={selected?.id ?? null}
                    onSelect={(event) => setSelectedId(event.id)}
                    maxAttempts={trigger.max_attempts}
                  />
                )}
                {eventsQuery.isError && events.length > 0 && (
                  <p className="p-3 text-sm text-destructive" role="alert">
                    {getAxiosErrorDetail(
                      eventsQuery.error,
                      t("triggers.errors.load"),
                    )}
                  </p>
                )}
                {eventsQuery.hasNextPage && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => void eventsQuery.fetchNextPage()}
                    loading={eventsQuery.isFetching}
                    data-testid="trigger-events-load-more"
                  >
                    {t("triggers.events.loadOlder")}
                  </Button>
                )}
              </div>
              <div className="min-h-0 overflow-y-auto p-6">
                {selected && (
                  <TriggerEventDetail
                    trigger={trigger}
                    event={selected}
                    events={events}
                    onSelect={(event) => {
                      setFilter("all");
                      setSelectedId(event.id);
                    }}
                    onReplay={setReplayTarget}
                    onOpenRun={setRunFor}
                    replaying={replay.isPending}
                  />
                )}
              </div>
            </div>
          </div>
        )}
        <ReplayConfirmDialog
          open={replayTarget !== null}
          onOpenChange={(open) => {
            if (!open) setReplayTarget(null);
          }}
          onConfirm={() => void confirmReplay()}
          busy={replay.isPending}
        />
        {trigger && runFor?.job_id && (
          <TriggerRunDialog
            event={runFor}
            flowName={trigger.flow_name ?? trigger.name}
            onOpenChange={(open) => {
              if (!open) setRunFor(null);
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

export default TriggerEventsDrawer;
