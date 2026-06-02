import type { Node } from "@xyflow/react";
import type { EdgeType } from "@/types/flow";

const mockSetNoticeData = jest.fn();

jest.mock("../alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setNoticeData: mockSetNoticeData,
    }),
  },
}));

import { filterMutuallyExclusiveComponents } from "../helpers/filter-mutually-exclusive-components";

function createNode(id: string, type: string): Node {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { type },
  } as Node;
}

function createEdge(id: string, source: string, target: string): EdgeType {
  return { id, source, target } as EdgeType;
}

describe("filterMutuallyExclusiveComponents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("removes a pasted ChatInput when a Webhook already exists in the flow", () => {
    const selection = {
      nodes: [createNode("node-1", "ChatInput")],
      edges: [],
    };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "Webhook"),
    ]);

    expect(selection.nodes).toHaveLength(0);
    expect(mockSetNoticeData).toHaveBeenCalledTimes(1);
  });

  it("removes a pasted Webhook when a ChatInput already exists in the flow", () => {
    const selection = {
      nodes: [createNode("node-1", "Webhook")],
      edges: [],
    };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "ChatInput"),
    ]);

    expect(selection.nodes).toHaveLength(0);
    expect(mockSetNoticeData).toHaveBeenCalledTimes(1);
  });

  it("keeps non-conflicting pasted nodes and does not show a notice", () => {
    const selection = {
      nodes: [
        createNode("node-1", "ChatInput"),
        createNode("node-2", "TextInput"),
      ],
      edges: [],
    };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "LLM"),
    ]);

    expect(selection.nodes).toHaveLength(2);
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });

  it("drops only the conflicting node and keeps the rest of the selection", () => {
    const selection = {
      nodes: [
        createNode("node-1", "ChatInput"),
        createNode("node-2", "TextInput"),
      ],
      edges: [createEdge("edge-1", "node-1", "node-2")],
    };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "Webhook"),
    ]);

    expect(selection.nodes).toHaveLength(1);
    expect(selection.nodes[0].id).toBe("node-2");
    // The edge referencing the removed node is dropped.
    expect(selection.edges).toHaveLength(0);
  });

  it("prevents a single paste from introducing two mutually exclusive components", () => {
    const selection = {
      nodes: [
        createNode("node-1", "ChatInput"),
        createNode("node-2", "Webhook"),
      ],
      edges: [],
    };

    filterMutuallyExclusiveComponents(selection, []);

    // The first node is kept; the second conflicts with it and is removed.
    expect(selection.nodes).toHaveLength(1);
    expect(selection.nodes[0].id).toBe("node-1");
    expect(mockSetNoticeData).toHaveBeenCalledTimes(1);
  });

  it("keeps edges between surviving nodes", () => {
    const selection = {
      nodes: [
        createNode("node-1", "ChatInput"),
        createNode("node-2", "TextInput"),
        createNode("node-3", "LLM"),
      ],
      edges: [
        createEdge("edge-1", "node-1", "node-2"),
        createEdge("edge-2", "node-2", "node-3"),
      ],
    };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "Webhook"),
    ]);

    expect(selection.nodes).toHaveLength(2);
    expect(selection.edges).toHaveLength(1);
    expect(selection.edges[0].id).toBe("edge-2");
  });

  it("does not crash on component types that collide with Object prototype keys", () => {
    const selection = {
      nodes: [createNode("node-1", "constructor")],
      edges: [],
    };

    expect(() =>
      filterMutuallyExclusiveComponents(selection, [
        createNode("existing-1", "Webhook"),
      ]),
    ).not.toThrow();
    // The non-rule type is kept and no notice fires.
    expect(selection.nodes).toHaveLength(1);
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });

  it("handles an empty selection without errors or notices", () => {
    const selection = { nodes: [] as Node[], edges: [] as EdgeType[] };

    filterMutuallyExclusiveComponents(selection, [
      createNode("existing-1", "Webhook"),
    ]);

    expect(selection.nodes).toHaveLength(0);
    expect(selection.edges).toHaveLength(0);
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });
});
