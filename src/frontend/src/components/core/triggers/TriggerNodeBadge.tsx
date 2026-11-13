import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import { useTriggerPollingInterval } from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import TriggerEventsDrawer from "./eventsDrawer";
import { formatRelativeTime } from "./helpers/format-relative-time";
import {
  availabilityOf,
  badgeLabelKey,
  badgeStateOf,
  blockedReasonKey,
  parseServerTime,
  TRIGGER_BADGE_STYLE,
  transportOf,
} from "./helpers/trigger-presentation";
import { useNodeTrigger } from "./hooks/use-node-trigger";
import { useTriggerActionRunner } from "./hooks/use-trigger-action-runner";
import TriggerStatusSummary from "./TriggerStatusSummary";
import TriggerTransportLabel from "./TriggerTransportLabel";

/**
 * A1/B1: the trigger's state in the node header. Opens a popover with the
 * reason, the one fix, and the actions the server allows; unavailable ones
 * stay visible with their reason.
 */
export function TriggerNodeBadge({ trigger }: { trigger: TriggerRead }) {
  const { t, i18n } = useTranslation();
  const interval = useTriggerPollingInterval();
  const [open, setOpen] = useState(false);
  const [eventsFor, setEventsFor] = useState<TriggerRead | null>(null);
  const runner = useTriggerActionRunner({ onViewEvents: setEventsFor });
  const badgeState = badgeStateOf(trigger.state, trigger.reason);
  const style = TRIGGER_BADGE_STYLE[badgeState];
  const label = t(badgeLabelKey(badgeState));
  const lastFired = parseServerTime(trigger.last_fired_at);
  const busy = runner.busyId === trigger.id;
  const test = availabilityOf(trigger, "test");

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              "nodrag flex h-6 shrink-0 items-center gap-1 rounded-sm px-1.5 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              style.className,
            )}
            aria-label={t("triggers.node.badgeAria", { state: label })}
            data-testid="trigger-node-badge"
            data-state={trigger.state}
          >
            <ForwardedIconComponent
              name={style.icon}
              aria-hidden="true"
              className={cn(
                "h-3 w-3",
                badgeState === "pending" && "motion-safe:animate-spin",
              )}
            />
            {label}
          </button>
        </PopoverTrigger>
        {/* Non-portaled so the popover follows the canvas transform. */}
        <PopoverContentWithoutPortal
          side="bottom"
          align="end"
          className="nodrag nopan nowheel flex w-80 cursor-auto flex-col gap-3 p-4"
          aria-label={t("triggers.node.details")}
          data-testid="trigger-node-popover"
        >
          <TriggerStatusSummary
            trigger={trigger}
            busy={busy}
            onFix={runner.run}
            explainRunning
          />
          <p className="text-xs text-muted-foreground">
            {t("triggers.node.polled", {
              seconds: Math.round(interval / 1000),
            })}
          </p>
          <dl className="grid grid-cols-[6rem_1fr] gap-y-1 text-xs">
            <dt className="text-muted-foreground">
              {transportOf(trigger) === "schedule"
                ? t("triggers.kind.schedule")
                : t("triggers.node.transport")}
            </dt>
            <dd>
              <TriggerTransportLabel trigger={trigger} />
            </dd>
            <dt className="text-muted-foreground">
              {t("triggers.columns.lastEvent")}
            </dt>
            <dd>
              {lastFired === null
                ? t("triggers.lastEvent.never")
                : formatRelativeTime(lastFired, i18n.language)}
            </dd>
          </dl>
          <div className="flex flex-wrap gap-2">
            {test && (
              <ShadTooltip
                content={
                  test.blockedReason
                    ? t(blockedReasonKey(test.blockedReason))
                    : undefined
                }
              >
                <Button
                  size="sm"
                  variant="outline"
                  aria-disabled={test.blockedReason ? true : undefined}
                  aria-description={
                    test.blockedReason
                      ? t(blockedReasonKey(test.blockedReason))
                      : undefined
                  }
                  className={
                    test.blockedReason
                      ? "cursor-not-allowed opacity-50 aria-disabled:pointer-events-auto"
                      : ""
                  }
                  loading={busy}
                  onClick={() => {
                    if (!test.blockedReason) runner.run(trigger, "test");
                  }}
                  data-testid="trigger-node-test"
                >
                  {t("triggers.actions.test")}
                </Button>
              </ShadTooltip>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setOpen(false);
                runner.run(trigger, "view_events");
              }}
              data-testid="trigger-node-events"
            >
              {t("triggers.actions.view_events")}
            </Button>
          </div>
        </PopoverContentWithoutPortal>
      </Popover>
      <TriggerEventsDrawer
        trigger={eventsFor}
        onOpenChange={(next) => {
          if (!next) setEventsFor(null);
        }}
      />
      {runner.dialogs}
    </>
  );
}

export default TriggerNodeBadge;

/** The badge for a canvas node, once its flow has been saved into a trigger row. */
export function TriggerNodeStatus({ nodeId }: { nodeId: string }) {
  const { trigger } = useNodeTrigger(nodeId);
  return trigger ? <TriggerNodeBadge trigger={trigger} /> : null;
}
