import { act, renderHook } from "@testing-library/react";

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
  ENABLE_INSPECTION_PANEL: false,
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
  trackDataLoaded: jest.fn(),
  trackFlowBuild: jest.fn(),
}));

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
  useDarkStore: { getState: () => ({ refreshStars: jest.fn() }) },
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
  useGlobalVariablesStore: { getState: () => ({ globalVariables: {} }) },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: {
    getState: () => ({ initialSetup: jest.fn(), tweaks: {} }),
  },
}));

jest.mock("../typesStore", () => ({
  useTypesStore: { getState: () => ({ templates: {}, types: {} }) },
}));

jest.mock("@/utils/utils", () => ({
  brokenEdgeMessage: jest.fn(),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  buildPositionDictionary: jest.fn(() => ({})),
  checkChatInput: jest.fn(),
  cleanEdges: jest.fn(() => ({ edges: [], brokenEdges: [] })),
  getConnectedSubgraph: jest.fn(),
  getHandleId: jest.fn(),
  getNodeId: jest.fn(),
  scapedJSONStringfy: jest.fn(),
  scapeJSONParse: jest.fn(),
  unselectAllNodesEdges: jest.fn(),
  updateGroupRecursion: jest.fn(),
  validateEdge: jest.fn(),
  validateNodes: jest.fn(),
}));

jest.mock("@/utils/storeUtils", () => ({
  getInputsAndOutputs: jest.fn(() => ({ inputs: [], outputs: [] })),
}));

jest.mock("@/utils/buildUtils", () => ({
  buildFlowVerticesWithFallback: jest.fn(),
}));

import type { FlowType } from "@/types/flow";
import useFlowStore from "../flowStore";

describe("useFlowStore - lasso mode", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    act(() => {
      useFlowStore.setState({ isLassoMode: false });
    });
  });

  describe("initial state", () => {
    it("defaults to false", () => {
      const { result } = renderHook(() => useFlowStore((s) => s.isLassoMode));
      expect(result.current).toBe(false);
    });
  });

  describe("setIsLassoMode", () => {
    it("sets lasso mode to true", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setIsLassoMode(true);
      });

      expect(result.current.isLassoMode).toBe(true);
    });

    it("sets lasso mode to false", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setIsLassoMode(false);
      });

      expect(result.current.isLassoMode).toBe(false);
    });

    it("toggles correctly across multiple calls", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.setIsLassoMode(true);
      });
      expect(result.current.isLassoMode).toBe(true);

      act(() => {
        result.current.setIsLassoMode(false);
      });
      expect(result.current.isLassoMode).toBe(false);

      act(() => {
        result.current.setIsLassoMode(true);
      });
      expect(result.current.isLassoMode).toBe(true);
    });
  });

  describe("resetFlowState", () => {
    it("resets isLassoMode to false", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.resetFlowState();
      });

      expect(result.current.isLassoMode).toBe(false);
    });

    it("leaves isLassoMode false when it was already false", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.resetFlowState();
      });

      expect(result.current.isLassoMode).toBe(false);
    });
  });

  describe("resetFlow", () => {
    const mockFlow: FlowType = {
      id: "flow-1",
      name: "Test Flow",
      description: "",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    };

    it("resets isLassoMode to false when switching flows", () => {
      act(() => {
        useFlowStore.setState({ isLassoMode: true });
      });

      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.resetFlow(mockFlow);
      });

      expect(result.current.isLassoMode).toBe(false);
    });

    it("leaves isLassoMode false when already false before switching flows", () => {
      const { result } = renderHook(() => useFlowStore());

      act(() => {
        result.current.resetFlow(mockFlow);
      });

      expect(result.current.isLassoMode).toBe(false);
    });
  });
});
