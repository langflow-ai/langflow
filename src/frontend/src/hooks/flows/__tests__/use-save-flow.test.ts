// biome-ignore-all lint/suspicious/noExplicitAny: store mocks intentionally accept multiple selector shapes
import { renderHook } from "@testing-library/react";
import useSaveFlow from "../use-save-flow";

const mockSetFlows = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSaveLoading = jest.fn();
const mockSetCurrentFlow = jest.fn();
const mockGetFlow = jest.fn();
const mockMutate = jest.fn();

let flowStoreState: any;
let flowsManagerState: any;

jest.mock("@/controllers/API/queries/flows/use-get-flow", () => ({
  useGetFlow: () => ({ mutate: mockGetFlow }),
}));

jest.mock("@/controllers/API/queries/flows/use-patch-update-flow", () => ({
  usePatchUpdateFlow: () => ({ mutate: mockMutate }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (selector: any) =>
    selector ? selector(flowStoreState) : flowStoreState;
  useFlowStore.getState = () => flowStoreState;

  return {
    __esModule: true,
    default: useFlowStore,
  };
});

jest.mock("@/stores/flowsManagerStore", () => {
  const useFlowsManagerStore = (selector: any) =>
    selector ? selector(flowsManagerState) : flowsManagerState;
  useFlowsManagerStore.getState = () => flowsManagerState;

  return {
    __esModule: true,
    default: useFlowsManagerStore,
  };
});

describe("useSaveFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    const savedFlow = {
      id: "flow-1",
      name: "Saved Flow",
      data: {
        nodes: [{ id: "old-node" }],
        edges: [{ id: "old-edge" }],
        viewport: { x: 1, y: 2, zoom: 0.5 },
      },
      description: "desc",
      folder_id: "folder-1",
      endpoint_name: "saved-flow",
      locked: false,
    };

    flowStoreState = {
      currentFlow: {
        ...savedFlow,
        data: {
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
      nodes: [],
      edges: [],
      reactFlowInstance: {
        getViewport: jest.fn(() => ({ x: 0, y: 0, zoom: 1 })),
      },
      onFlowPage: true,
      setCurrentFlow: mockSetCurrentFlow,
    };

    flowsManagerState = {
      currentFlow: savedFlow,
      flows: [savedFlow],
      setFlows: mockSetFlows,
      setSaveLoading: mockSetSaveLoading,
    };

    mockMutate.mockImplementation((_payload, options) => {
      options.onSuccess({
        ...flowStoreState.currentFlow,
        data: {
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      });
    });
  });

  it("persists empty-node flows instead of leaving the save promise pending", async () => {
    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current()).resolves.toBeUndefined();

    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "flow-1",
        data: expect.objectContaining({
          nodes: [],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        }),
      }),
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(mockMutate.mock.calls[0][0]).not.toHaveProperty(
      "providerScopeChanged",
    );
    expect(mockSetSaveLoading).toHaveBeenCalledWith(true);
    expect(mockSetSaveLoading).toHaveBeenCalledWith(false);
    expect(mockSetCurrentFlow).toHaveBeenCalled();
  });

  it("reports the backend detail before rejecting a failed save", async () => {
    const error = {
      response: {
        data: {
          detail: "You do not have permission to edit this flow",
        },
      },
    };
    mockMutate.mockImplementation((_payload, options) => {
      options.onError(error);
    });
    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current()).rejects.toBe(error);

    expect(mockSetErrorData).toHaveBeenCalledTimes(1);
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Failed to save flow",
      list: ["You do not have permission to edit this flow"],
    });
    expect(mockSetSaveLoading).toHaveBeenCalledWith(false);
  });

  it("stays silent but still rejects when the caller suppresses the error toast", async () => {
    const error = {
      response: { status: 400, data: { detail: "Name must be unique" } },
    };
    mockMutate.mockImplementation((_payload, options) => {
      options.onError(error);
    });
    const { result } = renderHook(() => useSaveFlow());

    await expect(
      result.current(undefined, { suppressErrorToast: true }),
    ).rejects.toBe(error);

    expect(mockSetErrorData).not.toHaveBeenCalled();
    expect(mockSetSaveLoading).toHaveBeenCalledWith(false);
  });

  it("suppresses the store-inconsistency toast too so the caller never gets two", async () => {
    // A caller that reports the rejection itself would otherwise show a second
    // toast on top of this one.
    flowsManagerState.flows = undefined;
    mockMutate.mockImplementation((_payload, options) => {
      options.onSuccess({ ...flowsManagerState.currentFlow, name: "Renamed" });
    });
    const { result } = renderHook(() => useSaveFlow());

    await expect(
      result.current(undefined, { suppressErrorToast: true }),
    ).rejects.toThrow("Flows variable undefined");

    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("does not autosave hydrated data while the persisted flow is locked", async () => {
    const persistedFlow = {
      ...flowsManagerState.currentFlow,
      locked: true,
    };
    flowsManagerState.currentFlow = persistedFlow;
    flowsManagerState.flows = [persistedFlow];
    flowStoreState.currentFlow = {
      ...persistedFlow,
      data: {
        ...persistedFlow.data,
        nodes: [{ id: "old-node", data: { is_refresh: true } }],
        viewport: { x: 10, y: 20, zoom: 0.75 },
      },
    };

    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current()).resolves.toBeUndefined();

    expect(mockMutate).not.toHaveBeenCalled();
    expect(mockSetSaveLoading).not.toHaveBeenCalled();
  });

  it("unlocks a persisted flow before saving other settings changes", async () => {
    const persistedFlow = {
      ...flowsManagerState.currentFlow,
      locked: true,
    };
    const requestedFlow = {
      ...persistedFlow,
      name: "Renamed after unlock",
      locked: false,
      data: {
        ...persistedFlow.data,
        nodes: [{ id: "old-node", data: { is_refresh: true } }],
      },
    };
    flowsManagerState.currentFlow = persistedFlow;
    flowsManagerState.flows = [persistedFlow];
    flowStoreState.currentFlow = persistedFlow;

    mockMutate.mockImplementation((payload, options) => {
      options.onSuccess({
        ...requestedFlow,
        ...payload,
      });
    });

    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current(requestedFlow)).resolves.toBeUndefined();

    expect(mockMutate).toHaveBeenCalledTimes(2);
    expect(mockMutate.mock.calls[0][0]).toEqual({
      id: "flow-1",
      locked: false,
    });
    expect(mockMutate.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        id: "flow-1",
        name: "Renamed after unlock",
        locked: false,
        data: requestedFlow.data,
      }),
    );
    expect(mockSetSaveLoading).toHaveBeenCalledWith(true);
    expect(mockSetSaveLoading).toHaveBeenCalledWith(false);
    expect(mockSetCurrentFlow).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Renamed after unlock",
        locked: false,
      }),
    );
  });

  it("does not autosave a locked editor flow when the manager snapshot is stale", async () => {
    const staleManagerFlow = {
      ...flowsManagerState.currentFlow,
      locked: false,
    };
    const lockedEditorFlow = {
      ...staleManagerFlow,
      locked: true,
      data: {
        ...staleManagerFlow.data,
        nodes: [{ id: "old-node", data: { is_refresh: true } }],
      },
    };
    flowsManagerState.currentFlow = staleManagerFlow;
    flowsManagerState.flows = [staleManagerFlow];
    flowStoreState.currentFlow = lockedEditorFlow;

    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current()).resolves.toBeUndefined();

    expect(mockMutate).not.toHaveBeenCalled();
    expect(mockSetSaveLoading).not.toHaveBeenCalled();
  });

  it("unlocks a locked editor flow when the manager snapshot is stale", async () => {
    const staleManagerFlow = {
      ...flowsManagerState.currentFlow,
      locked: false,
    };
    const lockedEditorFlow = {
      ...staleManagerFlow,
      locked: true,
    };
    const requestedFlow = {
      ...lockedEditorFlow,
      locked: false,
      data: {
        ...lockedEditorFlow.data,
        nodes: [{ id: "old-node", data: { is_refresh: true } }],
      },
    };
    flowsManagerState.currentFlow = staleManagerFlow;
    flowsManagerState.flows = [staleManagerFlow];
    flowStoreState.currentFlow = lockedEditorFlow;

    mockMutate.mockImplementation((payload, options) => {
      options.onSuccess({
        ...requestedFlow,
        ...payload,
      });
    });

    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current(requestedFlow)).resolves.toBeUndefined();

    expect(mockMutate).toHaveBeenCalledTimes(2);
    expect(mockMutate.mock.calls[0][0]).toEqual({
      id: "flow-1",
      locked: false,
    });
    expect(mockMutate.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        id: "flow-1",
        locked: false,
        data: requestedFlow.data,
      }),
    );
  });

  it("should_update_store_flow_folder_id_when_moved_via_drag_drop_from_dashboard", async () => {
    // Arrange — dashboard scenario: no flow open in the editor, the
    // global flows store is populated from `header_flows=true`, so the
    // flow being moved has no `data` field.
    const headerFlow = {
      id: "flow-1",
      name: "Saved Flow",
      data: null,
      description: "desc",
      folder_id: "folder-A",
      endpoint_name: "saved-flow",
      locked: false,
      is_component: false,
    };

    flowStoreState = {
      currentFlow: null,
      nodes: [],
      edges: [],
      reactFlowInstance: null,
      onFlowPage: false,
      setCurrentFlow: mockSetCurrentFlow,
    };

    flowsManagerState = {
      currentFlow: null,
      flows: [headerFlow],
      setFlows: mockSetFlows,
      setSaveLoading: mockSetSaveLoading,
    };

    mockMutate.mockImplementation((payload, options) => {
      // Backend responds with the patched flow (FlowRead), echoing the
      // new folder_id the client just sent.
      options.onSuccess({
        ...headerFlow,
        folder_id: payload.folder_id,
      });
    });

    const { result } = renderHook(() => useSaveFlow());

    // Act — the drag-and-drop handler spreads the existing flow and sets
    // the new folder_id, then calls saveFlow(updatedFlow).
    const updatedFlow = { ...headerFlow, folder_id: "folder-B" };
    await expect(result.current(updatedFlow)).resolves.toBeUndefined();

    // Assert — the global flows store must be updated with the new
    // folder_id so the HomePage's `isEmptyFolder` effect reflects the
    // move without requiring a full page refresh.
    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "flow-1",
        folder_id: "folder-B",
        providerScopeChanged: true,
      }),
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(mockSetFlows).toHaveBeenCalledTimes(1);
    const nextFlows = mockSetFlows.mock.calls[0][0];
    expect(nextFlows).toHaveLength(1);
    expect(nextFlows[0]).toEqual(
      expect.objectContaining({ id: "flow-1", folder_id: "folder-B" }),
    );
  });
  it("keeps canvas edits made while the save was in flight", async () => {
    // The editor's `currentFlow` is the baseline the next autosave diffs
    // against. Overwriting it with the response of a save that started before
    // the edit makes that edit look already-persisted, so the follow-up save
    // is skipped and the work is lost. Reproduced on Windows CI as a published
    // flow whose edge never reached the backend.
    let resolveSave: (() => void) | undefined;
    mockMutate.mockImplementation((payload, options) => {
      resolveSave = () =>
        options.onSuccess({
          ...flowsManagerState.currentFlow,
          data: payload.data,
        });
    });

    const { result } = renderHook(() => useSaveFlow());
    const inFlight = result.current();

    // The user connects an edge while the request is still open.
    const newEdges = [{ id: "new-edge" }];
    flowStoreState.edges = newEdges;
    flowStoreState.currentFlow = {
      ...flowStoreState.currentFlow,
      data: { ...flowStoreState.currentFlow.data, edges: newEdges },
    };

    resolveSave!();
    await inFlight;

    expect(mockSetCurrentFlow).not.toHaveBeenCalled();
    expect(flowStoreState.currentFlow.data.edges).toEqual(newEdges);
  });

  it("still adopts the saved flow when the canvas did not change", async () => {
    const { result } = renderHook(() => useSaveFlow());

    await expect(result.current()).resolves.toBeUndefined();

    expect(mockSetCurrentFlow).toHaveBeenCalledTimes(1);
  });
});
