// biome-ignore-all lint/suspicious/noExplicitAny: store mocks intentionally accept multiple selector shapes
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import useSaveFlow from "../use-save-flow";

const mockApiPatch = jest.fn();
const mockSetFlows = jest.fn();
const mockSetSaveLoading = jest.fn();
const mockSetCurrentFlow = jest.fn();

let flowStoreState: any;
let flowsManagerState: any;

jest.mock("@/controllers/API/api", () => ({
  api: { patch: (...args: unknown[]) => mockApiPatch(...args) },
}));

jest.mock("@/controllers/API/queries/flows/use-get-flow", () => ({
  useGetFlow: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ setErrorData: jest.fn(), setNoticeData: jest.fn() }),
}));

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (selector: any) =>
    selector ? selector(flowStoreState) : flowStoreState;
  useFlowStore.getState = () => flowStoreState;
  return { __esModule: true, default: useFlowStore };
});

jest.mock("@/stores/flowsManagerStore", () => {
  const useFlowsManagerStore = (selector: any) =>
    selector ? selector(flowsManagerState) : flowsManagerState;
  useFlowsManagerStore.getState = () => flowsManagerState;
  return { __esModule: true, default: useFlowsManagerStore };
});

describe("useSaveFlow when the canvas unmounts mid-save", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    const savedFlow = {
      id: "flow-1",
      name: "Flow",
      data: {
        nodes: [{ id: "a" }],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
      folder_id: "folder-1",
      locked: false,
      version_token: "token-before",
    };
    const movedNodes = [{ id: "a", position: { x: 10, y: 10 } }];
    flowStoreState = {
      currentFlow: {
        ...savedFlow,
        data: { ...savedFlow.data, nodes: movedNodes },
      },
      nodes: movedNodes,
      edges: [],
      reactFlowInstance: { getViewport: () => ({ x: 0, y: 0, zoom: 1 }) },
      onFlowPage: true,
      setCurrentFlow: mockSetCurrentFlow,
      userEditedSinceLoad: true,
    };
    flowsManagerState = {
      currentFlow: savedFlow,
      flows: [savedFlow],
      setFlows: mockSetFlows,
      setSaveLoading: mockSetSaveLoading,
    };
  });

  it("should adopt the new version token when the save completes after the canvas unmounted", async () => {
    let respond: (value: unknown) => void = () => {};
    mockApiPatch.mockReturnValue(
      new Promise((resolve) => {
        respond = resolve;
      }),
    );
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result, unmount } = renderHook(() => useSaveFlow(), { wrapper });

    const saving = result.current();
    // Opening Memories or Traces swaps the canvas out while the save is in flight.
    unmount();
    await act(async () => {
      respond({
        data: {
          ...flowStoreState.currentFlow,
          data: {
            nodes: flowStoreState.nodes,
            edges: [],
            viewport: { x: 0, y: 0, zoom: 1 },
          },
          version_token: "token-after",
        },
      });
    });

    await expect(saving).resolves.toBeUndefined();
    expect(mockApiPatch).toHaveBeenCalledWith(
      expect.stringContaining("flow-1"),
      expect.anything(),
      { headers: { "If-Match": "token-before" } },
    );
    expect(mockSetFlows).toHaveBeenCalledWith([
      expect.objectContaining({ id: "flow-1", version_token: "token-after" }),
    ]);
    expect(mockSetSaveLoading).toHaveBeenLastCalledWith(false);
  });
});
