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

const movedNodeA = {
  ...nodeA,
  position: { x: 25, y: 25 },
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
    expect(emit).toHaveBeenCalledWith([
      { type: "delete_nodes", ids: ["a"] },
      { type: "delete_edges", ids: ["e-ab"] },
    ]);
  });

  it("undo emits the resulting graph delta once", () => {
    const emit = seedFlow("undo-flow");
    useFlowsManagerStore.getState().takeSnapshot();
    useFlowStore.setState({
      nodes: [movedNodeA, nodeB],
      edges: [edgeAb],
    });

    useFlowsManagerStore.getState().undo();

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith([
      { type: "update_nodes", nodes: [expect.objectContaining({ id: "a" })] },
    ]);
  });

  it("redo emits the resulting graph delta once", () => {
    const emit = seedFlow("redo-flow");
    useFlowsManagerStore.getState().takeSnapshot();
    useFlowStore.setState({
      nodes: [movedNodeA, nodeB],
      edges: [edgeAb],
    });
    useFlowsManagerStore.getState().undo();
    emit.mockClear();

    useFlowsManagerStore.getState().redo();

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith([
      { type: "update_nodes", nodes: [expect.objectContaining({ id: "a" })] },
    ]);
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
