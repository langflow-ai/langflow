import type { TriggerEventRead } from "@/controllers/API/queries/triggers";
import { eventOriginOf } from "../helpers/trigger-presentation";

const SUMMARY_KEYS = ["text", "summary", "subject", "title", "name"] as const;
const MAX_SUMMARY = 80;

/**
 * One line for the list row, read from the normalized payload's most
 * telling text field; null when the payload has none (the row then names its
 * origin instead).
 */
export const eventSummaryOf = (
  event: Pick<TriggerEventRead, "payload">,
): string | null => {
  for (const key of SUMMARY_KEYS) {
    const value = event.payload?.[key];
    if (typeof value === "string" && value.trim()) {
      const line = value.trim().replace(/\s+/g, " ");
      return line.length > MAX_SUMMARY
        ? `${line.slice(0, MAX_SUMMARY - 1)}…`
        : line;
    }
  }
  return null;
};

export type TriggerEventFilter = "all" | "failed" | "replays" | "tests";

export const TRIGGER_EVENT_FILTERS: readonly TriggerEventFilter[] = [
  "all",
  "failed",
  "replays",
  "tests",
];

export const matchesEventFilter = (
  event: Pick<TriggerEventRead, "state" | "dedupe_key" | "replay_of_event_id">,
  filter: TriggerEventFilter,
): boolean => {
  switch (filter) {
    case "all":
      return true;
    case "failed":
      return event.state === "failed" || event.state === "dead";
    case "replays":
      return eventOriginOf(event) === "replay";
    case "tests":
      return eventOriginOf(event) === "test";
  }
};

/** The replay's parent, if loaded, and every loaded replay of this event. */
export const lineageOf = (
  event: Pick<TriggerEventRead, "id" | "replay_of_event_id">,
  events: readonly TriggerEventRead[],
): { parent: TriggerEventRead | undefined; replays: TriggerEventRead[] } => ({
  parent: event.replay_of_event_id
    ? events.find((row) => row.id === event.replay_of_event_id)
    : undefined,
  replays: events.filter((row) => row.replay_of_event_id === event.id),
});
