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
  const isDraggingRef = { current: isDragging };
  const { result, unmount } = renderHook(() =>
    useKeyboardMovePersistence(
      onNodesChange,
      isDraggingRef,
      takeSnapshot,
      persist,
      debounceMs,
    ),
  );
  return {
    result,
    unmount,
    onNodesChange,
    takeSnapshot,
    persist,
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

  it("flushes a pending persist on unmount so a move is not lost to navigation", () => {
    const { result, unmount, persist } = setup();
    act(() => result.current([positionChange("a", false)]));
    unmount();
    expect(persist).toHaveBeenCalledTimes(1);
  });
});
