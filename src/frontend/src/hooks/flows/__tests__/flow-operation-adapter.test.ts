import useFlowStore from "@/stores/flowStore";
import type { AllNodeType, EdgeType } from "@/types/flow";

import {
  applyFlowOperationsLocally,
  applyRemoteFlowOperations,
} from "../flow-operation-adapter";
import {
  buildGraphDiffOperations,
  buildInverseFlowOperations,
  buildSetNodeFieldUpdate,
  buildUpdateMetadataOperation,
  buildUpdateNodesOperation,
  collectFlowOperationTouches,
  flowOperationTouchesIntersect,
} from "../flow-operation-diff";

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
        data: {
          nodes: [nodeA, nodeB],
          edges: [edgeAb],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
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
        {
          type: "update_nodes",
          updates: [
            {
              id: "a",
              op: "overwrite_node",
              node: expect.objectContaining({ id: "a" }),
            },
          ],
        },
        { type: "delete_edges", ids: ["e-ab"] },
      ]),
    );
  });

  it("buildGraphDiffOperations ignores React Flow runtime node fields", () => {
    const measuredNode = {
      ...nodeA,
      selected: true,
      dragging: true,
      measured: { width: 320, height: 180 },
    } as AllNodeType;

    const operations = buildGraphDiffOperations(
      [nodeA],
      [edgeAb],
      [measuredNode],
      [edgeAb],
    );

    expect(operations).toEqual([]);
  });

  it("buildUpdateNodesOperation omits React Flow runtime node fields", () => {
    const operation = buildUpdateNodesOperation([
      {
        ...nodeA,
        selected: true,
        dragging: true,
        measured: { width: 320, height: 180 },
        position: { x: 25, y: 25 },
      } as AllNodeType,
    ]);

    expect(operation).toEqual({
      type: "update_nodes",
      updates: [
        {
          id: "a",
          op: "overwrite_node",
          node: {
            ...nodeA,
            position: { x: 25, y: 25 },
          },
        },
      ],
    });
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

  it("buildInverseFlowOperations restores deleted nodes with incident edges", () => {
    const inverse = buildInverseFlowOperations(
      [nodeA, nodeB],
      [edgeAb],
      { nodes: [nodeA, nodeB], edges: [edgeAb] },
      [{ type: "delete_nodes", ids: ["a"] }],
    );

    expect(inverse).toEqual([
      { type: "add_nodes", nodes: [nodeA] },
      { type: "add_edges", edges: [edgeAb] },
    ]);
  });

  it("buildInverseFlowOperations reverses edge reconnect order", () => {
    const replacementEdge = {
      ...edgeAb,
      id: "e-ba",
      source: "b",
      target: "a",
    } as EdgeType;

    const inverse = buildInverseFlowOperations(
      [nodeA, nodeB],
      [edgeAb],
      { nodes: [nodeA, nodeB], edges: [edgeAb] },
      [
        { type: "delete_edges", ids: ["e-ab"] },
        { type: "add_edges", edges: [replacementEdge] },
      ],
    );

    expect(inverse).toEqual([
      { type: "delete_edges", ids: ["e-ba"] },
      { type: "add_edges", edges: [edgeAb] },
    ]);
  });

  it("buildInverseFlowOperations restores metadata keys and deletes new keys", () => {
    const inverse = buildInverseFlowOperations(
      [nodeA, nodeB],
      [edgeAb],
      { theme: "old", stale_key: true },
      [
        {
          type: "update_metadata",
          fields: { theme: "new", created_key: "value" },
          delete_keys: ["stale_key"],
        },
      ],
    );

    expect(inverse).toEqual([
      {
        type: "update_metadata",
        fields: { theme: "old", stale_key: true },
        delete_keys: ["created_key"],
      },
    ]);
  });

  it("buildInverseFlowOperations inverts set and delete field updates", () => {
    const nodeWithFields = {
      ...nodeA,
      data: { ...nodeA.data, label: "old", removed: true },
    } as unknown as AllNodeType;

    const inverse = buildInverseFlowOperations(
      [nodeWithFields],
      [],
      { nodes: [nodeWithFields], edges: [] },
      [
        {
          type: "update_nodes",
          updates: [
            buildSetNodeFieldUpdate("a", ["data", "label"], "new"),
            buildSetNodeFieldUpdate("a", ["data", "created"], null),
            { id: "a", op: "delete_field", path: ["data", "removed"] },
          ],
        },
      ],
    );

    expect(inverse).toEqual([
      {
        type: "update_nodes",
        updates: [
          { id: "a", op: "set_field", path: ["data", "removed"], value: true },
          { id: "a", op: "delete_field", path: ["data", "created"] },
          { id: "a", op: "set_field", path: ["data", "label"], value: "old" },
        ],
      },
    ]);
  });

  it("flow operation touch helpers detect overlapping graph and metadata changes", () => {
    const localTouches = collectFlowOperationTouches([
      { type: "add_edges", edges: [edgeAb] },
      { type: "update_metadata", fields: { theme: "dark" } },
    ]);
    const remoteTouches = collectFlowOperationTouches([
      { type: "delete_nodes", ids: ["a"] },
    ]);
    const unrelatedTouches = collectFlowOperationTouches([
      { type: "update_metadata", fields: { another_key: true } },
    ]);

    expect(flowOperationTouchesIntersect(remoteTouches, localTouches)).toBe(
      true,
    );
    expect(flowOperationTouchesIntersect(unrelatedTouches, localTouches)).toBe(
      false,
    );
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

  it("applyFlowOperationsLocally preserves local node selection on updates", () => {
    const selectedNode = { ...nodeA, selected: true } as AllNodeType;
    const result = applyFlowOperationsLocally(
      [selectedNode, nodeB],
      [edgeAb],
      [
        {
          type: "update_nodes",
          updates: [
            {
              id: "a",
              op: "overwrite_node",
              node: {
                ...nodeA,
                selected: false,
                measured: { width: 320, height: 180 },
                position: { x: 25, y: 25 },
              } as AllNodeType,
            },
          ],
        },
      ],
    );

    expect(result.nodes[0]).toEqual({
      ...nodeA,
      selected: true,
      position: { x: 25, y: 25 },
    });
  });

  it("applyFlowOperationsLocally preserves local edge selection on node updates", () => {
    const selectedEdge = { ...edgeAb, selected: true } as EdgeType;
    const result = applyFlowOperationsLocally(
      [nodeA, nodeB],
      [selectedEdge],
      [
        {
          type: "update_nodes",
          updates: [
            buildSetNodeFieldUpdate("a", ["position"], { x: 25, y: 25 }),
          ],
        },
      ],
    );

    expect(result.edges).toEqual([
      expect.objectContaining({ id: "e-ab", selected: true }),
    ]);
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
        updates: [buildSetNodeFieldUpdate("a", ["position"], { x: 25, y: 25 })],
      },
    ]);

    expect(useFlowStore.getState().nodes[0]?.position).toEqual({
      x: 25,
      y: 25,
    });
    expect(emit).not.toHaveBeenCalled();
  });

  it("applyRemoteFlowOperations preserves selected edges in the local store", () => {
    const selectedEdge = { ...edgeAb, selected: true } as EdgeType;
    useFlowStore.setState({
      edges: [selectedEdge],
      currentFlow: {
        id: "flow-1",
        name: "Flow",
        description: "",
        data: {
          nodes: [nodeA, nodeB],
          edges: [selectedEdge],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
    });

    applyRemoteFlowOperations([
      {
        type: "update_nodes",
        updates: [buildSetNodeFieldUpdate("a", ["position"], { x: 25, y: 25 })],
      },
    ]);

    expect(useFlowStore.getState().edges).toEqual([
      expect.objectContaining({ id: "e-ab", selected: true }),
    ]);
  });

  it("applyFlowOperationsLocally updates fields without clobbering siblings", () => {
    const node = {
      ...nodeA,
      data: { ...nodeA.data, label: "old", sibling: true },
    } as unknown as AllNodeType;

    const result = applyFlowOperationsLocally(
      [node],
      [],
      [
        {
          type: "update_nodes",
          updates: [
            buildSetNodeFieldUpdate("a", ["data", "label"], null),
            { id: "a", op: "delete_field", path: ["data", "missing"] },
          ],
        },
      ],
    );

    expect(result.nodes[0]?.data).toEqual({
      ...nodeA.data,
      label: null,
      sibling: true,
    });
  });
});
