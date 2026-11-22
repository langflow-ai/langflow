import { renderHook } from "@testing-library/react";
import type { TriggerSessionRead } from "@/controllers/API/queries/triggers";
import { useSessionLabels } from "../use-session-labels";

let mockOrigins: TriggerSessionRead[] = [];
let mockPlaygroundPage = false;
const mockSessionsQuery = jest.fn();

jest.mock("@/controllers/API/queries/triggers", () => ({
  useTriggerSessionsQuery: (
    flowId: string,
    sessions: string[],
    enabled: boolean,
  ) => {
    mockSessionsQuery(flowId, sessions, enabled);
    return { data: enabled ? mockOrigins : undefined };
  },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ playgroundPage: mockPlaygroundPage }),
}));

const origin = (
  overrides: Partial<TriggerSessionRead>,
): TriggerSessionRead => ({
  session_id: "trigger:t1:e1",
  trigger_id: "t1",
  trigger_name: "Schedule */5 * * * *",
  kind: "schedule",
  provider: null,
  // Midday UTC: the same calendar day in every test runner's time zone.
  started_at: "2026-10-29T12:00:05",
  ...overrides,
});

describe("useSessionLabels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPlaygroundPage = false;
    mockOrigins = [];
  });

  it("names each trigger run by its start time, then its source", () => {
    mockOrigins = [
      origin({ session_id: "trigger:t1:e1" }),
      origin({
        session_id: "trigger:t2:e9",
        trigger_id: "t2",
        kind: "slack.message",
        provider: "slack",
      }),
    ];
    const sessions = ["flow-1", "trigger:t1:e1", "trigger:t2:e9", "my chat"];

    const { result } = renderHook(() => useSessionLabels("flow-1", sessions));

    expect(result.current.get("trigger:t1:e1")).toMatch(
      /^Oct 29, \d{1,2}:\d{2}:05.* · Schedule$/,
    );
    expect(result.current.get("trigger:t2:e9")).toMatch(/^Oct 29, .* · Slack$/);
    expect(result.current.has("my chat")).toBe(false);
    expect(mockSessionsQuery).toHaveBeenCalledWith("flow-1", sessions, true);
  });

  it("labels a shared session as every run of its trigger", () => {
    mockOrigins = [origin({ session_id: "trigger:t1" })];

    const { result } = renderHook(() =>
      useSessionLabels("flow-1", ["trigger:t1"]),
    );

    expect(result.current.get("trigger:t1")).toBe("Schedule · All runs");
  });

  it("does not ask for labels on the shared Playground", () => {
    mockPlaygroundPage = true;

    const { result } = renderHook(() =>
      useSessionLabels("flow-1", ["trigger:t1:e1"]),
    );

    expect(mockSessionsQuery).toHaveBeenCalledWith(
      "flow-1",
      ["trigger:t1:e1"],
      false,
    );
    expect(result.current.size).toBe(0);
  });
});
