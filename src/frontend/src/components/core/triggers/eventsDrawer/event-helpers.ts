import type {
  TriggerEventFilterParam,
  TriggerEventRead,
} from "@/controllers/API/queries/triggers";

const SUMMARY_KEYS = ["text", "summary", "subject", "title", "name"] as const;
const MAX_SUMMARY = 80;

const WHATSAPP_STATUS_KEYS = new Map([
  ["sent", "triggers.events.whatsapp.sent"],
  ["delivered", "triggers.events.whatsapp.delivered"],
  ["read", "triggers.events.whatsapp.read"],
  ["failed", "triggers.events.whatsapp.failed"],
]);

const whatsappDataOf = (event: Pick<TriggerEventRead, "payload">) => {
  const data = event.payload?.data;
  return event.payload?.provider === "whatsapp" &&
    data !== null &&
    typeof data === "object" &&
    !Array.isArray(data)
    ? (data as Record<string, unknown>)
    : null;
};

/** WhatsApp event types stay visible even when a delivery has no message text. */
export const eventLabelKeyOf = (
  event: Pick<TriggerEventRead, "payload">,
): string | null => {
  const data = whatsappDataOf(event);
  if (data?.event === "message") return "triggers.events.whatsapp.message";
  if (data?.event !== "status") return null;
  return typeof data.status === "string"
    ? (WHATSAPP_STATUS_KEYS.get(data.status) ??
        "triggers.events.whatsapp.status")
    : "triggers.events.whatsapp.status";
};

/** Only the normalized delivery failure is shown, never provider response bodies. */
export const deliveryErrorOf = (
  event: Pick<TriggerEventRead, "payload">,
): string | null => {
  const data = whatsappDataOf(event);
  return data?.event === "status" &&
    data.status === "failed" &&
    typeof data.delivery_error === "string"
    ? data.delivery_error.trim().slice(0, 500) || null
    : null;
};

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

/**
 * The event's run is under way: its trace is written only when the run ends,
 * so until then there is nothing to load.
 */
export const isEventRunning = (event: Pick<TriggerEventRead, "state">) =>
  event.state === "claimed" || event.state === "dispatched";

/**
 * Why "Open flow" is unavailable for ``event``, as a catalog key, or null when
 * its run can be opened. A run exists only once the event is dispatched.
 */
export const openRunBlockedKeyOf = (
  event: Pick<TriggerEventRead, "state" | "job_id">,
): string | null => {
  if (event.job_id) return null;
  return event.state === "pending" || event.state === "claimed"
    ? "triggers.events.runNotStarted"
    : "triggers.events.noRunStarted";
};

export type TriggerEventFilter = "all" | TriggerEventFilterParam;

export const TRIGGER_EVENT_FILTERS: readonly TriggerEventFilter[] = [
  "all",
  "failed",
  "skipped",
  "replays",
  "tests",
];

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
