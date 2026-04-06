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
});
