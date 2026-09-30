import { renderHook } from "@testing-library/react";
import type {
  GetMemoryMessagesApiResponse,
  MemoryMessageApiItem,
} from "@/controllers/API/queries/memories/use-get-memory-messages";
import { useMemoryDocuments } from "../useMemoryDocuments";

const mockFetchNextPage = jest.fn();
const mockRefetch = jest.fn();

type MessagePageFixture = Partial<GetMemoryMessagesApiResponse> & {
  items: Partial<MemoryMessageApiItem>[];
};

let mockPages: MessagePageFixture[] = [];

jest.mock("@/controllers/API/queries/memories/use-get-memory-messages", () => ({
  useGetMemoryMessages: () => ({
    data: { pages: mockPages, pageParams: [1] },
    isLoading: false,
    fetchNextPage: mockFetchNextPage,
    hasNextPage: false,
    isFetchingNextPage: false,
    refetch: mockRefetch,
  }),
}));

const memorySessions = [
  {
    session_id: "s1",
    total_processed: 1,
    pending_count: 0,
    last_sync_at: "2026-04-01",
    id: "s1",
    memory_base_id: "m1",
    cursor_id: null,
  },
  {
    session_id: "s2",
    total_processed: 2,
    pending_count: 0,
    last_sync_at: "2026-03-01",
    id: "s2",
    memory_base_id: "m1",
    cursor_id: null,
  },
];

describe("useMemoryDocuments", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPages = [
      {
        items: [
          {
            timestamp: "2026-04-01T10:00:00",
            sender: "User",
            job_id: "job-1",
            ingestion_timestamp: "2026-04-01T11:00:00",
            session_id: "s1",
            text: "Hello world",
          },
          {
            timestamp: "2026-04-01T10:01:00",
            sender: "AI",
            job_id: "job-2",
            ingestion_timestamp: "2026-04-01T11:01:00",
            session_id: "s1",
            text: "Hi there",
          },
        ],
        total: 2,
        page: 1,
        size: 50,
        pages: 1,
      },
    ];
  });

  it("exposes refetchMessages from the messages query", () => {
    const { result } = renderHook(() =>
      useMemoryDocuments({ memoryId: "m1", sessionId: "s1", memorySessions }),
    );

    expect(result.current.refetchMessages).toBe(mockRefetch);
  });

  it("flattens all message pages into documents", () => {
    const { result } = renderHook(() =>
      useMemoryDocuments({ memoryId: "m1", sessionId: "s1", memorySessions }),
    );

    expect(result.current.docsData.documents).toHaveLength(2);
  });

  it("filters out messages with no content", () => {
    mockPages = [
      {
        items: [
          { timestamp: "t1", sender: "User", session_id: "s1", text: "Valid" },
          { timestamp: "t2", sender: "AI", session_id: "s1", text: "" },
        ],
      },
    ];

    const { result } = renderHook(() =>
      useMemoryDocuments({ memoryId: "m1", sessionId: "s1", memorySessions }),
    );

    expect(result.current.docsData.documents).toHaveLength(1);
    expect(result.current.docsData.documents![0].content).toBe("Valid");
  });

  it("returns every message from the API without re-filtering by session", () => {
    // Server is now the source of truth for session filtering; the hook
    // must surface whatever the API returned, even when multiple sessions
    // are present in the payload (e.g. when sessionId is null).
    mockPages = [
      {
        items: [
          {
            timestamp: "t1",
            sender: "User",
            session_id: "s1",
            text: "From s1",
          },
          {
            timestamp: "t2",
            sender: "User",
            session_id: "s2",
            text: "From s2",
          },
        ],
      },
    ];

    const { result } = renderHook(() =>
      useMemoryDocuments({ memoryId: "m1", sessionId: null, memorySessions }),
    );

    expect(result.current.docsData.documents).toHaveLength(2);
    const contents = result.current.docsData.documents!.map((d) => d.content);
    expect(contents).toContain("From s1");
    expect(contents).toContain("From s2");
  });

  it("builds the sessions list from memorySessions", () => {
    const { result } = renderHook(() =>
      useMemoryDocuments({ memoryId: "m1", sessionId: "s1", memorySessions }),
    );

    expect(result.current.docsData.sessions).toEqual(["s1", "s2"]);
  });

  it("deduplicates session IDs in the sessions list", () => {
    const dupSessions = [
      ...memorySessions,
      {
        session_id: "s1",
        total_processed: 0,
        pending_count: 0,
        last_sync_at: "",
        id: "s1b",
        memory_base_id: "m1",
        cursor_id: null,
      },
    ];

    const { result } = renderHook(() =>
      useMemoryDocuments({
        memoryId: "m1",
        sessionId: "s1",
        memorySessions: dupSessions,
      }),
    );

    const s1Count = result.current.docsData.sessions!.filter(
      (s) => s === "s1",
    ).length;
    expect(s1Count).toBe(1);
  });
});
