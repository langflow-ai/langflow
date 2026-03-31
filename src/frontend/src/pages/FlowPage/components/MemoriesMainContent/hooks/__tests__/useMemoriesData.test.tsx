import { act, renderHook } from "@testing-library/react";
import { useMemoriesData } from "../useMemoriesData";

jest.mock("@tanstack/react-query", () => {
  const actual = jest.requireActual("@tanstack/react-query");
  return {
    ...actual,
    useQuery: () => ({ data: [] }),
  };
});

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
  documents: [
    { message_id: "msg1", session_id: "s1", content: "hello", sender: "user" },
  ],
  document_sessions: ["s1"],
  documents_total: 1,
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
      documents: [
        {
          message_id: "msg1",
          session_id: "s1",
          content: "hello",
          sender: "user",
        },
      ],
      document_sessions: ["s1"],
      documents_total: 1,
    };
    memoryQueryIsLoading = false;
    memoryQueryIsError = false;
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

  it("commits search and clears selected session", () => {
    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    act(() => {
      result.current.setSearchQuery("hello");
    });

    act(() => {
      result.current.setSelectedSession("s1");
    });

    act(() => {
      result.current.handleSearch();
    });

    expect(result.current.activeSearch).toBe("hello");
    expect(result.current.selectedSession).toBeNull();
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

  it("groups docs by session and respects selectedSession filter", () => {
    memoryQueryData = {
      ...memoryQueryData,
      documents: [
        { message_id: "a", session_id: "s1", content: "hello", sender: "user" },
        {
          message_id: "b",
          session_id: "s2",
          content: "world",
          sender: "assistant",
        },
      ],
      document_sessions: ["s1", "s2"],
    };

    const { result } = renderHook(() =>
      useMemoriesData({
        currentFlowId: "flow-1",
        selectedMemoryId: "m1",
        onSelectMemory: jest.fn(),
      }),
    );

    expect(Array.from(result.current.groupedBySession.keys())).toEqual(["s1", "s2"]);

    act(() => {
      result.current.setSelectedSession("s2");
    });

    expect(Array.from(result.current.groupedBySession.keys())).toEqual(["s2"]);
  });
});
