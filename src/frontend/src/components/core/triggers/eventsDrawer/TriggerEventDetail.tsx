import { useId } from "react";
import { useTranslation } from "react-i18next";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import type {
  TriggerEventRead,
  TriggerRead,
} from "@/controllers/API/queries/triggers";
import { formatDateTime } from "../helpers/format-relative-time";
import {
  availabilityOf,
  blockedReasonKey,
  eventErrorKeyOf,
  parseServerTime,
} from "../helpers/trigger-presentation";
import { lineageOf } from "./event-helpers";
import TriggerEventStateBadge from "./TriggerEventStateBadge";

export interface TriggerEventDetailProps {
  trigger: TriggerRead;
  event: TriggerEventRead;
  events: TriggerEventRead[];
  onSelect: (event: TriggerEventRead) => void;
  onReplay: (event: TriggerEventRead) => void;
  onOpenRun: (event: TriggerEventRead) => void;
  replaying: boolean;
}

export function TriggerEventDetail({
  trigger,
  event,
  events,
  onSelect,
  onReplay,
  onOpenRun,
  replaying,
}: TriggerEventDetailProps) {
  const { t, i18n } = useTranslation();
  const replayReasonId = useId();
  const time = parseServerTime(event.created_at);
  const errorKey = eventErrorKeyOf(event.error);
  const replay = availabilityOf(trigger, "replay");
  const { parent, replays } = lineageOf(event, events);
  const when = (row: TriggerEventRead) => {
    const at = parseServerTime(row.created_at);
    return at === null ? "" : formatDateTime(at, i18n.language);
  };

  return (
    <section
      aria-label={t("triggers.events.detailLabel")}
      className="flex min-w-0 flex-col gap-5"
      data-testid="trigger-event-detail"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <TriggerEventStateBadge event={event} />
            {time !== null && (
              <span className="font-medium">
                {formatDateTime(time, i18n.language)}
              </span>
            )}
          </div>
          {errorKey && (
            <p className="text-sm text-muted-foreground">
              {t(errorKey)}{" "}
              <code className="rounded bg-muted px-1 text-xs">
                {event.error}
              </code>
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!event.job_id}
            onClick={() => onOpenRun(event)}
            data-testid="trigger-event-open-run"
          >
            {t("triggers.events.openRun")}
          </Button>
          {replay && (
            <ShadTooltip
              content={
                replay.blockedReason
                  ? t(blockedReasonKey(replay.blockedReason))
                  : undefined
              }
            >
              <Button
                size="sm"
                aria-disabled={replay.blockedReason ? true : undefined}
                aria-describedby={
                  replay.blockedReason ? replayReasonId : undefined
                }
                className={
                  replay.blockedReason ? "cursor-not-allowed opacity-50" : ""
                }
                loading={replaying}
                onClick={() => {
                  if (!replay.blockedReason) onReplay(event);
                }}
                data-testid="trigger-event-replay"
              >
                {t("triggers.actions.replay")}
                {replay.blockedReason && (
                  <span id={replayReasonId} className="sr-only">
                    {t(blockedReasonKey(replay.blockedReason))}
                  </span>
                )}
              </Button>
            </ShadTooltip>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">
          {t("triggers.events.received")}
        </dt>
        <dd>{time === null ? "–" : formatDateTime(time, i18n.language)}</dd>
        <dt className="text-muted-foreground">
          {t("triggers.events.attemptsLabel")}
        </dt>
        <dd>
          {t("triggers.events.attemptsValue", {
            attempt: event.attempt,
            max: trigger.max_attempts,
          })}
        </dd>
        <dt className="text-muted-foreground">
          {t("triggers.events.session")}
        </dt>
        <dd className="break-all font-mono text-xs">
          {event.session_id ?? "–"}
        </dd>
        <dt className="text-muted-foreground">
          {t("triggers.events.dedupeKey")}
        </dt>
        <dd className="break-all font-mono text-xs">{event.dedupe_key}</dd>
      </dl>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">{t("triggers.events.payload")}</h3>
        {/* Wraps instead of scrolling: a scroll box of its own would need a
            tab stop, and no role IBM accepts on a tab stop fits read-only
            text. The detail pane scrolls a long payload instead. */}
        <pre
          className="whitespace-pre-wrap break-all rounded-md border bg-muted p-3 font-mono text-xs"
          data-testid="trigger-event-payload"
        >
          {JSON.stringify(event.payload, null, 2)}
        </pre>
        <p className="text-xs text-muted-foreground">
          {t("triggers.events.payloadNote")}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium">{t("triggers.events.lineage")}</h3>
        <ol
          className="flex flex-col gap-1 text-sm"
          data-testid="trigger-event-lineage"
        >
          {event.replay_of_event_id && (
            <li className="flex items-center gap-2">
              <span className="text-muted-foreground">
                {t("triggers.events.replayOf")}
              </span>
              {parent ? (
                <button
                  type="button"
                  className="underline underline-offset-2"
                  onClick={() => onSelect(parent)}
                >
                  {when(parent)}
                </button>
              ) : (
                <span className="text-muted-foreground">
                  {t("triggers.events.parentNotLoaded")}
                </span>
              )}
            </li>
          )}
          <li className="flex items-center gap-2">
            <span className="font-medium">
              {t("triggers.events.thisEvent")}
            </span>
            <TriggerEventStateBadge event={event} />
          </li>
          {replays.map((child) => (
            <li key={child.id} className="flex items-center gap-2">
              <span className="text-muted-foreground">
                {t("triggers.events.replayAt", { time: when(child) })}
              </span>
              <TriggerEventStateBadge event={child} />
              <button
                type="button"
                className="underline underline-offset-2"
                onClick={() => onSelect(child)}
              >
                {t("triggers.events.view")}
              </button>
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">
          {t("triggers.events.replayNote")}
        </p>
      </div>
    </section>
  );
}

export default TriggerEventDetail;
