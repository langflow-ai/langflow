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

import { filterSingletonComponent } from "../helpers/filter-singleton-component";

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

describe("filterSingletonComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should not filter when selection does not contain the component type", () => {
    const selection = {
      nodes: [createNode("node-1", "TextInput")],
      edges: [],
    };

    filterSingletonComponent(selection, "ChatInput", true, "Notice");

    expect(selection.nodes).toHaveLength(1);
    expect(selection.nodes[0].id).toBe("node-1");
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });

  it("should not filter when component does not exist in flow", () => {
    const selection = {
      nodes: [createNode("node-1", "ChatInput")],
      edges: [],
    };

    filterSingletonComponent(selection, "ChatInput", false, "Notice");

    expect(selection.nodes).toHaveLength(1);
    expect(selection.nodes[0].id).toBe("node-1");
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });

  it("should filter singleton node and show notice when component exists in flow", () => {
    const selection = {
      nodes: [createNode("node-1", "ChatInput")],
      edges: [],
    };
    const message = "You can only have one Chat Input component in a flow.";

    filterSingletonComponent(selection, "ChatInput", true, message);

    expect(selection.nodes).toHaveLength(0);
    expect(mockSetNoticeData).toHaveBeenCalledWith({ title: message });
  });

  it("should remove orphaned edges after filtering the singleton node", () => {
    const selection = {
      nodes: [
        createNode("node-1", "ChatInput"),
        createNode("node-2", "TextInput"),
      ],
      edges: [createEdge("edge-1", "node-1", "node-2")],
    };

    filterSingletonComponent(selection, "ChatInput", true, "Only one allowed.");

    expect(selection.nodes).toHaveLength(1);
    expect(selection.nodes[0].id).toBe("node-2");
    expect(selection.edges).toHaveLength(0);
  });

  it("should keep edges between remaining nodes", () => {
    const selection = {
      nodes: [
        createNode("node-1", "Webhook"),
        createNode("node-2", "TextInput"),
        createNode("node-3", "LLM"),
      ],
      edges: [
        createEdge("edge-1", "node-1", "node-2"),
        createEdge("edge-2", "node-2", "node-3"),
      ],
    };

    filterSingletonComponent(selection, "Webhook", true, "Only one allowed.");

    expect(selection.nodes).toHaveLength(2);
    expect(selection.edges).toHaveLength(1);
    expect(selection.edges[0].id).toBe("edge-2");
  });

  it("should handle empty selection without errors", () => {
    const selection = { nodes: [] as Node[], edges: [] as EdgeType[] };

    filterSingletonComponent(selection, "ChatInput", true, "Notice");

    expect(selection.nodes).toHaveLength(0);
    expect(selection.edges).toHaveLength(0);
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });
});
