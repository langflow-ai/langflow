import { act, renderHook } from "@testing-library/react";
import { useMemoriesData } from "../useMemoriesData";

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setErrorData: mockSetErrorData,
    setSuccessData: mockSetSuccessData,
  }),
}));

let memories = [
  {
    id: "m1",
    name: "First",
    description: "alpha",
    status: "idle",
    is_active: true,
  },
  {
    id: "m2",
    name: "Second",
    description: "beta",
    status: "idle",
    is_active: false,
  },
] as any;

jest.mock("@/controllers/API/queries/memories/use-get-memories", () => ({
  useGetMemories: () => ({
    data: {
      pages: [
        {
          items: memories,
          total: memories.length,
          page: 1,
          size: 50,
          pages: 1,
        },
      ],
      pageParams: [1],
    },
    fetchNextPage: jest.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
  }),
}));

let memoryQueryData: any = {
  id: "m1",
  status: "idle",
  is_active: true,
};
let memoryQueryIsLoading = false;
let memoryQueryIsError = false;

jest.mock("@/controllers/API/queries/memories/use-get-memory", () => ({
  useGetMemory: () => ({
    data: memoryQueryData,
    isLoading: memoryQueryIsLoading,
    isError: memoryQueryIsError,
  }),
}));

let memorySessionsData: any[] = [
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

let messagesBySession: Record<string, any[]> = {
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
    useGetMemorySessionMessages: (params: any) => {
      const sessionId = params?.sessionId;
      const items = sessionId ? (messagesBySession[sessionId] ?? []) : [];
      return {
        data: {
          pages: [
            {
              items,
              total: items.length,
              page: 1,
              size: 50,
              pages: 1,
            },
          ],
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

const manualUpdateMutation = { mutate: jest.fn(), isPending: false };
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
    memories = [
      {
        id: "m1",
        name: "First",
        description: "alpha",
        status: "idle",
        is_active: true,
      },
      {
        id: "m2",
        name: "Second",
        description: "beta",
        status: "idle",
        is_active: false,
      },
    ] as any;
    memoryQueryData = {
      id: "m1",
      status: "idle",
      is_active: true,
    };
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
      result.current.handleOpenDocumentPanel({ message_id: "msg1" } as any);
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

    expect(updateMemoryMutation.mutate).toHaveBeenCalledWith({
      memoryId: "m1",
      auto_capture: false,
    });

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
});
