import { resolveDefaultSessionId } from "../memorySessionResolverHelpers";

describe("resolveDefaultSessionId", () => {
  it("returns null when sessions are empty", () => {
    expect(resolveDefaultSessionId([])).toBeNull();
  });

  it("picks the most recently synced session", () => {
    const sessions = [
      {
        session_id: "s1",
        last_sync_at: "2026-03-01T00:00:00.000Z",
        pending_count: 0,
      },
      {
        session_id: "s2",
        last_sync_at: "2026-04-01T00:00:00.000Z",
        pending_count: 0,
      },
      // biome-ignore lint/suspicious/noExplicitAny: legacy
    ] as any;

    expect(resolveDefaultSessionId(sessions)).toBe("s2");
  });

  it("breaks ties by pending_count then session_id", () => {
    const sameTime = "2026-04-01T00:00:00.000Z";
    const sessions = [
      {
        session_id: "b",
        last_sync_at: sameTime,
        pending_count: 1,
      },
      {
        session_id: "a",
        last_sync_at: sameTime,
        pending_count: 1,
      },
      {
        session_id: "c",
        last_sync_at: sameTime,
        pending_count: 2,
      },
      // biome-ignore lint/suspicious/noExplicitAny: legacy
    ] as any;

    expect(resolveDefaultSessionId(sessions)).toBe("c");
  });
});
