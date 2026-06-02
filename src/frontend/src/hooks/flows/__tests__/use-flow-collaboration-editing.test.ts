import { act, renderHook, waitFor } from "@testing-library/react";

import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import type { FlowOperation } from "@/types/flow-operations";

import {
  readCollaborationOperationBetaEnabled,
  writeCollaborationOperationBetaEnabled,
} from "../collaboration-operation-beta";
import type { UseFlowCollaborationOptions } from "../use-flow-collaboration";
import { useFlowCollaborationEditing } from "../use-flow-collaboration-editing";

const mockSubmitOperations = jest.fn((operations: FlowOperation[]) =>
  Promise.resolve({
    type: "operation.accepted",
    request_id: "req-1",
    flow_id: "flow-1",
    revision: 1,
    actor_user_id: "user-1",
    actor_delegate: "self",
    forward_ops: operations,
    created_at: "2026-05-30T00:00:00Z",
  }),
);
const mockDisconnect = jest.fn();
const mockGetFlow = jest.fn();
const mockApplyFlowToCanvas = jest.fn();
const mockClearUndoRedoHistory = jest.fn();
let mockCollaborationOptions: UseFlowCollaborationOptions | null = null;

jest.mock("../use-flow-collaboration", () => ({
  useFlowCollaboration: jest.fn((options: UseFlowCollaborationOptions) => {
    mockCollaborationOptions = options;
    return {
      status: "ready",
      connectionId: "conn-1",
      currentRevision: 0,
      users: [],
      selections: [],
      isReady: true,
      submitOperations: mockSubmitOperations,
      sendSelectionUpdate: jest.fn(),
      disconnect: mockDisconnect,
    };
  }),
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
    mockCollaborationOptions = null;
    mockSubmitOperations.mockImplementation((operations: FlowOperation[]) =>
      Promise.resolve({
        type: "operation.accepted",
        request_id: "req-1",
        flow_id: "flow-1",
        revision: 1,
        actor_user_id: "user-1",
        actor_delegate: "self",
        forward_ops: operations,
        created_at: "2026-05-30T00:00:00Z",
      }),
    );
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

  it("coalesces rapid node update operations before submitting", async () => {
    jest.useFakeTimers();
    try {
      writeCollaborationOperationBetaEnabled(true);
      const originalNode = {
        id: "node-1",
        position: { x: 0, y: 0 },
        data: { id: "node-1", value: "" },
      } as AllNodeType;
      const firstTypedNode = {
        ...originalNode,
        data: { id: "node-1", value: "h" },
      } as AllNodeType;
      const finalTypedNode = {
        ...originalNode,
        data: { id: "node-1", value: "hi" },
      } as AllNodeType;

      renderHook(() =>
        useFlowCollaborationEditing({
          flowId: "flow-1",
        }),
      );

      await act(async () => {});

      act(() => {
        useFlowStore
          .getState()
          .onCollaborationOperations?.(
            [{ type: "update_nodes", nodes: [firstTypedNode] }],
            {
              historyEntry: {
                forwardOps: [{ type: "update_nodes", nodes: [firstTypedNode] }],
                inverseOps: [{ type: "update_nodes", nodes: [originalNode] }],
              },
            },
          );
        useFlowStore
          .getState()
          .onCollaborationOperations?.(
            [{ type: "update_nodes", nodes: [finalTypedNode] }],
            {
              historyEntry: {
                forwardOps: [{ type: "update_nodes", nodes: [finalTypedNode] }],
                inverseOps: [{ type: "update_nodes", nodes: [firstTypedNode] }],
              },
            },
          );
      });

      expect(mockSubmitOperations).not.toHaveBeenCalled();

      await act(async () => {
        jest.advanceTimersByTime(300);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenCalledTimes(1);
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", nodes: [finalTypedNode] },
      ]);

      mockSubmitOperations.mockClear();

      await act(async () => {
        useFlowStore.getState().undoCollaborationOperations?.();
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", nodes: [originalNode] },
      ]);
    } finally {
      jest.useRealTimers();
    }
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

  it("submits inverse operations when collaboration undo is invoked", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const originalNode = {
      id: "node-1",
      position: { x: 0, y: 0 },
      data: { id: "node-1" },
    } as AllNodeType;
    const movedNode = {
      ...originalNode,
      position: { x: 25, y: 25 },
    } as AllNodeType;

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});
    await act(async () => {
      useFlowStore
        .getState()
        .onCollaborationOperations?.(
          [{ type: "update_nodes", nodes: [movedNode] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", nodes: [movedNode] }],
              inverseOps: [{ type: "update_nodes", nodes: [originalNode] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", nodes: [movedNode] },
      ]);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", nodes: [originalNode] },
      ]);
    });
  });

  it("does not undo a local history entry invalidated by remote operations", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const nodeA = {
      id: "a",
      position: { x: 0, y: 0 },
      data: { id: "a" },
    } as AllNodeType;
    useFlowStore.setState({
      nodes: [nodeA],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: { nodes: [nodeA], edges: [] },
      },
    });

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});
    await act(async () => {
      useFlowStore
        .getState()
        .onCollaborationOperations?.([{ type: "add_nodes", nodes: [nodeA] }], {
          historyEntry: {
            forwardOps: [{ type: "add_nodes", nodes: [nodeA] }],
            inverseOps: [{ type: "delete_nodes", ids: ["a"] }],
          },
        });
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledTimes(1);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      mockCollaborationOptions?.onRemoteOperation?.({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 2,
        actor_user_id: "user-2",
        actor_delegate: "self",
        forward_ops: [{ type: "delete_nodes", ids: ["a"] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    expect(mockSubmitOperations).not.toHaveBeenCalled();
  });
});
