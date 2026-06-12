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
        data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      },
    });
    mockGetFlow.mockResolvedValue({
      id: "flow-1",
      name: "Flow",
      description: "",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
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
      const firstUpdate = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "value"],
        value: "h",
      };
      const finalUpdate = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "value"],
        value: "hi",
      };
      const originalInverse = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "value"],
        value: "",
      };

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
            [{ type: "update_nodes", updates: [firstUpdate] }],
            {
              historyEntry: {
                forwardOps: [{ type: "update_nodes", updates: [firstUpdate] }],
                inverseOps: [
                  { type: "update_nodes", updates: [originalInverse] },
                ],
              },
            },
          );
        useFlowStore
          .getState()
          .onCollaborationOperations?.(
            [{ type: "update_nodes", updates: [finalUpdate] }],
            {
              historyEntry: {
                forwardOps: [{ type: "update_nodes", updates: [finalUpdate] }],
                inverseOps: [
                  {
                    type: "update_nodes",
                    updates: [
                      {
                        id: "node-1",
                        op: "set_field" as const,
                        path: ["data", "value"],
                        value: "h",
                      },
                    ],
                  },
                ],
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
        { type: "update_nodes", updates: [finalUpdate] },
      ]);

      mockSubmitOperations.mockClear();

      await act(async () => {
        useFlowStore.getState().undoCollaborationOperations?.();
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [originalInverse] },
      ]);
    } finally {
      jest.useRealTimers();
    }
  });

  it("coalesces overlapping field paths with a correct final-to-original inverse", async () => {
    jest.useFakeTimers();
    try {
      writeCollaborationOperationBetaEnabled(true);
      const firstForward = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "slider"],
        value: { value: 1, min: 0, max: 10 },
      };
      const secondForward = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "slider", "value"],
        value: 2,
      };
      const originalInverse = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "slider"],
        value: { value: 0, min: 0, max: 10 },
      };
      const intermediateInverse = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "slider", "value"],
        value: 1,
      };

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
            [{ type: "update_nodes", updates: [firstForward] }],
            {
              historyEntry: {
                forwardOps: [{ type: "update_nodes", updates: [firstForward] }],
                inverseOps: [
                  { type: "update_nodes", updates: [originalInverse] },
                ],
              },
            },
          );
        useFlowStore
          .getState()
          .onCollaborationOperations?.(
            [{ type: "update_nodes", updates: [secondForward] }],
            {
              historyEntry: {
                forwardOps: [
                  { type: "update_nodes", updates: [secondForward] },
                ],
                inverseOps: [
                  { type: "update_nodes", updates: [intermediateInverse] },
                ],
              },
            },
          );
      });

      await act(async () => {
        jest.advanceTimersByTime(300);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [firstForward, secondForward] },
      ]);
      mockSubmitOperations.mockClear();

      await act(async () => {
        useFlowStore.getState().undoCollaborationOperations?.();
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [originalInverse] },
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
    const moveForward = {
      id: "node-1",
      op: "set_field" as const,
      path: ["position"],
      value: { x: 25, y: 25 },
    };
    const moveInverse = {
      id: "node-1",
      op: "set_field" as const,
      path: ["position"],
      value: { x: 0, y: 0 },
    };

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
          [{ type: "update_nodes", updates: [moveForward] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", updates: [moveForward] }],
              inverseOps: [{ type: "update_nodes", updates: [moveInverse] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [moveForward] },
      ]);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [moveInverse] },
      ]);
    });
  });

  it("allows undo before a local operation is accepted", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const forwardOperation: FlowOperation = {
      type: "delete_edges",
      ids: ["e1"],
    };
    const inverseOperation: FlowOperation = {
      type: "add_edges",
      edges: [{ id: "e1", source: "a", target: "b" } as never],
    };
    let resolveFirstSubmit:
      | ((value: {
          type: "operation.accepted";
          request_id: string;
          flow_id: string;
          revision: number;
          actor_user_id: string;
          forward_ops: FlowOperation[];
          created_at: string;
        }) => void)
      | undefined;

    mockSubmitOperations.mockImplementationOnce(
      (operations: FlowOperation[]) =>
        new Promise((resolve) => {
          resolveFirstSubmit = resolve;
        }),
    );

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});
    act(() => {
      useFlowStore.getState().onCollaborationOperations?.([forwardOperation], {
        historyEntry: {
          forwardOps: [forwardOperation],
          inverseOps: [inverseOperation],
        },
      });
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([forwardOperation]);
    });

    act(() => {
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    expect(mockSubmitOperations).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirstSubmit?.({
        type: "operation.accepted",
        request_id: "req-1",
        flow_id: "flow-1",
        revision: 1,
        actor_user_id: "user-1",
        forward_ops: [forwardOperation],
        created_at: "2026-05-30T00:00:00Z",
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([inverseOperation]);
    });
  });

  it("allows undoing coalesced node updates before they are submitted", async () => {
    jest.useFakeTimers();
    try {
      writeCollaborationOperationBetaEnabled(true);
      const forwardUpdate = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "model", "value"],
        value: [{ name: "gpt-4o", provider: "OpenAI" }],
      };
      const inverseUpdate = {
        id: "node-1",
        op: "set_field" as const,
        path: ["data", "node", "template", "model", "value"],
        value: [],
      };
      const forwardOperation: FlowOperation = {
        type: "update_nodes",
        updates: [forwardUpdate],
      };
      const inverseOperation: FlowOperation = {
        type: "update_nodes",
        updates: [inverseUpdate],
      };

      renderHook(() =>
        useFlowCollaborationEditing({
          flowId: "flow-1",
        }),
      );

      await act(async () => {});
      act(() => {
        useFlowStore
          .getState()
          .onCollaborationOperations?.([forwardOperation], {
            historyEntry: {
              forwardOps: [forwardOperation],
              inverseOps: [inverseOperation],
            },
          });
      });

      expect(mockSubmitOperations).not.toHaveBeenCalled();

      await act(async () => {
        useFlowStore.getState().undoCollaborationOperations?.();
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockSubmitOperations).toHaveBeenNthCalledWith(1, [
        forwardOperation,
      ]);
      expect(mockSubmitOperations).toHaveBeenNthCalledWith(2, [
        inverseOperation,
      ]);
    } finally {
      jest.useRealTimers();
    }
  });

  it("applies collaboration undo to the local graph state immediately", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const node = {
      id: "agent-node",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "agent-node",
        type: "Agent",
        node: {
          template: {
            model: { value: [] },
          },
        },
      },
    } as unknown as AllNodeType;
    const selectedNode = {
      ...node,
      data: {
        ...node.data,
        node: {
          ...node.data.node,
          template: {
            ...node.data.node?.template,
            model: {
              ...node.data.node?.template?.model,
              value: [{ name: "gpt-4o", provider: "OpenAI" }],
            },
          },
        },
      },
    } as unknown as AllNodeType;

    useFlowStore.setState({
      nodes: [node],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [node],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
    });

    renderHook(() =>
      useFlowCollaborationEditing({
        flowId: "flow-1",
      }),
    );

    await act(async () => {});

    act(() => {
      useFlowStore
        .getState()
        .setNode("agent-node", selectedNode, true, undefined, {
          collaborationUpdates: [
            {
              id: "agent-node",
              op: "set_field",
              path: ["data", "node", "template", "model", "value"],
              value: [{ name: "gpt-4o", provider: "OpenAI" }],
            },
          ],
        });
    });

    expect(
      useFlowStore.getState().nodes[0].data.node?.template?.model?.value,
    ).toEqual([{ name: "gpt-4o", provider: "OpenAI" }]);

    await act(async () => {
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    expect(
      useFlowStore.getState().nodes[0].data.node?.template?.model?.value,
    ).toEqual([]);
  });

  it("keeps local undo history after a remote delete touches the same node", async () => {
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
        data: {
          nodes: [nodeA],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        forward_ops: [{ type: "delete_nodes", ids: ["a"] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      useFlowStore.getState().undoCollaborationOperations?.();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "delete_nodes", ids: ["a"] },
    ]);
  });

  it("keeps local undo history after a remote edit to an unrelated field on the same node", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const nodeA = {
      id: "a",
      position: { x: 0, y: 0 },
      data: { value: "old", remote: "old" },
    } as AllNodeType;
    const localForward = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "local",
    };
    const localInverse = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "old",
    };
    const remoteForward = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "remote"],
      value: "remote",
    };
    useFlowStore.setState({
      nodes: [nodeA],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [nodeA],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        .onCollaborationOperations?.(
          [{ type: "update_nodes", updates: [localForward] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", updates: [localForward] }],
              inverseOps: [{ type: "update_nodes", updates: [localInverse] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [localForward] },
      ]);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      mockCollaborationOptions?.onRemoteOperation?.({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 2,
        actor_user_id: "user-2",
        forward_ops: [{ type: "update_nodes", updates: [remoteForward] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      useFlowStore.getState().undoCollaborationOperations?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "update_nodes", updates: [localInverse] },
    ]);
  });

  it("keeps local undo history after a remote edit elsewhere in the graph", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const nodeA = {
      id: "a",
      position: { x: 0, y: 0 },
      data: { value: "old" },
    } as AllNodeType;
    const nodeB = {
      id: "b",
      position: { x: 100, y: 0 },
      data: { value: "remote" },
    } as AllNodeType;
    const localForward = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "local",
    };
    const localInverse = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "old",
    };

    useFlowStore.setState({
      nodes: [nodeA],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [nodeA],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        .onCollaborationOperations?.(
          [{ type: "update_nodes", updates: [localForward] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", updates: [localForward] }],
              inverseOps: [{ type: "update_nodes", updates: [localInverse] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [localForward] },
      ]);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      mockCollaborationOptions?.onRemoteOperation?.({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 2,
        actor_user_id: "user-2",
        forward_ops: [{ type: "add_nodes", nodes: [nodeB] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      useFlowStore.getState().undoCollaborationOperations?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "update_nodes", updates: [localInverse] },
    ]);
  });

  it("keeps local undo history after a remote edit to the same field path", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const nodeA = {
      id: "a",
      position: { x: 0, y: 0 },
      data: { value: "old" },
    } as AllNodeType;
    const localForward = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "local",
    };
    const localInverse = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "old",
    };
    const remoteForward = {
      id: "a",
      op: "set_field" as const,
      path: ["data", "value"],
      value: "remote",
    };
    useFlowStore.setState({
      nodes: [nodeA],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [nodeA],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        .onCollaborationOperations?.(
          [{ type: "update_nodes", updates: [localForward] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", updates: [localForward] }],
              inverseOps: [{ type: "update_nodes", updates: [localInverse] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [localForward] },
      ]);
    });
    mockSubmitOperations.mockClear();

    await act(async () => {
      mockCollaborationOptions?.onRemoteOperation?.({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 2,
        actor_user_id: "user-2",
        forward_ops: [{ type: "update_nodes", updates: [remoteForward] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      useFlowStore.getState().undoCollaborationOperations?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "update_nodes", updates: [localInverse] },
    ]);
  });

  it("redoes to the value visible before undo after another user edits the same field", async () => {
    writeCollaborationOperationBetaEnabled(true);
    const modelPath = ["data", "node", "template", "model", "value"];
    const initialValue = [{ name: "gpt-5.4", provider: "OpenAI" }];
    const userAValue = [{ name: "gpt-5.5", provider: "OpenAI" }];
    const userBValue = [{ name: "gpt-5.3", provider: "OpenAI" }];
    const node = {
      id: "agent-node",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "agent-node",
        type: "Agent",
        node: {
          template: {
            model: { value: initialValue },
          },
        },
      },
    } as unknown as AllNodeType;
    const userAForward = {
      id: "agent-node",
      op: "set_field" as const,
      path: modelPath,
      value: userAValue,
    };
    const userAInverse = {
      id: "agent-node",
      op: "set_field" as const,
      path: modelPath,
      value: initialValue,
    };
    const userBForward = {
      id: "agent-node",
      op: "set_field" as const,
      path: modelPath,
      value: userBValue,
    };

    useFlowStore.setState({
      nodes: [node],
      edges: [],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [node],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        .onCollaborationOperations?.(
          [{ type: "update_nodes", updates: [userAForward] }],
          {
            historyEntry: {
              forwardOps: [{ type: "update_nodes", updates: [userAForward] }],
              inverseOps: [{ type: "update_nodes", updates: [userAInverse] }],
            },
          },
        );
    });

    await waitFor(() => {
      expect(mockSubmitOperations).toHaveBeenCalledWith([
        { type: "update_nodes", updates: [userAForward] },
      ]);
    });

    await act(async () => {
      mockCollaborationOptions?.onRemoteOperation?.({
        type: "operation.broadcast",
        flow_id: "flow-1",
        revision: 2,
        actor_user_id: "user-2",
        forward_ops: [{ type: "update_nodes", updates: [userBForward] }],
        created_at: "2026-05-30T00:00:00Z",
      });
      await Promise.resolve();
    });

    mockSubmitOperations.mockClear();

    await act(async () => {
      useFlowStore.getState().undoCollaborationOperations?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "update_nodes", updates: [userAInverse] },
    ]);
    expect(
      useFlowStore.getState().nodes[0].data.node?.template?.model?.value,
    ).toEqual(initialValue);

    mockSubmitOperations.mockClear();

    await act(async () => {
      useFlowStore.getState().redoCollaborationOperations?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(mockSubmitOperations).toHaveBeenCalledWith([
      { type: "update_nodes", updates: [userBForward] },
    ]);
    expect(
      useFlowStore.getState().nodes[0].data.node?.template?.model?.value,
    ).toEqual(userBValue);
  });
});
