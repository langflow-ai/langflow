import { act, renderHook } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFitViewWhenMeasured } from "../use-fit-view-when-measured";

const mockFitView = jest.fn();
let mockNodesInitialized = false;
let mockCanvasSize = { width: 1000, height: 800 };
let mockViewport = { x: 0, y: 0, zoom: 1 };

/** Stands in for the viewport ReactFlow lands on after a fit. */
function fitLandsOn(viewport: { x: number; y: number; zoom: number }) {
  mockFitView.mockImplementation(() => {
    mockViewport = viewport;
  });
}

jest.mock("@xyflow/react", () => ({
  useNodesInitialized: () => mockNodesInitialized,
  useReactFlow: () => ({
    fitView: mockFitView,
    getViewport: () => mockViewport,
  }),
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
    mockFitView.mockReset();
    setNodesInitialized(false);
    mockCanvasSize = { width: 1000, height: 800 };
    mockViewport = { x: 0, y: 0, zoom: 1 };
    useFlowStore.setState({ fitViewRequest: { id: 0 } });
    useFlowsManagerStore.setState({ currentFlowId: "" });
  });

  it("should not fit while the canvas holds no flow", () => {
    setNodesInitialized(true);
    renderHook(() => useFitViewWhenMeasured(FIT_VIEW_OPTIONS));

    expect(mockFitView).not.toHaveBeenCalled();
  });

  // Regression: measuring a graph is not a request. A user dropping the first
  // component onto an empty canvas measures one too, and re-framing there moves
  // the canvas out from under them mid-edit.
  it("should not fit when nodes appear without a request", () => {
    openFlow("flow-1");
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    setNodesInitialized(true);
    rerender();

    expect(mockFitView).not.toHaveBeenCalled();
  });

  // The bug this hook exists for: ReactFlow resolves a queued fit on the first
  // internals batch, so a fit that runs while nodes are still unmeasured drops
  // them from the bounding box and the flow opens framed around a subset.
  it("should hold a requested fit until every node is measured", () => {
    openFlow("flow-1");
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    act(() => {
      useFlowStore.getState().requestFitView();
    });
    expect(mockFitView).not.toHaveBeenCalled();

    setNodesInitialized(true);
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
    expect(mockFitView).toHaveBeenCalledWith(FIT_VIEW_OPTIONS);
  });

  it("should fit immediately when the nodes are already measured", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    renderHook(() => useFitViewWhenMeasured(FIT_VIEW_OPTIONS));

    act(() => {
      useFlowStore.getState().requestFitView();
    });

    expect(mockFitView).toHaveBeenCalledTimes(1);
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

  it("should fit once per request, not on every re-render", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    act(() => {
      useFlowStore.getState().requestFitView();
    });
    rerender();
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
  });

  // Version restore replaces the graph under the same flow id.
  it("should fit again for a later request", () => {
    openFlow("flow-1");
    setNodesInitialized(true);
    renderHook(() => useFitViewWhenMeasured(FIT_VIEW_OPTIONS));

    act(() => {
      useFlowStore.getState().requestFitView();
    });
    act(() => {
      useFlowStore.getState().requestFitView();
    });

    expect(mockFitView).toHaveBeenCalledTimes(2);
  });

  it("should run the request's callback after the fit", () => {
    const onFitted = jest.fn();
    openFlow("flow-1");
    setNodesInitialized(true);
    renderHook(() => useFitViewWhenMeasured(FIT_VIEW_OPTIONS));

    act(() => {
      useFlowStore.getState().requestFitView(onFitted);
    });

    expect(onFitted).toHaveBeenCalledTimes(1);
    expect(useFlowStore.getState().fitViewRequest.onFitted).toBeUndefined();
  });

  describe("canvas resize after the fit", () => {
    // The welcome overlay hides the sidebar while it is up: the canvas is wider
    // for the fit and narrows the moment the overlay closes, leaving the graph
    // framed for a viewport it no longer has.
    it("should refit when the canvas resizes and the viewport is untouched", () => {
      openFlow("flow-1");
      setNodesInitialized(true);
      fitLandsOn({ x: -100, y: 40, zoom: 0.6 });
      const { rerender } = renderHook(() =>
        useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
      );

      act(() => {
        useFlowStore.getState().requestFitView();
      });
      expect(mockFitView).toHaveBeenCalledTimes(1);

      mockCanvasSize = { width: 780, height: 800 };
      rerender();

      expect(mockFitView).toHaveBeenCalledTimes(2);
    });

    it("should leave a viewport the user has moved alone", () => {
      openFlow("flow-1");
      setNodesInitialized(true);
      fitLandsOn({ x: -100, y: 40, zoom: 0.6 });
      const { rerender } = renderHook(() =>
        useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
      );

      act(() => {
        useFlowStore.getState().requestFitView();
      });

      // The user pans, then resizes the window.
      mockViewport = { x: -400, y: 120, zoom: 0.6 };
      mockCanvasSize = { width: 780, height: 800 };
      rerender();

      expect(mockFitView).toHaveBeenCalledTimes(1);
    });

    it("should correct a request at most once", () => {
      openFlow("flow-1");
      setNodesInitialized(true);
      fitLandsOn({ x: -100, y: 40, zoom: 0.6 });
      const { rerender } = renderHook(() =>
        useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
      );

      act(() => {
        useFlowStore.getState().requestFitView();
      });
      mockCanvasSize = { width: 780, height: 800 };
      rerender();
      expect(mockFitView).toHaveBeenCalledTimes(2);

      mockCanvasSize = { width: 700, height: 800 };
      rerender();

      expect(mockFitView).toHaveBeenCalledTimes(2);
    });
  });

  // The sequence a template open actually depends on, end to end: the fit runs
  // under the welcome overlay, the callback uncovers the canvas, the sidebar
  // returns and narrows it, and the correction re-frames the graph for the size
  // the canvas settles at.
  it("should frame the graph for the canvas the overlay leaves behind", () => {
    openFlow("flow-1");
    mockCanvasSize = { width: 1920, height: 920 };
    const { rerender } = renderHook(() =>
      useFitViewWhenMeasured(FIT_VIEW_OPTIONS),
    );

    const closeOverlay = jest.fn();

    act(() => {
      useFlowStore.getState().requestFitView(closeOverlay);
    });
    expect(mockFitView).not.toHaveBeenCalled();

    // The template's nodes finish measuring.
    fitLandsOn({ x: -80, y: 95, zoom: 0.64 });
    setNodesInitialized(true);
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(1);
    expect(closeOverlay).toHaveBeenCalledTimes(1);

    // Uncovering is a React state update, so ReactFlow only learns the canvas
    // narrowed once its ResizeObserver fires, after layout.
    mockCanvasSize = { width: 1640, height: 920 };
    rerender();

    expect(mockFitView).toHaveBeenCalledTimes(2);
  });
});
