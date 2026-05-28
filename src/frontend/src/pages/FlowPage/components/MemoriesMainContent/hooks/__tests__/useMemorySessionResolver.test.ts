import { act, renderHook } from "@testing-library/react";
import { useMemorySessionResolver } from "../useMemorySessionResolver";

const mockFetchNextPage = jest.fn();
const mockRefetch = jest.fn();

// biome-ignore lint/suspicious/noExplicitAny: legacy
let mockSessionPages: any[] = [
  {
    items: [
      {
        session_id: "s1",
        last_sync_at: "2026-04-02T00:00:00.000Z",
        total_processed: 5,
        pending_count: 0,
      },
      {
        session_id: "s2",
        last_sync_at: "2026-03-01T00:00:00.000Z",
        total_processed: 2,
        pending_count: 1,
      },
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
          {
            session_id: "s1",
            last_sync_at: "2026-04-02T00:00:00.000Z",
            total_processed: 5,
            pending_count: 0,
          },
          {
            session_id: "s2",
            last_sync_at: "2026-03-01T00:00:00.000Z",
            total_processed: 2,
            pending_count: 1,
          },
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
        items: [
          {
            session_id: "s1",
            last_sync_at: "2026-04-02",
            total_processed: 0,
            pending_count: 0,
          },
        ],
      },
      {
        items: [
          {
            session_id: "s2",
            last_sync_at: "2026-03-01",
            total_processed: 0,
            pending_count: 0,
          },
        ],
      },
    ];

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

  it("sets effectiveSessionId to the most recently synced session by default", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    expect(result.current.effectiveSessionId).toBe("s1");
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

  it("falls back to default session when selectedSession is not in the list", () => {
    const { result } = renderHook(() =>
      useMemorySessionResolver({ memoryId: "m1" }),
    );

    act(() => {
      result.current.setSelectedSession("nonexistent");
    });

    expect(result.current.effectiveSessionId).toBe("s1");
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
});
