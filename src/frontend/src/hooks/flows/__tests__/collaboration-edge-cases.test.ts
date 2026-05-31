import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { applyRemoteFlowOperations } from "../flow-operation-adapter";

const nodeA = {
  id: "a",
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: { id: "a", type: "TextInput", node: {} },
} as AllNodeType;

const nodeB = {
  id: "b",
  type: "genericNode",
  position: { x: 100, y: 0 },
  data: { id: "b", type: "TextOutput", node: {} },
} as AllNodeType;

const edgeAb = {
  id: "e-ab",
  source: "a",
  target: "b",
} as EdgeType;

function seedFlow(flowId: string, emit = jest.fn()) {
  useFlowsManagerStore.setState({
    currentFlowId: flowId,
    currentFlow: {
      id: flowId,
      name: "Flow",
      description: "",
      data: { nodes: [nodeA, nodeB], edges: [edgeAb] },
    },
  });
  useFlowStore.setState({
    nodes: [nodeA, nodeB],
    edges: [edgeAb],
    currentFlow: {
      id: flowId,
      name: "Flow",
      description: "",
      data: { nodes: [nodeA, nodeB], edges: [edgeAb] },
    },
    collaborationOperationMode: true,
    isApplyingRemoteOperations: false,
    onCollaborationOperations: emit,
  });
  return emit;
}

describe("collaboration edge-case store wiring", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("cut emits one combined delete batch", () => {
    const emit = seedFlow("cut-flow");

    useFlowStore.getState().setLastCopiedSelection(
      {
        nodes: [nodeA],
        edges: [],
      },
      true,
    );

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith(
      [
        { type: "delete_nodes", ids: ["a"] },
        { type: "delete_edges", ids: ["e-ab"] },
      ],
      expect.objectContaining({
        historyEntry: expect.objectContaining({
          inverseOps: [
            { type: "add_nodes", nodes: [nodeA] },
            { type: "add_edges", edges: [edgeAb] },
          ],
        }),
      }),
    );
  });

  it("undo delegates to collaboration operation history when enabled", () => {
    seedFlow("undo-flow");
    const undoCollaborationOperations = jest.fn();
    useFlowStore.setState({ undoCollaborationOperations });

    useFlowsManagerStore.getState().undo();

    expect(undoCollaborationOperations).toHaveBeenCalledTimes(1);
  });

  it("redo delegates to collaboration operation history when enabled", () => {
    seedFlow("redo-flow");
    const redoCollaborationOperations = jest.fn();
    useFlowStore.setState({ redoCollaborationOperations });

    useFlowsManagerStore.getState().redo();

    expect(redoCollaborationOperations).toHaveBeenCalledTimes(1);
  });

  it("remote operations clear stale undo history so undo does not resurrect remote deletes", () => {
    const emit = seedFlow("remote-delete-flow");
    useFlowsManagerStore.getState().takeSnapshot();

    applyRemoteFlowOperations([{ type: "delete_nodes", ids: ["a"] }]);
    emit.mockClear();

    useFlowsManagerStore.getState().undo();

    expect(useFlowStore.getState().nodes.map((node) => node.id)).toEqual(["b"]);
    expect(useFlowStore.getState().edges).toEqual([]);
    expect(emit).not.toHaveBeenCalled();
  });
});
