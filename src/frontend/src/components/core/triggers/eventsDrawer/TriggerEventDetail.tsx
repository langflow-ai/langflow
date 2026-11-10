import { useTranslation } from "react-i18next";
import type {
  TriggerEventRead,
  TriggerRead,
} from "@/controllers/API/queries/triggers";
import { BlockableButton } from "../BlockableButton";
import { formatDateTime } from "../helpers/format-relative-time";
import {
  availabilityOf,
  blockedReasonKey,
  eventErrorKeyOf,
  parseServerTime,
} from "../helpers/trigger-presentation";
import {
  deliveryErrorOf,
  lineageOf,
  openRunBlockedKeyOf,
} from "./event-helpers";
import TriggerEventStateBadge from "./TriggerEventStateBadge";
import TriggerPayloadTree from "./TriggerPayloadTree";

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
  const time = parseServerTime(event.created_at);
  const errorKey = eventErrorKeyOf(event.error);
  const errorDetail = event.error_detail?.trim();
  const deliveryError = deliveryErrorOf(event);
  const replay = availabilityOf(trigger, "replay");
  const replayBlockedReason =
    event.state === "skipped"
      ? t("triggers.events.skippedCannotReplay")
      : replay?.blockedReason
        ? t(blockedReasonKey(replay.blockedReason))
        : undefined;
  const openRunBlockedKey = openRunBlockedKeyOf(event);
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
          {(errorDetail || errorKey) && (
            <p className="text-sm text-muted-foreground">
              {errorDetail || (errorKey ? t(errorKey) : null)}{" "}
              {event.error && (
                <code className="rounded bg-muted px-1 text-xs">
                  {event.error}
                </code>
              )}
            </p>
          )}
          {deliveryError && (
            <p
              className="text-sm text-destructive"
              data-testid="trigger-event-delivery-error"
            >
              {t("triggers.events.whatsapp.failed")}. {deliveryError}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <BlockableButton
            variant="outline"
            size="sm"
            blockedReason={openRunBlockedKey ? t(openRunBlockedKey) : undefined}
            onClick={() => onOpenRun(event)}
            data-testid="trigger-event-open-run"
          >
            {t("triggers.events.openRun")}
          </BlockableButton>
          {replay && (
            <BlockableButton
              size="sm"
              blockedReason={replayBlockedReason}
              loading={replaying}
              onClick={() => onReplay(event)}
              data-testid="trigger-event-replay"
            >
              {t("triggers.actions.replay")}
            </BlockableButton>
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
        <TriggerPayloadTree key={event.id} payload={event.payload} />
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
