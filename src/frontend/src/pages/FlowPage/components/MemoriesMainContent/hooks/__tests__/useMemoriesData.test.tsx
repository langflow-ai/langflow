import { act, renderHook } from "@testing-library/react";
import type {
  MemoryDocumentItem,
  MemoryInfo,
  MemorySessionInfo,
} from "@/controllers/API/queries/memories/types";
import type {
  GetMemoryMessagesParams,
  MemoryMessageApiItem,
} from "@/controllers/API/queries/memories/use-get-memory-messages";
import { useMemoriesData } from "../useMemoriesData";

// ---------------------------------------------------------------------------
// Local types
// ---------------------------------------------------------------------------

type MemoriesPageFixture = {
  items: MemoryInfo[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

// ---------------------------------------------------------------------------
// Fixture factories
// ---------------------------------------------------------------------------

function makeMemoryInfo(
  overrides: Pick<MemoryInfo, "id" | "name"> &
    Partial<Omit<MemoryInfo, "id" | "name">>,
): MemoryInfo {
  return {
    kb_name: "",
    embedding_model: "",
    embedding_provider: "",
    is_active: true,
    total_messages_processed: 0,
    sessions_count: 0,
    batch_size: 1,
    preprocessing_enabled: false,
    pending_messages_count: 0,
    user_id: "u1",
    flow_id: "flow-1",
    ...overrides,
  };
}

function makeDoc(
  overrides: Pick<MemoryDocumentItem, "message_id"> &
    Partial<Omit<MemoryDocumentItem, "message_id">>,
): MemoryDocumentItem {
  return {
    content: "",
    sender: "",
    session_id: "",
    timestamp: "",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Alert store
// ---------------------------------------------------------------------------

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setErrorData: mockSetErrorData,
    setSuccessData: mockSetSuccessData,
  }),
}));

// ---------------------------------------------------------------------------
// Mutable fixture state (reset in beforeEach)
// ---------------------------------------------------------------------------

let memories: MemoryInfo[] = [
  makeMemoryInfo({ id: "m1", name: "First", description: "alpha" }),
  makeMemoryInfo({
    id: "m2",
    name: "Second",
    description: "beta",
    is_active: false,
  }),
];

// Set in individual tests to simulate multiple pages; undefined = single page.
let memoriesPages: MemoriesPageFixture[] | undefined;

const mockRefetchMemories = jest.fn();
jest.mock("@/controllers/API/queries/memories/use-get-memories", () => ({
  useGetMemories: () => {
    const pages: MemoriesPageFixture[] = memoriesPages ?? [
      { items: memories, total: memories.length, page: 1, size: 50, pages: 1 },
    ];
    return {
      data: { pages, pageParams: pages.map((_, i) => i + 1) },
      fetchNextPage: jest.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      refetch: mockRefetchMemories,
    };
  },
}));

let memoryQueryData: MemoryInfo = makeMemoryInfo({ id: "m1", name: "First" });
let memoryQueryIsLoading = false;
let memoryQueryIsError = false;

jest.mock("@/controllers/API/queries/memories/use-get-memory", () => ({
  useGetMemory: () => ({
    data: memoryQueryData,
    isLoading: memoryQueryIsLoading,
    isError: memoryQueryIsError,
  }),
}));

let memorySessionsData: MemorySessionInfo[] = [
  {
    session_id: "s1",
    cursor_id: null,
    total_processed: 0,
    last_sync_at: "2026-04-01T00:00:00.000Z",
    id: "s1",
    memory_base_id: "m1",
    pending_count: 0,
  },
  {
    session_id: "s2",
    cursor_id: null,
    total_processed: 0,
    last_sync_at: "2026-03-01T00:00:00.000Z",
    id: "s2",
    memory_base_id: "m1",
    pending_count: 0,
  },
];

const mockRefetchSessions = jest.fn();
const mockFetchNextSessionsPage = jest.fn();
jest.mock("@/controllers/API/queries/memories/use-get-memory-sessions", () => ({
  useGetMemorySessions: () => ({
    data: {
      pages: [
        {
          items: memorySessionsData,
          total: memorySessionsData.length,
          page: 1,
          size: 50,
          pages: 1,
        },
      ],
      pageParams: [1],
    },
    refetch: mockRefetchSessions,
    fetchNextPage: mockFetchNextSessionsPage,
    hasNextPage: false,
    isFetchingNextPage: false,
  }),
}));

let messagesBySession: Record<string, MemoryMessageApiItem[]> = {
  s1: [
    {
      timestamp: "2026-04-01T19:29:07",
      sender: "User",
      sender_name: "User",
      job_id: "job-1",
      ingestion_timestamp: "2026-04-02T20:51:06.951803",
      session_id: "s1",
      text: "Hello.",
      content_blocks: [],
    },
  ],
  s2: [
    {
      timestamp: "2026-04-01T19:29:08",
      sender: "Machine",
      sender_name: "AI",
      job_id: "job-2",
      ingestion_timestamp: "2026-04-02T20:51:06.951803",
      session_id: "s2",
      text: "Hi.",
      content_blocks: [],
    },
  ],
};

const mockRefetchMessages = jest.fn();
jest.mock("@/controllers/API/queries/memories/use-get-memory-messages", () => ({
  useGetMemoryMessages: (params: GetMemoryMessagesParams) => {
    const { sessionId } = params;
    const items = sessionId
      ? (messagesBySession[sessionId] ?? [])
      : Object.values(messagesBySession).flat();
    return {
      data: {
        pages: [{ items, total: items.length, page: 1, size: 50, pages: 1 }],
        pageParams: [1],
      },
      isLoading: false,
      fetchNextPage: jest.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      refetch: mockRefetchMessages,
    };
  },
}));

const deleteMutation = { mutate: jest.fn(), isPending: false };
const updateMemoryMutation = { mutate: jest.fn(), isPending: false };
jest.mock("@/controllers/API/queries/memories/use-delete-memory", () => ({
  useDeleteMemory: () => deleteMutation,
}));
jest.mock("@/controllers/API/queries/memories/use-update-memory", () => ({
  useUpdateMemory: () => updateMemoryMutation,
}));

describe("useMemoriesData", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    memoriesPages = undefined;
    memories = [
      makeMemoryInfo({ id: "m1", name: "First", description: "alpha" }),
      makeMemoryInfo({
        id: "m2",
        name: "Second",
        description: "beta",
        is_active: false,
      }),
    ];
    memoryQueryData = makeMemoryInfo({ id: "m1", name: "First" });
    memoryQueryIsLoading = false;
    memoryQueryIsError = false;

    memorySessionsData = [
      {
        session_id: "s1",
        cursor_id: null,
        total_processed: 0,
        last_sync_at: "2026-04-01T00:00:00.000Z",
        id: "s1",
        memory_base_id: "m1",
        pending_count: 0,
      },
      {
        session_id: "s2",
        cursor_id: null,
        total_processed: 0,
        last_sync_at: "2026-03-01T00:00:00.000Z",
        id: "s2",
        memory_base_id: "m1",
        pending_count: 0,
      },
    ];

    messagesBySession = {
      s1: [
        {
          timestamp: "2026-04-01T19:29:07",
          sender: "User",
          sender_name: "User",
          job_id: "job-1",
          ingestion_timestamp: "2026-04-02T20:51:06.951803",
          session_id: "s1",
          text: "Hello.",
          content_blocks: [],
        },
      ],
      s2: [
        {
          timestamp: "2026-04-01T19:29:08",
          sender: "Machine",
          sender_name: "AI",
          job_id: "job-2",
          ingestion_timestamp: "2026-04-02T20:51:06.951803",
          session_id: "s2",
          text: "Hi.",
          content_blocks: [],
        },
      ],
    };
  });

  it("auto-selects first memory when no selection", () => {
    const onSelectMemory = jest.fn();

    renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: null,
        onSelectMemory,
      }),
    );

    expect(onSelectMemory).toHaveBeenCalledWith("m1");
  });

  it("filters memories by search query", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.setMemoriesSearch("second");
    });

    expect(result.current.filteredMemories).toHaveLength(1);
    expect(result.current.filteredMemories[0].id).toBe("m2");
  });

  it("opens document panel for selected document", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.handleOpenDocumentPanel(makeDoc({ message_id: "msg1" }));
    });

    expect(result.current.documentPanelOpen).toBe(true);
    expect(result.current.selectedDocument?.message_id).toBe("msg1");
  });

  it("toggles active state through update mutation", () => {
    jest.useFakeTimers();
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
    });

    expect(updateMemoryMutation.mutate).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(updateMemoryMutation.mutate).toHaveBeenCalledWith(
      { memoryId: "m1", auto_capture: false },
      expect.any(Object),
    );

    jest.useRealTimers();
  });

  it("does not call update when toggled back within debounce", () => {
    jest.useFakeTimers();
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.handleToggleActive(false);
      result.current.handleToggleActive(true);
    });

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(updateMemoryMutation.mutate).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it("clears selected memory when selected memory fetch errors", () => {
    memoryQueryIsError = true;
    const onSelectMemory = jest.fn();

    renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory,
      }),
    );

    expect(onSelectMemory).toHaveBeenCalledWith(null);
  });

  it("shows messages for the default session and switches when selectedSession changes", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    expect(Array.from(result.current.groupedBySession.keys())).toEqual([
      "s1",
      "s2",
    ]);

    act(() => {
      result.current.setSelectedSession("s2");
    });

    expect(Array.from(result.current.groupedBySession.keys())).toEqual(["s2"]);
  });

  it("deselects stale memory when the list comes back empty", () => {
    memories = [];
    const onSelectMemory = jest.fn();

    renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory,
      }),
    );

    expect(onSelectMemory).toHaveBeenCalledWith(null);
  });

  it("clears document panel when selected memory switches", () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | null }) =>
        useMemoriesData({
          currentFlowId: "flow-1",
          selectedMemoryId: id,
          onSelectMemory: jest.fn(),
        }),
      { initialProps: { id: "m1" as string | null } },
    );

    act(() => {
      result.current.handleOpenDocumentPanel(makeDoc({ message_id: "doc-1" }));
    });
    expect(result.current.documentPanelOpen).toBe(true);
    expect(result.current.selectedDocument?.message_id).toBe("doc-1");

    rerender({ id: "m2" });

    expect(result.current.documentPanelOpen).toBe(false);
    expect(result.current.selectedDocument).toBeNull();
  });

  it("falls back to a valid session when setSelectedSession receives an unknown ID", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.setSelectedSession("ghost-session-xyz");
    });

    const keys = Array.from(result.current.groupedBySession.keys());
    expect(keys).not.toContain("ghost-session-xyz");
    expect(result.current.groupedBySession.size).toBeGreaterThan(0);
  });

  it("exposes onRefresh as a function", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    expect(typeof result.current.onRefresh).toBe("function");
  });

  it("onRefresh calls refetchMemories, refetchMemorySessions and refetchMessages", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.onRefresh();
    });

    expect(mockRefetchMemories).toHaveBeenCalledTimes(1);
    expect(mockRefetchSessions).toHaveBeenCalled();
    expect(mockRefetchMessages).toHaveBeenCalledTimes(1);
  });

  it("flattens memories across multiple API pages into a single array", () => {
    memoriesPages = [
      {
        items: [makeMemoryInfo({ id: "m1", name: "First" })],
        total: 2,
        page: 1,
        size: 1,
        pages: 2,
      },
      {
        items: [makeMemoryInfo({ id: "m2", name: "Second", is_active: false })],
        total: 2,
        page: 2,
        size: 1,
        pages: 2,
      },
    ];

    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    expect(result.current.memories).toHaveLength(2);
    expect(result.current.memories[0].id).toBe("m1");
    expect(result.current.memories[1].id).toBe("m2");
  });

  it("exposes fetchNextSessionsPage, hasNextSessionsPage and isFetchingNextSessionsPage", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    expect(result.current.fetchNextSessionsPage).toBe(
      mockFetchNextSessionsPage,
    );
    expect(result.current.hasNextSessionsPage).toBe(false);
    expect(result.current.isFetchingNextSessionsPage).toBe(false);
  });
});
