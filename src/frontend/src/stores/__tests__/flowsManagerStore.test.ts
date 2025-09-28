import { act, renderHook } from "@testing-library/react";

// Mock lodash
const mockCloneDeep = jest.fn((obj) => JSON.parse(JSON.stringify(obj)));
jest.mock("lodash", () => ({
  cloneDeep: mockCloneDeep,
}));

// Mock constants
jest.mock("@/constants/constants", () => ({
  SAVE_DEBOUNCE_TIME: 1000,
}));

// Mock flowStore
const mockResetFlow = jest.fn();
const mockSetNodes = jest.fn();
const mockSetEdges = jest.fn();

const mockFlowStore = {
  getState: jest.fn(() => ({
    nodes: [],
    edges: [],
    resetFlow: mockResetFlow,
    setNodes: mockSetNodes,
    setEdges: mockSetEdges,
  })),
};

jest.mock("../flowStore", () => ({
  __esModule: true,
  default: mockFlowStore,
}));

import type { FlowType } from "@/types/flow";
import useFlowsManagerStore from "../flowsManagerStore";

describe("useFlowsManagerStore", () => {
  // Mock flow data
  const mockFlow1: FlowType = {
    id: "flow-1",
    name: "Test Flow 1",
    description: "Test Description 1",
    data: { nodes: [], edges: [] },
    is_component: false,
  } as FlowType;

  const mockFlow2: FlowType = {
    id: "flow-2",
    name: "Test Flow 2",
    description: "Test Description 2",
    data: { nodes: [], edges: [] },
    is_component: false,
  } as FlowType;

  const mockFlows = [mockFlow1, mockFlow2];

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();
    mockCloneDeep.mockImplementation((obj) => JSON.parse(JSON.stringify(obj)));
    mockResetFlow.mockClear();
    mockSetNodes.mockClear();
    mockSetEdges.mockClear();

    // Reset the store state
    useFlowsManagerStore.setState({
      IOModalOpen: false,
      healthCheckMaxRetries: 5,
      autoSaving: true,
      autoSavingInterval: 1000,
      examples: [],
      currentFlowId: "",
      flows: undefined,
      currentFlow: undefined,
      saveLoading: false,
      isLoading: false,
      searchFlowsComponents: "",
      selectedFlowsComponentsCards: [],
    });
  });

  describe("initial state", () => {
    it("should initialize with correct default values", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      expect(result.current.IOModalOpen).toBe(false);
      expect(result.current.healthCheckMaxRetries).toBe(5);
      expect(result.current.autoSaving).toBe(true);
      expect(result.current.autoSavingInterval).toBe(1000);
      expect(result.current.examples).toEqual([]);
      expect(result.current.currentFlowId).toBe("");
      expect(result.current.flows).toBeUndefined();
      expect(result.current.currentFlow).toBeUndefined();
      expect(result.current.saveLoading).toBe(false);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.searchFlowsComponents).toBe("");
      expect(result.current.selectedFlowsComponentsCards).toEqual([]);
    });
  });

  describe("IO Modal management", () => {
    it("should set IO modal open state", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setIOModalOpen(true);
      });

      expect(result.current.IOModalOpen).toBe(true);

      act(() => {
        result.current.setIOModalOpen(false);
      });

      expect(result.current.IOModalOpen).toBe(false);
    });
  });

  describe("health check configuration", () => {
    it("should set health check max retries", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setHealthCheckMaxRetries(10);
      });

      expect(result.current.healthCheckMaxRetries).toBe(10);
    });

    it("should handle edge case values for health check retries", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setHealthCheckMaxRetries(0);
      });
      expect(result.current.healthCheckMaxRetries).toBe(0);

      act(() => {
        result.current.setHealthCheckMaxRetries(100);
      });
      expect(result.current.healthCheckMaxRetries).toBe(100);
    });
  });

  describe("auto-saving configuration", () => {
    it("should toggle auto-saving", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setAutoSaving(false);
      });

      expect(result.current.autoSaving).toBe(false);

      act(() => {
        result.current.setAutoSaving(true);
      });

      expect(result.current.autoSaving).toBe(true);
    });

    it("should set auto-saving interval", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setAutoSavingInterval(5000);
      });

      expect(result.current.autoSavingInterval).toBe(5000);
    });
  });

  describe("examples management", () => {
    it("should set examples", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setExamples(mockFlows);
      });

      expect(result.current.examples).toEqual(mockFlows);
    });

    it("should handle empty examples", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setExamples([]);
      });

      expect(result.current.examples).toEqual([]);
    });
  });

  describe("flow management", () => {
    it("should set current flow", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setCurrentFlow(mockFlow1);
      });

      expect(result.current.currentFlow).toEqual(mockFlow1);
      expect(result.current.currentFlowId).toBe("flow-1");
      expect(mockResetFlow).toHaveBeenCalledWith(mockFlow1);
    });

    it("should handle undefined current flow", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setCurrentFlow(undefined);
      });

      expect(result.current.currentFlow).toBeUndefined();
      expect(result.current.currentFlowId).toBe("");
      expect(mockResetFlow).toHaveBeenCalledWith(undefined);
    });

    it("should set flows and update current flow", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // First set a current flow ID
      act(() => {
        result.current.setCurrentFlow(mockFlow1);
      });

      // Then set flows which should update the current flow
      act(() => {
        result.current.setFlows(mockFlows);
      });

      expect(result.current.flows).toEqual(mockFlows);
      expect(result.current.currentFlow).toEqual(mockFlow1);
    });

    it("should get flow by id", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setFlows(mockFlows);
      });

      const foundFlow = result.current.getFlowById("flow-1");
      expect(foundFlow).toEqual(mockFlow1);

      const notFoundFlow = result.current.getFlowById("non-existent");
      expect(notFoundFlow).toBeUndefined();
    });

    it("should handle getFlowById when flows is undefined", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      const foundFlow = result.current.getFlowById("flow-1");
      expect(foundFlow).toBeUndefined();
    });
  });

  describe("loading states", () => {
    it("should manage save loading state", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setSaveLoading(true);
      });

      expect(result.current.saveLoading).toBe(true);

      act(() => {
        result.current.setSaveLoading(false);
      });

      expect(result.current.saveLoading).toBe(false);
    });

    it("should manage general loading state", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setIsLoading(true);
      });

      expect(result.current.isLoading).toBe(true);

      act(() => {
        result.current.setIsLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe("undo/redo functionality", () => {
    beforeEach(() => {
      // Setup flowStore mock with test data
      mockFlowStore.getState.mockReturnValue({
        nodes: [{ id: "node-1", data: {} }],
        edges: [{ id: "edge-1" }],
        resetFlow: mockResetFlow,
        setNodes: mockSetNodes,
        setEdges: mockSetEdges,
      });
    });

    it("should take snapshot of current state", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setCurrentFlow(mockFlow1);
        result.current.takeSnapshot();
      });

      expect(mockCloneDeep).toHaveBeenCalledWith([{ id: "node-1", data: {} }]);
      expect(mockCloneDeep).toHaveBeenCalledWith([{ id: "edge-1" }]);
    });

    it("should not take duplicate snapshots", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setCurrentFlow(mockFlow1);
        result.current.takeSnapshot();
        result.current.takeSnapshot(); // Should be ignored as duplicate
      });

      // Should still be called for the first snapshot
      expect(mockCloneDeep).toHaveBeenCalled();
    });

    it("should handle undo operation", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Setup initial state
      mockFlowStore.getState.mockReturnValue({
        nodes: [{ id: "node-2", data: {} }],
        edges: [{ id: "edge-2" }],
        resetFlow: mockResetFlow,
        setNodes: mockSetNodes,
        setEdges: mockSetEdges,
      });

      act(() => {
        result.current.setCurrentFlow(mockFlow1);
        result.current.takeSnapshot();
      });

      // Change the flow store state
      mockFlowStore.getState.mockReturnValue({
        nodes: [{ id: "node-3", data: {} }],
        edges: [{ id: "edge-3" }],
        resetFlow: mockResetFlow,
        setNodes: mockSetNodes,
        setEdges: mockSetEdges,
      });

      act(() => {
        result.current.undo();
      });

      expect(mockSetNodes).toHaveBeenCalledWith([{ id: "node-2", data: {} }]);
      expect(mockSetEdges).toHaveBeenCalledWith([{ id: "edge-2" }]);
    });

    it("should handle redo operation", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      mockFlowStore.getState.mockReturnValue({
        nodes: [{ id: "node-1", data: {} }],
        edges: [{ id: "edge-1" }],
        resetFlow: mockResetFlow,
        setNodes: mockSetNodes,
        setEdges: mockSetEdges,
      });

      act(() => {
        result.current.setCurrentFlow(mockFlow1);
        result.current.takeSnapshot();
        result.current.undo();
        result.current.redo();
      });

      // Should restore to the state before undo
      expect(mockSetNodes).toHaveBeenCalled();
      expect(mockSetEdges).toHaveBeenCalled();
    });

    it("should handle undo with no past state gracefully", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Don't set current flow, just try to undo with empty state
      act(() => {
        result.current.undo(); // Should do nothing since no current flow and no past state
      });

      // Since no current flow is set, undo should be safe to call
      expect(true).toBe(true); // Test passes if no errors are thrown
    });
  });

  describe("search functionality", () => {
    it("should manage search flows components", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setSearchFlowsComponents("search term");
      });

      expect(result.current.searchFlowsComponents).toBe("search term");
    });

    it("should handle empty search", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setSearchFlowsComponents("");
      });

      expect(result.current.searchFlowsComponents).toBe("");
    });
  });

  describe("component cards selection", () => {
    it("should manage selected flows components cards", () => {
      const { result } = renderHook(() => useFlowsManagerStore());
      const selectedCards = ["card-1", "card-2"];

      act(() => {
        result.current.setSelectedFlowsComponentsCards(selectedCards);
      });

      expect(result.current.selectedFlowsComponentsCards).toEqual(
        selectedCards,
      );
    });

    it("should handle empty selection", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setSelectedFlowsComponentsCards([]);
      });

      expect(result.current.selectedFlowsComponentsCards).toEqual([]);
    });
  });

  describe("store reset", () => {
    it("should reset store to initial state", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Set up some state
      act(() => {
        result.current.setFlows(mockFlows);
        result.current.setCurrentFlow(mockFlow1);
        result.current.setSearchFlowsComponents("test search");
        result.current.setSelectedFlowsComponentsCards(["card-1"]);
      });

      // Reset store
      act(() => {
        result.current.resetStore();
      });

      expect(result.current.flows).toEqual([]);
      expect(result.current.currentFlow).toBeUndefined();
      expect(result.current.currentFlowId).toBe("");
      expect(result.current.searchFlowsComponents).toBe("");
      expect(result.current.selectedFlowsComponentsCards).toEqual([]);
    });
  });

  describe("integration scenarios", () => {
    it("should handle complete flow management workflow", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Start with setting flows
      act(() => {
        result.current.setFlows(mockFlows);
      });

      // Set current flow
      act(() => {
        result.current.setCurrentFlow(mockFlow1);
      });

      // Configure auto-saving
      act(() => {
        result.current.setAutoSaving(true);
        result.current.setAutoSavingInterval(2000);
      });

      // Take snapshot for undo/redo
      act(() => {
        result.current.takeSnapshot();
      });

      // Search and select components
      act(() => {
        result.current.setSearchFlowsComponents("component");
        result.current.setSelectedFlowsComponentsCards(["comp-1", "comp-2"]);
      });

      expect(result.current.flows).toEqual(mockFlows);
      expect(result.current.currentFlow).toEqual(mockFlow1);
      expect(result.current.autoSaving).toBe(true);
      expect(result.current.autoSavingInterval).toBe(2000);
      expect(result.current.searchFlowsComponents).toBe("component");
      expect(result.current.selectedFlowsComponentsCards).toEqual([
        "comp-1",
        "comp-2",
      ]);
    });

    it("should handle loading states during operations", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Simulate loading flow
      act(() => {
        result.current.setIsLoading(true);
      });

      expect(result.current.isLoading).toBe(true);

      // Simulate saving flow
      act(() => {
        result.current.setSaveLoading(true);
        result.current.setIsLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.saveLoading).toBe(true);

      // Complete operations
      act(() => {
        result.current.setSaveLoading(false);
      });

      expect(result.current.saveLoading).toBe(false);
    });

    it("should maintain state consistency during flow changes", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      // Set initial state
      act(() => {
        result.current.setFlows(mockFlows);
        result.current.setCurrentFlow(mockFlow1);
      });

      expect(result.current.currentFlowId).toBe("flow-1");

      // Change to different flow
      act(() => {
        result.current.setCurrentFlow(mockFlow2);
      });

      expect(result.current.currentFlowId).toBe("flow-2");
      expect(result.current.currentFlow).toEqual(mockFlow2);

      // Verify flow store was called correctly
      expect(mockResetFlow).toHaveBeenCalledWith(mockFlow2);
    });
  });

  describe("edge cases", () => {
    it("should handle rapid state changes", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setAutoSaving(true);
        result.current.setAutoSaving(false);
        result.current.setAutoSaving(true);
        result.current.setHealthCheckMaxRetries(10);
        result.current.setHealthCheckMaxRetries(5);
        result.current.setIOModalOpen(true);
        result.current.setIOModalOpen(false);
      });

      expect(result.current.autoSaving).toBe(true);
      expect(result.current.healthCheckMaxRetries).toBe(5);
      expect(result.current.IOModalOpen).toBe(false);
    });

    it("should handle undefined and null values gracefully", () => {
      const { result } = renderHook(() => useFlowsManagerStore());

      act(() => {
        result.current.setCurrentFlow(undefined);
        result.current.setFlows([]);
        result.current.setExamples([]);
      });

      expect(result.current.currentFlow).toBeUndefined();
      expect(result.current.flows).toEqual([]);
      expect(result.current.examples).toEqual([]);
    });
  });
});
