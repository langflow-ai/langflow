import {
  actionsOf,
  availabilityOf,
  badgeStateOf,
  eventDisplayStateOf,
  eventErrorKeyOf,
  eventOriginOf,
  inlineFixOf,
  needsAttention,
  parseServerTime,
  reasonKey,
  sourceIconOf,
  sourceKeyOf,
  transportOf,
} from "../helpers/trigger-presentation";
import { makeEvent, makeTrigger } from "./fixtures";

describe("badgeStateOf", () => {
  it("distinguishes blocked configuration from setup in progress", () => {
    expect(badgeStateOf("pending", "config_invalid")).toBe("blocked");
    expect(badgeStateOf("pending", "pending")).toBe("pending");
  });
  it("renders dead with the error treatment, never as a seventh badge", () => {
    expect(badgeStateOf("dead")).toBe("error");
  });

  it.each([
    "pending",
    "active",
    "paused",
    "expired",
    "needs_reconnect",
    "error",
  ] as const)("keeps %s as its own badge", (state) => {
    expect(badgeStateOf(state)).toBe(state);
  });
});

describe("actionsOf", () => {
  it("lists allowed actions in server order, then blocked ones with their reason", () => {
    const trigger = makeTrigger({
      allowed_actions: ["pause", "delete"],
      blocked_actions: { test: "pending", reconnect: "reconnect_not_needed" },
    });

    expect(actionsOf(trigger)).toEqual([
      { action: "pause" },
      { action: "delete" },
      { action: "test", blockedReason: "pending" },
      { action: "reconnect", blockedReason: "reconnect_not_needed" },
    ]);
  });

  it("leaves out an action in neither collection, since it does not apply", () => {
    const trigger = makeTrigger({
      allowed_actions: ["pause"],
      blocked_actions: {},
    });

    expect(availabilityOf(trigger, "rotate_secret")).toBeUndefined();
  });

  it("filters to the requested actions", () => {
    const trigger = makeTrigger();

    expect(actionsOf(trigger, ["delete"])).toEqual([{ action: "delete" }]);
  });

  it("tolerates a response that predates the capability fields", () => {
    const trigger = makeTrigger({
      allowed_actions: undefined,
      blocked_actions: undefined,
    });

    expect(actionsOf(trigger)).toEqual([]);
  });

  it("treats an action listed in both collections as allowed", () => {
    const trigger = makeTrigger({
      allowed_actions: ["test"],
      blocked_actions: { test: "pending" },
    });

    expect(actionsOf(trigger, ["test"])).toEqual([{ action: "test" }]);
  });
});

describe("inlineFixOf", () => {
  it("prefers reconnect over resume when both are allowed", () => {
    expect(
      inlineFixOf(makeTrigger({ allowed_actions: ["resume", "reconnect"] })),
    ).toBe("reconnect");
  });

  it("offers resume for a stopped trigger", () => {
    expect(
      inlineFixOf(makeTrigger({ allowed_actions: ["resume", "delete"] })),
    ).toBe("resume");
  });

  it("offers nothing when no fix is allowed", () => {
    expect(
      inlineFixOf(makeTrigger({ allowed_actions: ["delete"] })),
    ).toBeNull();
  });
});

describe("reasonKey", () => {
  it("explains a cleanly running trigger", () => {
    expect(reasonKey({ reason: null })).toBe("triggers.reason.running");
  });

  it("uses the server's reason code", () => {
    expect(reasonKey({ reason: "consent_required" })).toBe(
      "triggers.reason.consent_required",
    );
  });
});

describe("transportOf", () => {
  it.each([
    ["slack.events_api", "push"],
    ["microsoft.graph_change_notifications", "push"],
    ["google.gmail_watch_pubsub_push", "push"],
    ["github.repository_webhook", "push"],
    ["gitlab.project_webhook", "push"],
    ["whatsapp.webhook", "push"],
    ["telegram.webhook", "push"],
    ["discord.gateway", "socket"],
    ["telegram.get_updates", "poll"],
    ["slack.socket_mode", "socket"],
    ["microsoft.graph_delta_poll", "poll"],
  ])("reads %s as %s", (mechanism, transport) => {
    expect(
      transportOf(makeTrigger({ config: { mechanism_id: mechanism } })),
    ).toBe(transport);
  });

  it("names the core kinds by how they fire", () => {
    expect(transportOf(makeTrigger({ kind: "schedule", config: {} }))).toBe(
      "schedule",
    );
    expect(
      transportOf(makeTrigger({ kind: "inbound_webhook", config: {} })),
    ).toBe("request");
  });

  it("falls back to poll for a missing or non-string mechanism", () => {
    expect(transportOf(makeTrigger({ config: {} }))).toBe("poll");
    expect(transportOf(makeTrigger({ config: { mechanism_id: 42 } }))).toBe(
      "poll",
    );
  });
});

describe("sourceKeyOf", () => {
  it.each([
    ["gitlab", "Gitlab"],
    ["whatsapp", "MessageCircle"],
    ["discord", "MessageCircle"],
    ["telegram", "Send"],
    ["salesforce", "Cloud"],
    ["servicenow", "Server"],
    ["jira", "Ticket"],
    ["confluence", "BookOpen"],
  ])("shows the %s provider icon", (provider, icon) => {
    expect(sourceIconOf(makeTrigger({ provider }))).toBe(icon);
  });

  it("names a provider trigger by its provider", () => {
    expect(sourceKeyOf(makeTrigger())).toBe("triggers.provider.slack");
  });

  it("names a core trigger by its kind", () => {
    expect(
      sourceKeyOf(makeTrigger({ provider: null, kind: "inbound_webhook" })),
    ).toBe("triggers.kind.webhook");
    expect(sourceKeyOf(makeTrigger({ provider: null, kind: "schedule" }))).toBe(
      "triggers.kind.schedule",
    );
  });
});

describe("needsAttention", () => {
  it("includes a pending trigger whose configuration needs correction", () => {
    expect(needsAttention({ state: "pending", reason: "config_invalid" })).toBe(
      true,
    );
  });
  it.each(["needs_reconnect", "error", "dead", "expired"] as const)(
    "flags %s",
    (state) => {
      expect(needsAttention({ state })).toBe(true);
    },
  );

  it.each(["active", "pending", "paused"] as const)(
    "does not flag %s",
    (state) => {
      expect(needsAttention({ state })).toBe(false);
    },
  );
});

describe("parseServerTime", () => {
  it("reads a naive backend timestamp as UTC", () => {
    expect(parseServerTime("2026-10-15T10:00:00")).toBe(
      Date.UTC(2026, 9, 15, 10, 0, 0),
    );
  });

  it("keeps an explicit offset", () => {
    expect(parseServerTime("2026-10-15T10:00:00+02:00")).toBe(
      Date.UTC(2026, 9, 15, 8, 0, 0),
    );
  });

  it("returns null for missing or unparseable input", () => {
    expect(parseServerTime(null)).toBeNull();
    expect(parseServerTime("not a date")).toBeNull();
  });
});

describe("eventOriginOf", () => {
  it("reads a replay from its parent link or its key", () => {
    expect(eventOriginOf(makeEvent({ replay_of_event_id: "evt-0" }))).toBe(
      "replay",
    );
    expect(eventOriginOf(makeEvent({ dedupe_key: "replay:abc" }))).toBe(
      "replay",
    );
  });

  it("reads a test from its key", () => {
    expect(eventOriginOf(makeEvent({ dedupe_key: "test:abc" }))).toBe("test");
  });

  it("does not mistake a key that merely contains test", () => {
    expect(eventOriginOf(makeEvent({ dedupe_key: "slack:test:abc" }))).toBe(
      "event",
    );
  });
});

describe("eventDisplayStateOf", () => {
  it("shows both in-flight states as running", () => {
    expect(eventDisplayStateOf({ state: "claimed" })).toBe("running");
    expect(eventDisplayStateOf({ state: "dispatched" })).toBe("running");
  });

  it("shows pending as queued", () => {
    expect(eventDisplayStateOf({ state: "pending" })).toBe("queued");
  });
});

describe("eventErrorKeyOf", () => {
  it.each([
    [null, null],
    ["owner_inactive", "triggers.eventError.owner_inactive"],
    ["job_failed", "triggers.eventError.job"],
    ["job_cancelled", "triggers.eventError.job"],
    ["submit_failed:TimeoutError", "triggers.eventError.submit"],
    ["<script>alert(1)</script>", "triggers.eventError.other"],
  ])("maps %s", (error, key) => {
    expect(eventErrorKeyOf(error)).toBe(key);
  });
});
