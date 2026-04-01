import { act, renderHook } from "@testing-library/react";
import type { AllNodeType, NodeDataType } from "@/types/flow";
import { useTweaksStore } from "../tweaksStore";

// Mock all the complex dependencies
jest.mock("@/modals/apiModal/utils/get-changes-types", () => ({
  getChangesType: jest.fn((value, template) => value),
}));

jest.mock("@/modals/apiModal/utils/get-nodes-with-default-value", () => ({
  getNodesWithDefaultValue: jest.fn((nodes, tweaks) => nodes),
}));

jest.mock("@/utils/local-storage-util", () => ({
  getLocalStorage: jest.fn(),
  setLocalStorage: jest.fn(),
}));

jest.mock("../flowStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(() => ({
      unselectAll: jest.fn(),
    })),
  },
}));

// Mock imports
const mockGetChangesType =
  require("@/modals/apiModal/utils/get-changes-types").getChangesType;
const mockGetNodesWithDefaultValue =
  require("@/modals/apiModal/utils/get-nodes-with-default-value").getNodesWithDefaultValue;
const mockGetLocalStorage =
  require("@/utils/local-storage-util").getLocalStorage;
const mockSetLocalStorage =
  require("@/utils/local-storage-util").setLocalStorage;
const mockFlowStore = require("../flowStore").default;

const mockNode: AllNodeType = {
  id: "node-1",
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: {
    node: {
      template: {
        param1: {
          advanced: false,
          value: "test-value",
        },
        param2: {
          advanced: true,
          value: "advanced-value",
        },
      },
      frozen: false,
    },
    type: "TestNode",
  } as NodeDataType,
};

const mockNode2: AllNodeType = {
  id: "node-2",
  type: "genericNode",
  position: { x: 100, y: 100 },
  data: {
    node: {
      template: {
        param3: {
          advanced: false,
          value: "another-value",
        },
      },
      frozen: false,
    },
    type: "AnotherNode",
  } as NodeDataType,
};

const mockFrozenNode: AllNodeType = {
  id: "node-frozen",
  type: "genericNode",
  position: { x: 200, y: 200 },
  data: {
    node: {
      template: {
        param4: {
          advanced: false,
          value: "frozen-value",
        },
      },
      frozen: true,
    },
    type: "FrozenNode",
  } as NodeDataType,
};

describe("useTweaksStore", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Reset mocks to default behavior
    mockGetChangesType.mockImplementation((value, template) => value);
    mockGetNodesWithDefaultValue.mockImplementation((nodes, tweaks) => nodes);
    mockGetLocalStorage.mockReturnValue("{}");
    mockFlowStore.getState.mockReturnValue({
      unselectAll: jest.fn(),
    });

    act(() => {
      useTweaksStore.setState({
        tweaks: {},
        nodes: [],
        currentFlowId: "",
      });
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useTweaksStore());

      expect(result.current.tweaks).toEqual({});
      expect(result.current.nodes).toEqual([]);
      expect(result.current.currentFlowId).toBe("");
    });
  });

  describe("setNodes", () => {
    it("should set nodes with array", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode, mockNode2]);
      });

      expect(result.current.nodes).toEqual([mockNode, mockNode2]);
    });

    it("should set nodes with function", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode]);
      });

      act(() => {
        result.current.setNodes((oldNodes) => [...oldNodes, mockNode2]);
      });

      expect(result.current.nodes).toEqual([mockNode, mockNode2]);
    });

    it("should call updateTweaks after setting nodes", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode]);
      });

      // updateTweaks should be called during setNodes
      expect(mockSetLocalStorage).toHaveBeenCalled();
    });

    it("should handle empty nodes array", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode]);
      });
      expect(result.current.nodes).toEqual([mockNode]);

      act(() => {
        result.current.setNodes([]);
      });
      expect(result.current.nodes).toEqual([]);
    });
  });

  describe("setNode", () => {
    beforeEach(() => {
      const { result } = renderHook(() => useTweaksStore());
      act(() => {
        result.current.setNodes([mockNode, mockNode2]);
      });
    });

    it("should update single node by id", () => {
      const { result } = renderHook(() => useTweaksStore());
      const updatedNode = {
        ...mockNode,
        data: { ...mockNode.data, type: "UpdatedNode" },
      };

      act(() => {
        result.current.setNode("node-1", updatedNode);
      });

      expect(result.current.nodes[0]).toEqual(updatedNode);
      expect(result.current.nodes[1]).toEqual(mockNode2);
    });

    it("should update node with function", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNode("node-1", (oldNode) => ({
          ...oldNode,
          data: { ...oldNode.data, type: "FunctionUpdated" },
        }));
      });

      expect(result.current.nodes[0].data.type).toBe("FunctionUpdated");
      expect(result.current.nodes[1]).toEqual(mockNode2);
    });

    it("should unfreeze frozen node when updated", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockFrozenNode]);
      });

      const updatedNode = {
        ...mockFrozenNode,
        data: { ...mockFrozenNode.data, type: "Unfrozen" },
      };

      act(() => {
        result.current.setNode("node-frozen", updatedNode);
      });

      expect((result.current.nodes[0].data as NodeDataType).node?.frozen).toBe(
        false,
      );
    });

    it("should handle updating non-existent node", () => {
      const { result } = renderHook(() => useTweaksStore());
      const originalNodes = result.current.nodes;

      act(() => {
        result.current.setNode("non-existent", mockNode);
      });

      expect(result.current.nodes).toEqual(originalNodes);
    });
  });

  describe("getNode", () => {
    beforeEach(() => {
      const { result } = renderHook(() => useTweaksStore());
      act(() => {
        result.current.setNodes([mockNode, mockNode2]);
      });
    });

    it("should return node by id", () => {
      const { result } = renderHook(() => useTweaksStore());

      const node = result.current.getNode("node-1");
      expect(node).toEqual(mockNode);
    });

    it("should return undefined for non-existent node", () => {
      const { result } = renderHook(() => useTweaksStore());

      const node = result.current.getNode("non-existent");
      expect(node).toBeUndefined();
    });

    it("should return correct node from multiple nodes", () => {
      const { result } = renderHook(() => useTweaksStore());

      const node1 = result.current.getNode("node-1");
      const node2 = result.current.getNode("node-2");

      expect(node1).toEqual(mockNode);
      expect(node2).toEqual(mockNode2);
    });
  });

  describe("initialSetup", () => {
    it("should set currentFlowId and nodes", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.initialSetup([mockNode], "flow-123");
      });

      expect(result.current.currentFlowId).toBe("flow-123");
      expect(mockFlowStore.getState().unselectAll).toHaveBeenCalled();
    });

    it("should load tweaks from localStorage", () => {
      const savedTweaks = { "node-1": { param1: "saved-value" } };
      mockGetLocalStorage.mockReturnValue(JSON.stringify(savedTweaks));

      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.initialSetup([mockNode], "flow-123");
      });

      expect(mockGetLocalStorage).toHaveBeenCalledWith("lf_tweaks_flow-123");
      expect(mockGetNodesWithDefaultValue).toHaveBeenCalledWith(
        [mockNode],
        savedTweaks,
      );
    });

    it("should handle empty localStorage", () => {
      mockGetLocalStorage.mockReturnValue(null);

      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.initialSetup([mockNode], "flow-456");
      });

      expect(mockGetNodesWithDefaultValue).toHaveBeenCalledWith([mockNode], {});
    });

    it("should call updateTweaks after initial setup", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.initialSetup([mockNode], "flow-789");
      });

      // updateTweaks should be called during initialSetup
      expect(mockSetLocalStorage).toHaveBeenCalled();
    });
  });

  describe("updateTweaks", () => {
    it("should generate tweaks from nodes", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [mockNode, mockNode2],
        });
        result.current.updateTweaks();
      });

      expect(mockGetChangesType).toHaveBeenCalledWith(
        "test-value",
        mockNode.data.node?.template.param1,
      );
      expect(mockGetChangesType).toHaveBeenCalledWith(
        "another-value",
        mockNode2.data.node?.template.param3,
      );
      expect(mockSetLocalStorage).toHaveBeenCalledWith(
        "lf_tweaks_test-flow",
        expect.any(String),
      );
    });

    it("should only include non-advanced parameters", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [mockNode],
        });
        result.current.updateTweaks();
      });

      // Should not call getChangesType for advanced parameters
      expect(mockGetChangesType).not.toHaveBeenCalledWith(
        "advanced-value",
        mockNode.data.node?.template.param2,
      );
    });

    it("should skip nodes that are not genericNode type", () => {
      const nonGenericNode = { ...mockNode, type: "customNode" };
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [nonGenericNode],
        });
        result.current.updateTweaks();
      });

      expect(result.current.tweaks).toEqual({});
    });

    it("should handle nodes without template", () => {
      const nodeWithoutTemplate = {
        ...mockNode,
        data: {
          ...mockNode.data,
          node: { ...mockNode.data.node, template: undefined },
        },
      };
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [nodeWithoutTemplate],
        });
        result.current.updateTweaks();
      });

      expect(result.current.tweaks).toEqual({});
    });

    it("should save tweaks to localStorage", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [mockNode],
        });
        result.current.updateTweaks();
      });

      expect(mockSetLocalStorage).toHaveBeenCalledWith(
        "lf_tweaks_test-flow",
        expect.stringContaining("node-1"),
      );
    });

    it("should update tweaks state", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "test-flow",
          nodes: [mockNode, mockNode2],
        });
        result.current.updateTweaks();
      });

      expect(result.current.tweaks).toHaveProperty("node-1");
      expect(result.current.tweaks).toHaveProperty("node-2");
    });
  });

  describe("state interactions", () => {
    it("should handle complex node updates", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.initialSetup([mockNode], "complex-flow");
      });

      act(() => {
        result.current.setNode("node-1", (node) => ({
          ...node,
          data: {
            ...node.data,
            node: {
              ...node.data.node,
              template: {
                ...node.data.node?.template,
                param1: {
                  advanced: false,
                  value: "updated-value",
                },
              },
            },
          } as NodeDataType,
        }));
      });

      expect(result.current.currentFlowId).toBe("complex-flow");
      expect(result.current.nodes[0].data.node?.template?.param1?.value).toBe(
        "updated-value",
      );
    });

    it("should maintain state consistency across multiple operations", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode]);
        result.current.setNode("node-1", {
          ...mockNode,
          position: { x: 50, y: 50 },
        });
      });

      expect(result.current.nodes).toHaveLength(1);
      expect(result.current.nodes[0].position).toEqual({ x: 50, y: 50 });
    });
  });

  describe("edge cases", () => {
    it("should handle empty nodes array in updateTweaks", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({ currentFlowId: "empty-flow" });
        result.current.setNodes([]);
      });

      expect(result.current.tweaks).toEqual({});
      expect(mockSetLocalStorage).toHaveBeenCalledWith(
        "lf_tweaks_empty-flow",
        "{}",
      );
    });

    it("should handle nodes with empty templates", () => {
      const emptyTemplateNode = {
        ...mockNode,
        data: {
          ...mockNode.data,
          node: {
            ...mockNode.data.node,
            template: {},
          },
        } as NodeDataType,
      };

      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        useTweaksStore.setState({
          currentFlowId: "empty-template-flow",
          nodes: [emptyTemplateNode],
        });
        result.current.updateTweaks();
      });

      expect(result.current.tweaks).toEqual({});
    });

    it("should handle malformed localStorage data gracefully", () => {
      mockGetLocalStorage.mockReturnValue("invalid-json");
      // Mock JSON.parse to handle the error gracefully
      const originalParse = JSON.parse;
      jest.spyOn(JSON, "parse").mockImplementation((str) => {
        if (str === "invalid-json") {
          throw new SyntaxError("Unexpected token");
        }
        return originalParse(str);
      });

      const { result } = renderHook(() => useTweaksStore());

      expect(() => {
        act(() => {
          result.current.initialSetup([mockNode], "error-flow");
        });
      }).toThrow();

      JSON.parse.mockRestore();
    });

    it("should handle multiple node updates with same ID", () => {
      const { result } = renderHook(() => useTweaksStore());

      act(() => {
        result.current.setNodes([mockNode]);
      });

      act(() => {
        result.current.setNode("node-1", {
          ...mockNode,
          position: { x: 1, y: 1 },
        });
        result.current.setNode("node-1", {
          ...mockNode,
          position: { x: 2, y: 2 },
        });
        result.current.setNode("node-1", {
          ...mockNode,
          position: { x: 3, y: 3 },
        });
      });

      expect(result.current.nodes[0].position).toEqual({ x: 3, y: 3 });
    });
  });
});
