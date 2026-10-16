import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TriggerEventRead } from "@/controllers/API/queries/triggers";
import { cn } from "@/utils/utils";
import { formatDateTime } from "../helpers/format-relative-time";
import {
  eventOriginOf,
  parseServerTime,
} from "../helpers/trigger-presentation";
import { eventSummaryOf } from "./event-helpers";
import TriggerEventStateBadge from "./TriggerEventStateBadge";

export interface TriggerEventListProps {
  events: TriggerEventRead[];
  selectedId: string | null;
  onSelect: (event: TriggerEventRead) => void;
  maxAttempts: number;
  canLoadMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
}

/** Ledger rows, newest first. Each row is one button; the selected one is current. */
export function TriggerEventList({
  events,
  selectedId,
  onSelect,
  maxAttempts,
  canLoadMore,
  loadingMore,
  onLoadMore,
}: TriggerEventListProps) {
  const { t, i18n } = useTranslation();
  return (
    <div className="flex flex-col gap-1">
      <ul
        aria-label={t("triggers.events.listLabel")}
        className="flex flex-col gap-1"
      >
        {events.map((event) => {
          const origin = eventOriginOf(event);
          const time = parseServerTime(event.created_at);
          const summary =
            eventSummaryOf(event) ?? t(`triggers.events.origin.${origin}`);
          const selected = event.id === selectedId;
          return (
            <li key={event.id}>
              <button
                type="button"
                aria-current={selected ? "true" : undefined}
                onClick={() => onSelect(event)}
                className={cn(
                  "flex w-full flex-col gap-1 rounded-md border border-transparent px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected && "border-border bg-muted",
                )}
                data-testid={`trigger-event-${event.id}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5">
                    <TriggerEventStateBadge event={event} />
                    {origin !== "event" && (
                      <Badge variant="outline" size="tag">
                        {t(`triggers.events.tag.${origin}`)}
                      </Badge>
                    )}
                  </span>
                  {time !== null && (
                    <time
                      className="shrink-0 text-xs text-muted-foreground"
                      dateTime={new Date(time).toISOString()}
                    >
                      {formatDateTime(time, i18n.language)}
                    </time>
                  )}
                </span>
                <span className="truncate">{summary}</span>
                {event.attempt > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {t("triggers.events.attempts", {
                      attempt: event.attempt,
                      max: maxAttempts,
                    })}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {canLoadMore && (
        <Button
          variant="outline"
          size="sm"
          className="mt-2 self-center"
          onClick={onLoadMore}
          loading={loadingMore}
          data-testid="trigger-events-load-more"
        >
          {t("triggers.events.loadOlder")}
        </Button>
      )}
    </div>
  );
}

export default TriggerEventList;
