import type {
  TriggerAction,
  TriggerEventRead,
  TriggerRead,
  TriggerReason,
  TriggerState,
} from "@/controllers/API/queries/triggers";

/**
 * Blocked configuration needs attention, while ordinary pending setup is busy.
 * Dead triggers share the Error treatment.
 */
export type TriggerBadgeState = Exclude<TriggerState, "dead"> | "blocked";

export const badgeStateOf = (
  state: TriggerState,
  reason?: TriggerRead["reason"],
): TriggerBadgeState =>
  state === "pending" && reason === "config_invalid"
    ? "blocked"
    : state === "dead"
      ? "error"
      : state;

interface BadgeStyle {
  icon: string;
  className: string;
}

/** Every badge pairs an icon with text, never color alone. */
export const TRIGGER_BADGE_STYLE: Record<TriggerBadgeState, BadgeStyle> = {
  blocked: {
    icon: "TriangleAlert",
    className: "bg-accent-amber text-accent-amber-foreground border-0",
  },
  pending: {
    icon: "LoaderCircle",
    className: "bg-accent-indigo text-accent-indigo-foreground border-0",
  },
  active: {
    icon: "CircleCheck",
    className: "bg-accent-emerald text-accent-emerald-foreground border-0",
  },
  paused: {
    icon: "Pause",
    className: "bg-muted text-muted-foreground border-0",
  },
  expired: {
    icon: "Hourglass",
    className:
      "border border-accent-amber-foreground bg-background text-accent-amber-foreground",
  },
  needs_reconnect: {
    icon: "Unplug",
    className: "bg-accent-amber text-accent-amber-foreground border-0",
  },
  error: {
    icon: "TriangleAlert",
    className: "bg-error-background text-error-foreground border-0",
  },
};

/** Locale key for the badge label. */
export const badgeLabelKey = (state: TriggerBadgeState): string =>
  `triggers.state.${state}`;

/**
 * The popover headline and the line under the table badge. A trigger running
 * cleanly carries no reason; it still gets a sentence.
 */
export const reasonKey = (trigger: Pick<TriggerRead, "reason">): string =>
  `triggers.reason.${trigger.reason ?? "running"}`;

/** Tooltip for an action the server refused. */
export const blockedReasonKey = (reason: TriggerReason): string =>
  `triggers.blocked.${reason}`;

export const actionLabelKey = (action: TriggerAction): string =>
  `triggers.actions.${action}`;

export interface ActionAvailability {
  action: TriggerAction;
  /** Absent when the action is allowed. */
  blockedReason?: TriggerReason;
}

/**
 * The actions to render, in the server's display order: allowed ones enabled,
 * blocked ones disabled with their reason. An action in neither collection
 * does not apply to this trigger and is left out.
 */
export const actionsOf = (
  trigger: Pick<TriggerRead, "allowed_actions" | "blocked_actions">,
  only?: readonly TriggerAction[],
): ActionAvailability[] => {
  const allowed = trigger.allowed_actions ?? [];
  const blocked = trigger.blocked_actions ?? {};
  const order: TriggerAction[] = [
    ...allowed,
    ...(Object.keys(blocked) as TriggerAction[]).filter(
      (action) => !allowed.includes(action),
    ),
  ];
  return order
    .filter((action) => !only || only.includes(action))
    .map((action) =>
      allowed.includes(action)
        ? { action }
        : { action, blockedReason: blocked[action] },
    );
};

export const availabilityOf = (
  trigger: Pick<TriggerRead, "allowed_actions" | "blocked_actions">,
  action: TriggerAction,
): ActionAvailability | undefined =>
  actionsOf(trigger).find((entry) => entry.action === action);

/**
 * The one fix offered inline beside the badge: reconnect when the connection
 * is the problem, resume when the trigger is merely stopped. Only an allowed
 * action is offered.
 */
export const inlineFixOf = (
  trigger: Pick<TriggerRead, "allowed_actions">,
): "reconnect" | "resume" | null => {
  const allowed = trigger.allowed_actions ?? [];
  if (allowed.includes("reconnect")) return "reconnect";
  if (allowed.includes("resume")) return "resume";
  return null;
};

/**
 * Mechanisms a provider pushes to Langflow's ingress. Mirrors
 * `PUSH_MECHANISMS` in `services/triggers/constants.py`; everything else a
 * trigger runs is a listener (socket) or a poll.
 */
const PUSH_MECHANISMS = new Set([
  "slack.events_api",
  "microsoft.graph_change_notifications",
  "google.calendar_push",
  "google.drive_push",
  "google.gmail_watch_pubsub_push",
  "github.repository_webhook",
  "gitlab.project_webhook",
  "whatsapp.webhook",
  "telegram.webhook",
]);
const SOCKET_MECHANISMS = new Set(["slack.socket_mode", "discord.gateway"]);

export type TriggerTransport =
  | "push"
  | "socket"
  | "poll"
  | "schedule"
  | "request";

export const transportOf = (
  trigger: Pick<TriggerRead, "kind" | "config">,
): TriggerTransport => {
  if (trigger.kind === "schedule") return "schedule";
  if (trigger.kind === "inbound_webhook") return "request";
  const mechanism = trigger.config?.mechanism_id;
  if (typeof mechanism === "string") {
    if (PUSH_MECHANISMS.has(mechanism)) return "push";
    if (SOCKET_MECHANISMS.has(mechanism)) return "socket";
  }
  return "poll";
};

/** Core triggers have no provider; the kind names their source. */
export const sourceKeyOf = (
  trigger: Pick<TriggerRead, "kind" | "provider">,
): string =>
  trigger.provider
    ? `triggers.provider.${trigger.provider}`
    : `triggers.kind.${trigger.kind === "inbound_webhook" ? "webhook" : trigger.kind}`;

export const sourceIconOf = (
  trigger: Pick<TriggerRead, "kind" | "provider">,
): string => {
  switch (trigger.provider) {
    case "slack":
      return "Slack";
    case "google":
      return "Google";
    case "microsoft":
      return "Microsoft";
    case "github":
      return "Github";
    case "gitlab":
      return "Gitlab";
    case "whatsapp":
    case "discord":
      return "MessageCircle";
    case "telegram":
      return "Send";
    case "salesforce":
      return "Cloud";
    case "servicenow":
      return "Server";
    case "jira":
      return "Ticket";
    case "confluence":
      return "BookOpen";
    default:
      return trigger.kind === "inbound_webhook" ? "Webhook" : "Clock";
  }
};

/** "Needs attention" groups every state the owner has to act on. */
export const needsAttention = (
  trigger: Pick<TriggerRead, "state"> & Partial<Pick<TriggerRead, "reason">>,
): boolean =>
  (trigger.state === "pending" && trigger.reason === "config_invalid") ||
  trigger.state === "needs_reconnect" ||
  trigger.state === "error" ||
  trigger.state === "dead" ||
  trigger.state === "expired";

/** Backend timestamps are naive UTC; read them as such. */
export const parseServerTime = (
  iso: string | null | undefined,
): number | null => {
  if (!iso) return null;
  const time = Date.parse(
    /(?:[zZ]|[+-]\d\d:\d\d)$/.test(iso) ? iso : `${iso}Z`,
  );
  return Number.isNaN(time) ? null : time;
};

export type TriggerEventOrigin = "test" | "replay" | "event";

/** Dedupe-key prefixes name an event's origin; replays also carry a parent. */
export const eventOriginOf = (
  event: Pick<TriggerEventRead, "dedupe_key" | "replay_of_event_id">,
): TriggerEventOrigin => {
  if (event.replay_of_event_id || event.dedupe_key.startsWith("replay:"))
    return "replay";
  if (event.dedupe_key.startsWith("test:")) return "test";
  return "event";
};

/** claimed and dispatched are both in flight; the UI calls it Running. */
export type TriggerEventDisplayState =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "dead";

export const eventDisplayStateOf = (
  event: Pick<TriggerEventRead, "state">,
): TriggerEventDisplayState => {
  switch (event.state) {
    case "pending":
      return "queued";
    case "claimed":
    case "dispatched":
      return "running";
    default:
      return event.state;
  }
};

/**
 * Event error codes are machine strings (`job_failed`, `owner_inactive`,
 * `submit_failed:TimeoutError`). Map the known ones to the catalog and keep
 * the raw code beside it for support.
 */
const KNOWN_EVENT_ERRORS = new Set([
  "owner_inactive",
  "connection_not_authorized",
  "lease_expired",
]);

export const eventErrorKeyOf = (error: string | null): string | null => {
  if (!error) return null;
  if (KNOWN_EVENT_ERRORS.has(error)) return `triggers.eventError.${error}`;
  if (error.startsWith("job_")) return "triggers.eventError.job";
  if (error.startsWith("submit_failed")) return "triggers.eventError.submit";
  return "triggers.eventError.other";
};
