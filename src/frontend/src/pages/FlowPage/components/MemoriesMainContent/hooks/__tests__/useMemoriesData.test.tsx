import { act, renderHook } from "@testing-library/react";
import type {
  MemoryDocumentItem,
  MemoryInfo,
  MemorySessionInfo,
} from "@/controllers/API/queries/memories/types";
import type {
  GetMemorySessionMessagesParams,
  MemorySessionMessageApiItem,
} from "@/controllers/API/queries/memories/use-get-memory-session-messages";
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
// Fixture factories — provide required-field defaults so tests only specify
// the fields they actually exercise.
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
// Mutable fixture state (reset in beforeEach; mutated in individual tests)
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

// Override to simulate multiple pages; undefined means use the default single-page shape.
let memoriesPages: MemoriesPageFixture[] | undefined;

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

jest.mock("@/controllers/API/queries/memories/use-get-memory-sessions", () => ({
  useGetMemorySessions: () => ({
    data: memorySessionsData,
    isLoading: false,
    isError: false,
    refetch: jest.fn(),
  }),
}));

let messagesBySession: Record<string, MemorySessionMessageApiItem[]> = {
  s1: [
    {
      timestamp: "2026-04-01T19:29:07",
      sender: "User",
      sender_name: "User",
      ingestion_job_id: "job-1",
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
      ingestion_job_id: "job-2",
      ingestion_timestamp: "2026-04-02T20:51:06.951803",
      session_id: "s2",
      text: "Hi.",
      content_blocks: [],
    },
  ],
};

jest.mock(
  "@/controllers/API/queries/memories/use-get-memory-session-messages",
  () => ({
    useGetMemorySessionMessages: (params: GetMemorySessionMessagesParams) => {
      const { sessionId } = params;
      const items = sessionId ? (messagesBySession[sessionId] ?? []) : [];
      return {
        data: {
          pages: [{ items, total: items.length, page: 1, size: 50, pages: 1 }],
          pageParams: [1],
        },
        isLoading: false,
        fetchNextPage: jest.fn(),
        hasNextPage: false,
        isFetchingNextPage: false,
      };
    },
  }),
);

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
          ingestion_job_id: "job-1",
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
          ingestion_job_id: "job-2",
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

    expect(Array.from(result.current.groupedBySession.keys())).toEqual(["s1"]);

    act(() => {
      result.current.setSelectedSession("s2");
    });

    expect(Array.from(result.current.groupedBySession.keys())).toEqual(["s2"]);
  });

  // --- adversarial ---

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

    // effectiveSessionId must resolve to one of the real sessions, never the ghost
    const keys = Array.from(result.current.groupedBySession.keys());
    expect(keys).not.toContain("ghost-session-xyz");
    expect(result.current.groupedBySession.size).toBeGreaterThan(0);
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
    expect(result.current.memories.map((m) => m.id)).toEqual(["m1", "m2"]);
  });
});
