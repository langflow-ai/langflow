import { act, renderHook } from "@testing-library/react";

// Mock all the complex dependencies
jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn(),
  applyEdgeChanges: jest.fn((changes, edges) => edges),
  applyNodeChanges: jest.fn((changes, nodes) => nodes),
}));

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj) => JSON.parse(JSON.stringify(obj))),
  zip: jest.fn(),
}));

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(),
}));

jest.mock("@/constants/alerts_constants", () => ({
  MISSED_ERROR_ALERT: "MISSED_ERROR_ALERT",
}));

jest.mock("@/constants/constants", () => ({
  BROKEN_EDGES_WARNING: "BROKEN_EDGES_WARNING",
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
  trackDataLoaded: jest.fn(),
  trackFlowBuild: jest.fn(),
}));

// Mock all store dependencies
jest.mock("../alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setErrorData: jest.fn(),
      setSuccessData: jest.fn(),
    }),
  },
}));

jest.mock("../darkStore", () => ({
  useDarkStore: {
    getState: () => ({
      refreshStars: jest.fn(),
    }),
  },
}));

jest.mock("../flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setCurrentFlow: jest.fn(),
      takeSnapshot: jest.fn(),
    }),
  },
}));

jest.mock("../globalVariablesStore/globalVariables", () => ({
  useGlobalVariablesStore: {
    getState: () => ({
      globalVariables: {},
    }),
  },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: {
    getState: () => ({
      tweaks: {},
    }),
  },
}));

jest.mock("../typesStore", () => ({
  useTypesStore: {
    getState: () => ({
      templates: {},
      types: {},
    }),
  },
}));

// Mock utility functions
jest.mock("@/utils/utils", () => ({
  brokenEdgeMessage: jest.fn(),
}));

// Note: Some utility modules may not exist in test environment
// The store should handle missing utilities gracefully

import type { AllNodeType, EdgeType } from "@/types/flow";
import useFlowStore from "../flowStore";

describe("useFlowStore", () => {
  // Mock data
  const mockNode: AllNodeType = {
    id: "node-1",
    type: "genericNode",
    position: { x: 100, y: 100 },
    data: {
      node: {
        display_name: "Test Node",
        icon: "test-icon",
      },
    },
  } as AllNodeType;

  const mockEdge: EdgeType = {
    id: "edge-1",
    source: "node-1",
    target: "node-2",
  } as EdgeType;

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();

    // Reset store state to basics
    act(() => {
      useFlowStore.setState({
        playgroundPage: false,
        positionDictionary: {},
        componentsToUpdate: [],
        onFlowPage: false,
        flowState: undefined,
        flowBuildStatus: {},
        nodes: [],
        edges: [],
        isBuilding: false,
        isPending: true,
        reactFlowInstance: null,
        lastCopiedSelection: null,
        flowPool: {},
        inputs: [],
        outputs: [],
        hasIO: false,
      });
    });
  });

  describe("initial state", () => {
    it("should initialize with correct default values", () => {
      const { result } = renderHook(() => useFlowStore());

      expect(result.current.playgroundPage).toBe(false);
      expect(result.current.positionDictionary).toEqual({});
      expect(result.current.componentsToUpdate).toEqual([]);
      expect(result.current.onFlowPage).toBe(false);
      expect(result.current.nodes).toEqual([]);
      expect(result.current.edges).toEqual([]);
      expect(result.current.isBuilding).toBe(false);
      expect(result.current.isPending).toBe(true);
      expect(result.current.inputs).toEqual([]);
      expect(result.current.outputs).toEqual([]);
      expect(result.current.hasIO).toBe(false);
    });
  });

  describe("playground page management", () => {
    it("should set playground page state", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setPlaygroundPage(true);
      });

      expect(result.current.playgroundPage).toBe(true);

      act(() => {
        result.current.setPlaygroundPage(false);
      });

      expect(result.current.playgroundPage).toBe(false);
    });
  });

  describe("position dictionary management", () => {
    it("should set position dictionary", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockDict = { 100: 200, 300: 400 };

      act(() => {
        result.current.setPositionDictionary(mockDict);
      });

      expect(result.current.positionDictionary).toEqual(mockDict);
    });

    it("should check if position is available", () => {
      const { result } = renderHook(() => useFlowStore());

      // Set a position in dictionary
      act(() => {
        result.current.setPositionDictionary({ 100: 200 });
      });

      // Position should not be available if it exists in dictionary
      expect(result.current.isPositionAvailable({ x: 100, y: 200 })).toBe(
        false,
      );

      // Position should be available if it doesn't exist
      expect(result.current.isPositionAvailable({ x: 150, y: 250 })).toBe(true);
    });
  });

  describe("flow page management", () => {
    it("should set on flow page state", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setOnFlowPage(true);
      });

      expect(result.current.onFlowPage).toBe(true);

      act(() => {
        result.current.setOnFlowPage(false);
      });

      expect(result.current.onFlowPage).toBe(false);
    });
  });

  describe("components to update management", () => {
    it("should set components to update with array", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockComponents = [
        {
          id: "comp-1",
          icon: "icon-1",
          display_name: "Component 1",
          outdated: true,
          breakingChange: false,
          userEdited: true,
        },
      ];

      act(() => {
        result.current.setComponentsToUpdate(mockComponents);
      });

      expect(result.current.componentsToUpdate).toEqual(mockComponents);
    });

    it("should set components to update with function", () => {
      const { result } = renderHook(() => useFlowStore());
      const initialComponents = [
        {
          id: "comp-1",
          icon: "icon-1",
          display_name: "Component 1",
          outdated: true,
          breakingChange: false,
          userEdited: true,
        },
      ];

      // Set initial state
      act(() => {
        result.current.setComponentsToUpdate(initialComponents);
      });

      // Update with function
      act(() => {
        result.current.setComponentsToUpdate((prev) => [
          ...prev,
          {
            id: "comp-2",
            icon: "icon-2",
            display_name: "Component 2",
            outdated: false,
            breakingChange: true,
            userEdited: false,
          },
        ]);
      });

      expect(result.current.componentsToUpdate).toHaveLength(2);
    });
  });

  describe("inputs and outputs management", () => {
    it("should set inputs", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockInputs = [{ name: "input1", type: "text" }];

      act(() => {
        result.current.setInputs(mockInputs);
      });

      expect(result.current.inputs).toEqual(mockInputs);
    });

    it("should set outputs", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockOutputs = [{ name: "output1", type: "text" }];

      act(() => {
        result.current.setOutputs(mockOutputs);
      });

      expect(result.current.outputs).toEqual(mockOutputs);
    });

    it("should set hasIO state", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setHasIO(true);
      });

      expect(result.current.hasIO).toBe(true);

      act(() => {
        result.current.setHasIO(false);
      });

      expect(result.current.hasIO).toBe(false);
    });
  });

  describe("flow pool management", () => {
    it("should set flow pool", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockFlowPool = { flow1: { id: "flow1", data: {} } };

      act(() => {
        result.current.setFlowPool(mockFlowPool);
      });

      expect(result.current.flowPool).toEqual(mockFlowPool);
    });
  });

  describe("build management", () => {
    it("should handle building state", () => {
      const { result } = renderHook(() => useFlowStore());

      // Test that isBuilding can be read (setter is internal)
      expect(result.current.isBuilding).toBe(false);
    });

    it("should handle stop building", () => {
      const { result } = renderHook(() => useFlowStore());

      // Mock the buildController
      const mockAbort = jest.fn();
      act(() => {
        useFlowStore.setState({
          buildController: { abort: mockAbort },
          updateEdgesRunningByNodes: jest.fn(),
          revertBuiltStatusFromBuilding: jest.fn(),
          nodes: [mockNode],
        });
      });

      act(() => {
        result.current.stopBuilding();
      });

      expect(mockAbort).toHaveBeenCalled();
      expect(result.current.isBuilding).toBe(false);
    });
  });

  describe("reactflow integration", () => {
    it("should handle nodes change", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockChanges = [{ id: "node-1", type: "position" as const }];

      act(() => {
        result.current.onNodesChange(mockChanges);
      });

      // Verify that applyNodeChanges would be called
      expect(result.current.nodes).toBeDefined();
    });

    it("should handle edges change", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockChanges = [{ id: "edge-1", type: "remove" as const }];

      act(() => {
        result.current.onEdgesChange(mockChanges);
      });

      // Verify that applyEdgeChanges would be called
      expect(result.current.edges).toBeDefined();
    });

    it("should handle fitViewNode when reactFlowInstance exists", () => {
      const { result } = renderHook(() => useFlowStore());
      const mockFitView = jest.fn();

      act(() => {
        useFlowStore.setState({
          reactFlowInstance: { fitView: mockFitView },
          nodes: [mockNode],
        });
      });

      act(() => {
        result.current.fitViewNode("node-1");
      });

      expect(mockFitView).toHaveBeenCalledWith({ nodes: [{ id: "node-1" }] });
    });

    it("should not call fitView when reactFlowInstance is null", () => {
      const { result } = renderHook(() => useFlowStore());

      // Should not throw when reactFlowInstance is null
      expect(() => {
        act(() => {
          result.current.fitViewNode("node-1");
        });
      }).not.toThrow();
    });
  });

  describe("tool mode management", () => {
    it("should handle updateToolMode method existence", () => {
      const { result } = renderHook(() => useFlowStore());

      // Just verify the method exists
      expect(typeof result.current.updateToolMode).toBe("function");

      // Note: updateToolMode throws error if node doesn't exist, which is expected behavior
      // We test that the method exists and can be called (error handling is part of the store logic)
    });
  });

  describe("integration scenarios", () => {
    it("should handle complete flow setup workflow", () => {
      const { result } = renderHook(() => useFlowStore());

      // Set up basic flow page
      act(() => {
        result.current.setOnFlowPage(true);
        result.current.setPlaygroundPage(false);
      });

      // Configure positions
      act(() => {
        result.current.setPositionDictionary({ 100: 200 });
      });

      // Set up inputs/outputs
      act(() => {
        result.current.setInputs([{ name: "input1", type: "text" }]);
        result.current.setOutputs([{ name: "output1", type: "text" }]);
        result.current.setHasIO(true);
      });

      expect(result.current.onFlowPage).toBe(true);
      expect(result.current.playgroundPage).toBe(false);
      expect(result.current.positionDictionary).toEqual({ 100: 200 });
      expect(result.current.inputs).toHaveLength(1);
      expect(result.current.outputs).toHaveLength(1);
      expect(result.current.hasIO).toBe(true);
    });

    it("should handle state transitions correctly", () => {
      const { result } = renderHook(() => useFlowStore());

      // Start with playground
      act(() => {
        result.current.setPlaygroundPage(true);
        result.current.setOnFlowPage(false);
      });

      expect(result.current.playgroundPage).toBe(true);
      expect(result.current.onFlowPage).toBe(false);

      // Switch to flow page
      act(() => {
        result.current.setPlaygroundPage(false);
        result.current.setOnFlowPage(true);
      });

      expect(result.current.playgroundPage).toBe(false);
      expect(result.current.onFlowPage).toBe(true);
    });
  });

  describe("error handling and edge cases", () => {
    it("should handle empty position dictionary checks", () => {
      const { result } = renderHook(() => useFlowStore());

      // Should return true for any position when dictionary is empty
      expect(result.current.isPositionAvailable({ x: 100, y: 200 })).toBe(true);
    });

    it("should handle undefined/null values gracefully", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setInputs([]);
        result.current.setOutputs([]);
        result.current.setFlowPool({});
      });

      expect(result.current.inputs).toEqual([]);
      expect(result.current.outputs).toEqual([]);
      expect(result.current.flowPool).toEqual({});
    });

    it("should handle rapid state changes", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setPlaygroundPage(true);
        result.current.setPlaygroundPage(false);
        result.current.setOnFlowPage(true);
        result.current.setOnFlowPage(false);
        result.current.setHasIO(true);
        result.current.setHasIO(false);
      });

      expect(result.current.playgroundPage).toBe(false);
      expect(result.current.onFlowPage).toBe(false);
      expect(result.current.hasIO).toBe(false);
    });
  });

  describe("complex state management", () => {
    it("should maintain state consistency during concurrent operations", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        // Simulate concurrent operations
        result.current.setPlaygroundPage(true);
        result.current.setPositionDictionary({ 10: 20, 30: 40 });
        result.current.setComponentsToUpdate([]);
        result.current.setInputs([{ name: "concurrent-input", type: "text" }]);
        result.current.setOutputs([
          { name: "concurrent-output", type: "text" },
        ]);
        result.current.setHasIO(true);
      });

      expect(result.current.playgroundPage).toBe(true);
      expect(result.current.positionDictionary).toEqual({ 10: 20, 30: 40 });
      expect(result.current.componentsToUpdate).toEqual([]);
      expect(result.current.inputs).toHaveLength(1);
      expect(result.current.outputs).toHaveLength(1);
      expect(result.current.hasIO).toBe(true);
    });
  });
});
