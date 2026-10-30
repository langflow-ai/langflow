import {
  eventSummaryOf,
  isEventRunning,
  lineageOf,
  matchesEventFilter,
  openRunBlockedKeyOf,
} from "../eventsDrawer/event-helpers";
import { filterTriggers, providersOf } from "../helpers/filter-triggers";
import { formatRelativeTime } from "../helpers/format-relative-time";
import { isTriggerEnabled } from "../helpers/trigger-enabled";
import { makeEvent, makeTrigger } from "./fixtures";

describe("filterTriggers", () => {
  const triggers = [
    makeTrigger({ id: "a", flow_name: "Café digest", state: "active" }),
    makeTrigger({
      id: "b",
      flow_name: "Inbox",
      state: "needs_reconnect",
      provider: "microsoft",
    }),
    makeTrigger({
      id: "c",
      flow_name: "Old",
      state: "dead",
      provider: null,
      kind: "schedule",
    }),
    makeTrigger({
      id: "d",
      flow_name: "Idle",
      state: "paused",
      owner_username: "priya",
    }),
  ];
  const ids = (rows: { id: string }[]) => rows.map((row) => row.id);

  it("matches search without regard to case or accents", () => {
    expect(
      ids(filterTriggers(triggers, { search: "CAFE", state: "all" })),
    ).toEqual(["a"]);
  });

  it("matches the owner in the operator view", () => {
    expect(
      ids(filterTriggers(triggers, { search: "priya", state: "all" })),
    ).toEqual(["d"]);
  });

  it("treats regex metacharacters in search as plain text", () => {
    expect(filterTriggers(triggers, { search: ".*(", state: "all" })).toEqual(
      [],
    );
  });

  it("groups dead with error under the Error filter", () => {
    expect(
      ids(filterTriggers(triggers, { search: "", state: "error" })),
    ).toEqual(["c"]);
  });

  it("collects every state the owner must act on under needs attention", () => {
    expect(
      ids(filterTriggers(triggers, { search: "", state: "attention" })),
    ).toEqual(["b", "c"]);
  });

  it("filters by provider", () => {
    expect(
      ids(
        filterTriggers(triggers, {
          search: "",
          state: "all",
          provider: "microsoft",
        }),
      ),
    ).toEqual(["b"]);
  });

  it("lists distinct providers, skipping core triggers", () => {
    expect(providersOf(triggers)).toEqual(["microsoft", "slack"]);
  });
});

describe("matchesEventFilter", () => {
  it("counts dead-lettered events as failed", () => {
    expect(matchesEventFilter(makeEvent({ state: "dead" }), "failed")).toBe(
      true,
    );
    expect(
      matchesEventFilter(makeEvent({ state: "completed" }), "failed"),
    ).toBe(false);
  });

  it("separates replays from tests", () => {
    const replay = makeEvent({ replay_of_event_id: "evt-0" });
    const test = makeEvent({ dedupe_key: "test:1" });
    expect(matchesEventFilter(replay, "replays")).toBe(true);
    expect(matchesEventFilter(replay, "tests")).toBe(false);
    expect(matchesEventFilter(test, "tests")).toBe(true);
  });
});

describe("lineageOf", () => {
  const original = makeEvent({ id: "o", state: "failed" });
  const replay = makeEvent({ id: "r", replay_of_event_id: "o" });

  it("links a replay to its parent and the parent to its replays", () => {
    expect(lineageOf(replay, [original, replay]).parent).toBe(original);
    expect(lineageOf(original, [original, replay]).replays).toEqual([replay]);
  });

  it("reports a parent outside the loaded page as missing", () => {
    expect(lineageOf(replay, [replay]).parent).toBeUndefined();
  });
});

describe("eventSummaryOf", () => {
  it("reads the payload's text and collapses whitespace", () => {
    expect(eventSummaryOf(makeEvent({ payload: { text: "  a\n\nb  " } }))).toBe(
      "a b",
    );
  });

  it("truncates a long line", () => {
    const summary = eventSummaryOf(
      makeEvent({ payload: { text: "x".repeat(200) } }),
    );
    expect(summary).toHaveLength(80);
    expect(summary?.endsWith("…")).toBe(true);
  });

  it("returns null for a payload without text fields or with non-string ones", () => {
    expect(eventSummaryOf(makeEvent({ payload: {} }))).toBeNull();
    expect(
      eventSummaryOf(makeEvent({ payload: { text: { nested: true } } })),
    ).toBeNull();
  });
});

describe("isTriggerEnabled", () => {
  it("is on for armed states", () => {
    expect(isTriggerEnabled({ state: "active" }, false)).toBe(true);
    expect(isTriggerEnabled({ state: "needs_reconnect" }, false)).toBe(true);
  });

  it("is off for a fresh pending trigger and on for one the user just enabled", () => {
    expect(isTriggerEnabled({ state: "pending" }, false)).toBe(false);
    expect(isTriggerEnabled({ state: "pending" }, true)).toBe(true);
  });

  it("is off for paused even when an enable was requested", () => {
    expect(isTriggerEnabled({ state: "paused" }, true)).toBe(false);
  });
});

describe("formatRelativeTime", () => {
  const now = Date.UTC(2026, 9, 15, 12, 0, 0);

  it("picks the largest unit", () => {
    expect(formatRelativeTime(now - 2 * 60 * 1000, "en", now)).toBe(
      "2 minutes ago",
    );
    expect(formatRelativeTime(now - 2 * 24 * 3600 * 1000, "en", now)).toBe(
      "2 days ago",
    );
  });

  it("formats in the requested locale", () => {
    expect(formatRelativeTime(now - 24 * 3600 * 1000, "de", now)).toBe(
      "gestern",
    );
  });
});

describe("isEventRunning", () => {
  it.each([
    ["claimed", true],
    ["dispatched", true],
    ["pending", false],
    ["completed", false],
    ["failed", false],
    ["dead", false],
  ] as const)("%s → %s", (state, running) => {
    expect(isEventRunning(makeEvent({ state }))).toBe(running);
  });
});

describe("openRunBlockedKeyOf", () => {
  it("offers the run once the event has a job", () => {
    expect(openRunBlockedKeyOf(makeEvent({ state: "failed" }))).toBeNull();
  });

  it.each([
    ["pending", "triggers.events.runNotStarted"],
    ["claimed", "triggers.events.runNotStarted"],
    ["failed", "triggers.events.noRunStarted"],
    ["dead", "triggers.events.noRunStarted"],
    ["completed", "triggers.events.noRunStarted"],
  ] as const)("explains a %s event without a run", (state, key) => {
    expect(openRunBlockedKeyOf(makeEvent({ state, job_id: null }))).toBe(key);
  });
});
