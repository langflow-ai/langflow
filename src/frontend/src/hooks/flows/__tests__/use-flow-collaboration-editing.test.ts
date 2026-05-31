import { act, renderHook, waitFor } from "@testing-library/react";

import useFlowStore from "@/stores/flowStore";

import {
  readCollaborationOperationBetaEnabled,
  writeCollaborationOperationBetaEnabled,
} from "../collaboration-operation-beta";
import { useFlowCollaborationEditing } from "../use-flow-collaboration-editing";

const mockSubmitOperations = jest.fn().mockResolvedValue({
  type: "operation.accepted",
  revision: 1,
});
const mockDisconnect = jest.fn();
const mockGetFlow = jest.fn();
const mockApplyFlowToCanvas = jest.fn();
const mockClearUndoRedoHistory = jest.fn();

jest.mock("../use-flow-collaboration", () => ({
  useFlowCollaboration: jest.fn(() => ({
    status: "ready",
    connectionId: "conn-1",
    currentRevision: 0,
    users: [],
    isReady: true,
    submitOperations: mockSubmitOperations,
    disconnect: mockDisconnect,
  })),
}));

jest.mock("@/controllers/API/queries/flows/use-get-flow", () => ({
  useGetFlow: () => ({ mutateAsync: mockGetFlow }),
}));

jest.mock("@/hooks/flows/use-apply-flow-to-canvas", () => ({
  __esModule: true,
  default: () => mockApplyFlowToCanvas,
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const state = {
    currentFlowId: "flow-1",
    flows: [],
    setFlows: jest.fn(),
    setCurrentFlow: jest.fn(),
    clearUndoRedoHistory: mockClearUndoRedoHistory,
  };
  const useFlowsManagerStore = (selector?: (value: typeof state) => unknown) =>
    selector ? selector(state) : state;
  useFlowsManagerStore.getState = () => state;
  return { __esModule: true, default: useFlowsManagerStore };
});

describe("useFlowCollaborationEditing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSubmitOperations.mockResolvedValue({
      type: "operation.accepted",
      revision: 1,
    });
    writeCollaborationOperationBetaEnabled(false);
    useFlowStore.setState({
      collaborationOperationMode: false,
      onCollaborationOperations: undefined,
      flushCollaborationSave: undefined,
      nodes: [],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: { nodes: [], edges: [] },
      },
    });
    mockGetFlow.mockResolvedValue({
      id: "flow-1",
      name: "Flow",
      description: "",
      data: { nodes: [], edges: [] },
    });
  });

  it("does not enable collaboration mode when the beta toggle is off", async () => {
    const { useFlowCollaboration } = jest.requireMock(
      "../use-flow-collaboration",
    );

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});

    expect(useFlowCollaboration).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false }),
    );
    expect(useFlowStore.getState().collaborationOperationMode).toBe(false);
  });

  it("enables collaboration mode and reloads when the beta toggle is turned on", async () => {
    const { result } = renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {
      await result.current.setBetaEnabled(true);
    });

    expect(readCollaborationOperationBetaEnabled()).toBe(true);
    expect(mockGetFlow).toHaveBeenCalledWith({ id: "flow-1" });
    expect(mockApplyFlowToCanvas).toHaveBeenCalled();
    expect(useFlowStore.getState().collaborationOperationMode).toBe(true);
  });

  it("submits operations emitted from the flow store when collaboration mode is active", async () => {
    writeCollaborationOperationBetaEnabled(true);

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});

    await act(async () => {
      useFlowStore
        .getState()
        .onCollaborationOperations?.([{ type: "delete_edges", ids: ["e1"] }]);
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "delete_edges", ids: ["e1"] },
      ]);
    });
  });

  it("reloads and drops pending operations when submit fails", async () => {
    mockSubmitOperations.mockRejectedValueOnce(
      new Error("Stale base revision"),
    );
    writeCollaborationOperationBetaEnabled(true);

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});

    await act(async () => {
      useFlowStore
        .getState()
        .onCollaborationOperations?.([{ type: "delete_edges", ids: ["e1"] }]);
    });

    await waitFor(() => {
      expect(mockGetFlow).toHaveBeenCalledWith({ id: "flow-1" });
    });
  });
});
