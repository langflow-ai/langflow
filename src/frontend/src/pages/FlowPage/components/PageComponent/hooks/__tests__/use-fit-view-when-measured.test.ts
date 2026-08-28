import { act, renderHook } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFitViewWhenMeasured } from "../use-fit-view-when-measured";

const mockFitView = jest.fn();
let mockNodesInitialized = false;
let mockCanvasSize = { width: 1000, height: 800 };

jest.mock("@xyflow/react", () => ({
  useNodesInitialized: () => mockNodesInitialized,
  useReactFlow: () => ({ fitView: mockFitView }),
  useStore: (selector: (state: unknown) => unknown) => selector(mockCanvasSize),
}));

const FIT_VIEW_OPTIONS = { minZoom: 0.25, maxZoom: 2 };

function setNodesInitialized(initialized: boolean) {
  mockNodesInitialized = initialized;
}

function openFlow(id: string) {
  useFlowsManagerStore.setState({ currentFlowId: id });
}

describe("useFitViewWhenMeasured", () => {
  beforeEach(() => {
    mockFitView.mockClear();
    setNodesInitialized(false);
    mockCanvasSize = { width: 1000, height: 800 };
    useFlowStore.setState({ fitViewRequest: { id: 0 } });
    useFlowsManagerStore.setState({ currentFlowId: "" });
  });

  it("should not fit while the canvas holds no flow", () => {
    setNodesInitialized(true);
    renderHook(() => useFitViewWhenMeasured(FIT_VIEW_OPTIONS));

    expect(mockFitView).not.toHaveBeenCalled();
  });

  // The bug: ReactFlow resolves a queued fit on the first internals batch, so a
  // fit that runs while nodes are still unmeasured silently drops them from the
  // bounding box and the flow opens zoomed in on a subset.
  it("should hold the fit until every node is measured", () => {
    openFlow("flow-1");
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    expect(mockFitView).not.toHaveBeenCalled();

    setNodesInitialized(true);
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
    expect(mockFitView).toHaveBeenCalledWith(FIT_VIEW_OPTIONS);
  });

  // Navigating inside the app reuses this canvas and can skip
  // useApplyFlowToCanvas entirely, so the flow id has to imply a fit.
  it("should fit when a flow lands on an already mounted canvas", () => {
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    act(() => {
      openFlow("flow-1");
    });
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
  });

  it("should fit again when the canvas switches flows", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );
    expect(mockFitView).toHaveBeenCalledTimes(1);

    setNodesInitialized(false);
    act(() => {
      openFlow("flow-2");
    });
    rerender();
    expect(mockFitView).toHaveBeenCalledTimes(1);

    setNodesInitialized(true);
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(2);
  });

  // Version restore replaces the graph under the same flow id.
  it("should fit again for an explicit request on the same flow", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );
    expect(mockFitView).toHaveBeenCalledTimes(1);

    act(() => {
      useFlowStore.getState().requestFitView();
    });
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(2);
  });

  it("should collapse requests that arrive before the nodes are measured", () => {
    openFlow("flow-1");
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    act(() => {
      useFlowStore.getState().requestFitView();
      useFlowStore.getState().requestFitView();
    });
    setNodesInitialized(true);
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
  });

  // The welcome overlay hides the sidebar while it is up: the canvas is wider
  // for the fit and narrows the moment the overlay closes, leaving the graph
  // framed for a viewport it no longer has.
  it("should refit when the canvas resizes right after opening the flow", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );
    expect(mockFitView).toHaveBeenCalledTimes(1);

    mockCanvasSize = { width: 780, height: 800 };
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(2);
  });

  it("should leave the viewport alone when the canvas resizes later", () => {
    jest.useFakeTimers();
    try {
      openFlow("flow-1");
      setNodesInitialized(true);
      const { rerender } = renderHook(() =>
        useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
      );
      expect(mockFitView).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(5000);
      mockCanvasSize = { width: 780, height: 800 };
      rerender();

      expect(mockFitView).toHaveBeenCalledTimes(1);
    } finally {
      jest.useRealTimers();
    }
  });

  it("should fit once per request, not on every re-render", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    rerender();
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
  });

  it("should not refit when options identity changes without a new request", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(
      ({ options }) => useFitViewWhenMeasured(options),
      { initialProps: { options: { ...FIT_VIEW_OPTIONS } } },
    );

    rerender({ options: { ...FIT_VIEW_OPTIONS } });

    expect(mockFitView).toHaveBeenCalledTimes(1);
  });
});
