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
    expect(mockSetSaveLoading).toHaveBeenCalledWith(true);
    expect(mockSetSaveLoading).toHaveBeenCalledWith(false);
    expect(mockSetCurrentFlow).toHaveBeenCalled();
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
});
