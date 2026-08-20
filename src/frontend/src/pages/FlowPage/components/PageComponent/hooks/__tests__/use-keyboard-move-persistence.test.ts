import { act, renderHook } from "@testing-library/react";
import type { NodeChange } from "@xyflow/react";
import type { AllNodeType } from "@/types/flow";
import { useKeyboardMovePersistence } from "../use-keyboard-move-persistence";

const positionChange = (
  id: string,
  dragging: boolean,
): NodeChange<AllNodeType> => ({
  id,
  type: "position",
  position: { x: 10, y: 10 },
  dragging,
});

const dimensionChange = (id: string): NodeChange<AllNodeType> => ({
  id,
  type: "dimensions",
  dimensions: { width: 100, height: 50 },
});

function setup(isDragging = false, debounceMs = 600) {
  const onNodesChange = jest.fn();
  const takeSnapshot = jest.fn();
  const persist = jest.fn();
  const flushPersist = jest.fn();
  const isDraggingRef = { current: isDragging };
  const { result, unmount } = renderHook(() =>
    useKeyboardMovePersistence(
      onNodesChange,
      isDraggingRef,
      takeSnapshot,
      persist,
      debounceMs,
      flushPersist,
    ),
  );
  return {
    result,
    unmount,
    onNodesChange,
    takeSnapshot,
    persist,
    flushPersist,
    isDraggingRef,
  };
}

describe("useKeyboardMovePersistence", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("always delegates changes to the wrapped handler", () => {
    const { result, onNodesChange } = setup();
    const changes = [dimensionChange("a")];
    act(() => result.current(changes));
    expect(onNodesChange).toHaveBeenCalledWith(changes);
  });

  it("snapshots once per burst of keyboard moves and persists after the debounce", () => {
    const { result, takeSnapshot, persist } = setup();
    act(() => {
      result.current([positionChange("a", false)]);
      result.current([positionChange("a", false)]);
      result.current([positionChange("a", false)]);
    });
    // one snapshot for the whole burst, taken before the moves apply
    expect(takeSnapshot).toHaveBeenCalledTimes(1);
    expect(persist).not.toHaveBeenCalled();
    act(() => jest.advanceTimersByTime(700));
    expect(persist).toHaveBeenCalledTimes(1);
  });

  it("starts a fresh snapshot for a new burst after the previous one persisted", () => {
    const { result, takeSnapshot, persist } = setup();
    act(() => result.current([positionChange("a", false)]));
    act(() => jest.advanceTimersByTime(700));
    act(() => result.current([positionChange("a", false)]));
    act(() => jest.advanceTimersByTime(700));
    expect(takeSnapshot).toHaveBeenCalledTimes(2);
    expect(persist).toHaveBeenCalledTimes(2);
  });

  it("ignores position changes while a pointer drag is active (drag handles its own snapshot/save)", () => {
    const { result, takeSnapshot, persist, isDraggingRef } = setup(true);
    act(() => result.current([positionChange("a", true)]));
    // the final settle change of a drag arrives with dragging=false but
    // before onNodeDragStop clears the ref
    act(() => result.current([positionChange("a", false)]));
    isDraggingRef.current = false;
    act(() => jest.advanceTimersByTime(700));
    expect(takeSnapshot).not.toHaveBeenCalled();
    expect(persist).not.toHaveBeenCalled();
  });

  it("ignores non-position changes", () => {
    const { result, takeSnapshot, persist } = setup();
    act(() => result.current([dimensionChange("a")]));
    act(() => jest.advanceTimersByTime(700));
    expect(takeSnapshot).not.toHaveBeenCalled();
    expect(persist).not.toHaveBeenCalled();
  });

  it("ignores a selection-rectangle drag even though the node drag ref never flips", () => {
    // ReactFlow routes a selection-rect drag through onSelectionDrag*, not the
    // node drag handlers — its position changes arrive with dragging: true
    // while isDraggingRef can still be false. They must not be mistaken for
    // keyboard moves (that costs a second snapshot: one drag, two undos).
    const { result, takeSnapshot, persist } = setup(false);
    act(() => result.current([positionChange("a", true)]));
    act(() => result.current([positionChange("b", true)]));
    act(() => jest.advanceTimersByTime(700));
    expect(takeSnapshot).not.toHaveBeenCalled();
    expect(persist).not.toHaveBeenCalled();
  });

  it("uses the flush variant on unmount so the save fires before navigation swaps the flow", () => {
    // A plain persist() only schedules the debounced autosave, which can fire
    // after the store already points at a different flow — the wrapper must
    // hand unmount to the synchronous flush path instead.
    const { result, unmount, persist, flushPersist } = setup();
    act(() => result.current([positionChange("a", false)]));
    unmount();
    expect(flushPersist).toHaveBeenCalledTimes(1);
    expect(persist).not.toHaveBeenCalled();
  });
});
