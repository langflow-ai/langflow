import { act, renderHook } from "@testing-library/react";

jest.mock("lodash", () => ({
  cloneDeep: jest.fn((obj) => JSON.parse(JSON.stringify(obj))),
}));

jest.mock("@/constants/constants", () => ({
  SAVE_DEBOUNCE_TIME: 1000,
}));

jest.mock("../flowStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(() => ({
      nodes: [],
      edges: [],
      resetFlow: jest.fn(),
      setNodes: jest.fn(),
      setEdges: jest.fn(),
    })),
  },
}));

import type { FlowType } from "@/types/flow";
import useFlowsManagerStore from "../flowsManagerStore";

/**
 * ``currentFlow`` in this store is the *persisted* version of the flow the
 * editor diffs against: the unsaved-changes dialog reads its ``updated_at``
 * for the "Last saved" line, and ``useUnsavedChanges`` diffs its ``data``
 * against the canvas.
 *
 * The flow list that feeds ``setFlows`` is not always that shape. The app
 * header refetches ``GET /flows/?get_all=true&header_flows=true``, whose rows
 * are ``FlowHeader`` objects: no ``updated_at`` at all, and ``data`` nulled
 * for anything that is not a component.
 */
describe("useFlowsManagerStore saved-flow refresh", () => {
  const savedFlow = {
    id: "flow-1",
    name: "Test Flow",
    description: "Saved description",
    data: { nodes: [{ id: "node-1" }], edges: [], viewport: { x: 0, y: 0 } },
    is_component: false,
    locked: false,
    updated_at: "2026-08-19T10:00:00Z",
  } as unknown as FlowType;

  // What the header refetch actually lands: no updated_at, data nulled.
  const headerRow = {
    id: "flow-1",
    name: "Test Flow",
    description: "Saved description",
    data: null,
    is_component: false,
    folder_id: "folder-1",
  } as unknown as FlowType;

  const otherHeaderRow = {
    id: "flow-2",
    name: "Another Flow",
    data: null,
    is_component: false,
  } as unknown as FlowType;

  beforeEach(() => {
    jest.clearAllMocks();
    act(() => {
      useFlowsManagerStore.getState().resetStore();
    });
  });

  it("keeps updated_at when a header-only list refresh lands", () => {
    const { result } = renderHook(() => useFlowsManagerStore());

    act(() => {
      result.current.setCurrentFlow(savedFlow);
    });
    act(() => {
      result.current.setFlows([headerRow, otherHeaderRow]);
    });

    expect(result.current.currentFlow?.updated_at).toBe("2026-08-19T10:00:00Z");
  });

  it("keeps the persisted graph when a header-only list refresh lands", () => {
    const { result } = renderHook(() => useFlowsManagerStore());

    act(() => {
      result.current.setCurrentFlow(savedFlow);
    });
    act(() => {
      result.current.setFlows([headerRow, otherHeaderRow]);
    });

    expect(result.current.currentFlow?.data).toEqual(savedFlow.data);
    expect(result.current.currentFlow?.locked).toBe(false);
  });

  it("still applies fields the refreshed row does carry", () => {
    const { result } = renderHook(() => useFlowsManagerStore());

    act(() => {
      result.current.setCurrentFlow(savedFlow);
    });
    act(() => {
      result.current.setFlows([
        { ...headerRow, name: "Renamed elsewhere" },
        otherHeaderRow,
      ]);
    });

    expect(result.current.currentFlow?.name).toBe("Renamed elsewhere");
    expect(result.current.currentFlow?.folder_id).toBe("folder-1");
  });

  it("prefers a full row over the previously stored one", () => {
    const { result } = renderHook(() => useFlowsManagerStore());

    act(() => {
      result.current.setCurrentFlow(savedFlow);
    });
    act(() => {
      result.current.setFlows([
        {
          ...savedFlow,
          data: { nodes: [], edges: [] },
          updated_at: "2026-08-19T11:00:00Z",
        } as unknown as FlowType,
      ]);
    });

    expect(result.current.currentFlow?.data).toEqual({ nodes: [], edges: [] });
    expect(result.current.currentFlow?.updated_at).toBe("2026-08-19T11:00:00Z");
  });

  it("clears the current flow when it is gone from the refreshed list", () => {
    const { result } = renderHook(() => useFlowsManagerStore());

    act(() => {
      result.current.setCurrentFlow(savedFlow);
    });
    act(() => {
      result.current.setFlows([otherHeaderRow]);
    });

    expect(result.current.currentFlow).toBeUndefined();
  });
});
