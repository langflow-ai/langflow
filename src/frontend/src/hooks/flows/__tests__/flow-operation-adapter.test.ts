import useFlowStore from "@/stores/flowStore";
import type { AllNodeType, EdgeType } from "@/types/flow";

import {
  applyFlowOperationsLocally,
  applyRemoteFlowOperations,
  buildGraphDiffOperations,
  buildUpdateMetadataOperation,
} from "../flow-operation-adapter";

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

describe("flow-operation-adapter", () => {
  beforeEach(() => {
    useFlowStore.setState({
      nodes: [nodeA, nodeB],
      edges: [edgeAb],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: { nodes: [nodeA, nodeB], edges: [edgeAb] },
      },
      collaborationOperationMode: false,
      isApplyingRemoteOperations: false,
      onCollaborationOperations: undefined,
    });
  });

  it("buildGraphDiffOperations detects node updates and edge deletes", () => {
    const updatedA = {
      ...nodeA,
      position: { x: 10, y: 10 },
    } as AllNodeType;

    const operations = buildGraphDiffOperations(
      [nodeA, nodeB],
      [edgeAb],
      [updatedA, nodeB],
      [],
    );

    expect(operations).toEqual(
      expect.arrayContaining([
        { type: "update_nodes", nodes: [expect.objectContaining({ id: "a" })] },
        { type: "delete_edges", ids: ["e-ab"] },
      ]),
    );
  });

  it("buildGraphDiffOperations represents edge reconnect as delete plus add", () => {
    const reconnectedEdge = {
      ...edgeAb,
      id: "e-reconnected",
      source: "b",
      target: "a",
    } as EdgeType;

    const operations = buildGraphDiffOperations(
      [nodeA, nodeB],
      [edgeAb],
      [nodeA, nodeB],
      [reconnectedEdge],
    );

    expect(operations).toEqual([
      { type: "delete_edges", ids: ["e-ab"] },
      { type: "add_edges", edges: [reconnectedEdge] },
    ]);
  });

  it("buildUpdateMetadataOperation ignores graph collections and viewport", () => {
    const operation = buildUpdateMetadataOperation(
      {
        nodes: [nodeA],
        edges: [edgeAb],
        viewport: { x: 0, y: 0, zoom: 1 },
        theme: "old",
        removed: true,
      },
      {
        nodes: [],
        edges: [],
        viewport: { x: 10, y: 10, zoom: 2 },
        theme: "new",
      },
    );

    expect(operation).toEqual({
      type: "update_metadata",
      fields: { theme: "new" },
      delete_keys: ["removed"],
    });
  });

  it("applyFlowOperationsLocally applies delete_nodes with incident edges", () => {
    const result = applyFlowOperationsLocally(
      [nodeA, nodeB],
      [edgeAb],
      [{ type: "delete_nodes", ids: ["a"] }],
    );

    expect(result.nodes.map((node) => node.id)).toEqual(["b"]);
    expect(result.edges).toEqual([]);
  });

  it("applyRemoteFlowOperations updates the store without emitting collaboration ops", () => {
    const emit = jest.fn();
    useFlowStore.setState({
      onCollaborationOperations: emit,
      collaborationOperationMode: true,
    });

    applyRemoteFlowOperations([
      {
        type: "update_nodes",
        nodes: [{ ...nodeA, position: { x: 25, y: 25 } } as AllNodeType],
      },
    ]);

    expect(useFlowStore.getState().nodes[0]?.position).toEqual({
      x: 25,
      y: 25,
    });
    expect(emit).not.toHaveBeenCalled();
  });
});
