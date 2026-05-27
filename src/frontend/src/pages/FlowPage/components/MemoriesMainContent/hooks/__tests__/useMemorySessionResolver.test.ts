import { act, renderHook } from "@testing-library/react";
import type { MemorySessionInfo } from "@/controllers/API/queries/memories/types";
import {
  ALL_SESSIONS_VALUE,
  useMemorySessionResolver,
} from "../useMemorySessionResolver";

type SessionPage = {
  items: MemorySessionInfo[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

function makeSession(
  overrides: Pick<MemorySessionInfo, "session_id"> &
    Partial<Omit<MemorySessionInfo, "session_id">>,
): MemorySessionInfo {
  return {
    id: overrides.session_id,
    cursor_id: null,
    memory_base_id: "m1",
    last_sync_at: null,
    total_processed: 0,
    pending_count: 0,
    ...overrides,
  };
}

const mockFetchNextPage = jest.fn();
const mockRefetch = jest.fn();

let mockSessionPages: SessionPage[] = [
  {
    items: [
      makeSession({
        session_id: "s1",
        last_sync_at: "2026-04-02T00:00:00.000Z",
        total_processed: 5,
        pending_count: 0,
      }),
      makeSession({
        session_id: "s2",
        last_sync_at: "2026-03-01T00:00:00.000Z",
        total_processed: 2,
        pending_count: 1,
      }),
    ],
    total: 2,
    page: 1,
    size: 50,
    pages: 1,
  },
];
let mockHasNextPage = false;
let mockIsFetchingNextPage = false;

jest.mock("@/controllers/API/queries/memories/use-get-memory-sessions", () => ({
  useGetMemorySessions: () => ({
    data: { pages: mockSessionPages, pageParams: [1] },
    refetch: mockRefetch,
    fetchNextPage: mockFetchNextPage,
    hasNextPage: mockHasNextPage,
    isFetchingNextPage: mockIsFetchingNextPage,
  }),
}));

describe("useMemorySessionResolver", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockHasNextPage = false;
    mockIsFetchingNextPage = false;
    mockSessionPages = [
      {
        items: [
          makeSession({
            session_id: "s1",
            last_sync_at: "2026-04-02T00:00:00.000Z",
            total_processed: 5,
            pending_count: 0,
          }),
          makeSession({
            session_id: "s2",
            last_sync_at: "2026-03-01T00:00:00.000Z",
            total_processed: 2,
            pending_count: 1,
          }),
        ],
        total: 2,
        page: 1,
        size: 50,
        pages: 1,
      },
    ];
  });

  it("flattens all pages into a single memorySessions array", () => {
    mockSessionPages = [
      {
        items: [makeSession({ session_id: "s1", last_sync_at: "2026-04-02" })],
      },
      {
        items: [makeSession({ session_id: "s2", last_sync_at: "2026-03-01" })],
      },
    ] as SessionPage[];

    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.memorySessions).toHaveLength(2);
    expect(result.current.memorySessions[0].session_id).toBe("s1");
    expect(result.current.memorySessions[1].session_id).toBe("s2");
  });

  it("returns empty memorySessions when pages are empty", () => {
    mockSessionPages = [];

    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.memorySessions).toEqual([]);
  });

  it("exposes fetchNextSessionsPage from the query", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.fetchNextSessionsPage).toBe(mockFetchNextPage);
  });

  it("exposes hasNextSessionsPage from the query", () => {
    mockHasNextPage = true;

    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.hasNextSessionsPage).toBe(true);
  });

  it("exposes isFetchingNextSessionsPage from the query", () => {
    mockIsFetchingNextPage = true;

    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.isFetchingNextSessionsPage).toBe(true);
  });

  it("exposes refetchMemorySessions from the query", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.refetchMemorySessions).toBe(mockRefetch);
  });

  it("defaults effectiveSessionId to null (all sessions) when sessions load", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.effectiveSessionId).toBeNull();
    expect(result.current.selectedSession).toBe(ALL_SESSIONS_VALUE);
  });

  it("respects selectedSession when it exists in memorySessions", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    act(() => {
      result.current.setSelectedSession("s2");
    });

    expect(result.current.effectiveSessionId).toBe("s2");
    expect(result.current.selectedSession).toBe("s2");
  });

  it("falls back to null (all sessions) when selectedSession is not in the list", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    act(() => {
      result.current.setSelectedSession("nonexistent");
    });

    expect(result.current.effectiveSessionId).toBeNull();
  });

  it("resets selectedSession when memoryId changes", () => {
    const { result, rerender } = renderHook(
      ({ memoryId }) => useMemorySessionResolver({ memoryId }),
      { initialProps: { memoryId: "m1" } },
    );

    act(() => {
      result.current.setSelectedSession("s2");
    });
    expect(result.current.selectedSession).toBe("s2");

    // Return empty pages for the new memory so the auto-select effect doesn't fire
    mockSessionPages = [];
    rerender({ memoryId: "m2" });

    expect(result.current.selectedSession).toBeNull();
  });

  describe("ALL_SESSIONS_VALUE sentinel", () => {
    it("exports ALL_SESSIONS_VALUE as '__all__'", () => {
      expect(ALL_SESSIONS_VALUE).toBe("__all__");
    });

    it("returns null effectiveSessionId when ALL_SESSIONS_VALUE is selected", () => {
      const { result } = renderHook(() =>
        useMemorySessionResolver({ memoryId: "m1" }),
      );

      act(() => {
        result.current.setSelectedSession(ALL_SESSIONS_VALUE);
      });

      expect(result.current.effectiveSessionId).toBeNull();
    });

    it("keeps selectedSession as ALL_SESSIONS_VALUE after memorySessions update", () => {
      const { result, rerender } = renderHook(() =>
        useMemorySessionResolver({ memoryId: "m1" }),
      );

      act(() => {
        result.current.setSelectedSession(ALL_SESSIONS_VALUE);
      });
      expect(result.current.selectedSession).toBe(ALL_SESSIONS_VALUE);

      // Simulate sessions data changing (new session arrives)
      mockSessionPages = [
        {
          items: [
            makeSession({
              session_id: "s1",
              last_sync_at: "2026-04-02T00:00:00.000Z",
              total_processed: 5,
            }),
            makeSession({
              session_id: "s3",
              last_sync_at: "2026-05-01T00:00:00.000Z",
              total_processed: 1,
            }),
          ],
          total: 2,
          page: 1,
          size: 50,
          pages: 1,
        },
      ];
      rerender();

      expect(result.current.selectedSession).toBe(ALL_SESSIONS_VALUE);
      expect(result.current.effectiveSessionId).toBeNull();
    });

    it("does not treat ALL_SESSIONS_VALUE as a valid real session in effectiveSessionId fallback", () => {
      mockSessionPages = [
        {
          items: [
            makeSession({
              session_id: ALL_SESSIONS_VALUE,
              last_sync_at: "2026-04-02T00:00:00.000Z",
              total_processed: 5,
            }),
          ],
          total: 1,
          page: 1,
          size: 50,
          pages: 1,
        },
      ];

      const { result } = renderHook(() =>
        useMemorySessionResolver({ memoryId: "m1" }),
      );

      act(() => {
        result.current.setSelectedSession(ALL_SESSIONS_VALUE);
      });

      // Should still return null, not treat it as a real session match
      expect(result.current.effectiveSessionId).toBeNull();
    });

    it("allows switching from ALL_SESSIONS_VALUE back to a specific session", () => {
      const { result } = renderHook(() =>
        useMemorySessionResolver({ memoryId: "m1" }),
      );

      act(() => {
        result.current.setSelectedSession(ALL_SESSIONS_VALUE);
      });
      expect(result.current.effectiveSessionId).toBeNull();

      act(() => {
        result.current.setSelectedSession("s2");
      });
      expect(result.current.effectiveSessionId).toBe("s2");
      expect(result.current.selectedSession).toBe("s2");
    });

    it("resets ALL_SESSIONS_VALUE to null when memoryId changes", () => {
      const { result, rerender } = renderHook(
        ({ memoryId }) => useMemorySessionResolver({ memoryId }),
        { initialProps: { memoryId: "m1" } },
      );

      act(() => {
        result.current.setSelectedSession(ALL_SESSIONS_VALUE);
      });
      expect(result.current.selectedSession).toBe(ALL_SESSIONS_VALUE);

      mockSessionPages = [];
      rerender({ memoryId: "m2" });

      expect(result.current.selectedSession).toBeNull();
    });
  });
});
