import type { NodeChange } from "@xyflow/react";
import { useCallback, useEffect, useRef } from "react";
import type { AllNodeType } from "@/types/flow";

/**
 * Mouse drags persist and become undoable through onNodeDragStart
 * (takeSnapshot) and onNodeDragStop (autoSaveFlow + updateCurrentFlow).
 * Keyboard moves — ReactFlow's arrow-key moveSelectedNodes, enabled now that
 * disableKeyboardA11y is off — only flow through onNodesChange, so without
 * this they are lost on reload and invisible to undo.
 *
 * Wraps the onNodesChange handler: a position change that arrives while no
 * pointer drag is active is a keyboard move. The first one in a burst takes
 * an undo snapshot BEFORE the change is applied (so undo restores the
 * pre-move position); a trailing debounce persists once the burst of arrow
 * presses ends.
 *
 * Pointer gestures are excluded two ways, and both are needed:
 * - `isDraggingRef` mirrors the drag lifecycle (node drag AND selection-rect
 *   drag handlers set/clear it). ReactFlow fires the stop callbacks only
 *   after the final settle change, so the settle (which arrives with
 *   `dragging: false`) is still covered by the ref.
 * - any change carrying `dragging: true` is skipped outright — ReactFlow
 *   marks every mid-drag change that way, while its keyboard
 *   `moveSelectedNodes` never does. This catches any pointer path that has
 *   no lifecycle handler wired at all.
 */
export function useKeyboardMovePersistence(
  onNodesChange: (changes: NodeChange<AllNodeType>[]) => void,
  isDraggingRef: React.RefObject<boolean>,
  takeSnapshot: () => void,
  persist: () => void,
  debounceMs = 600,
  // Unmount usually means navigation: a plain persist() only schedules the
  // debounced autosave, which fires after the store may already point at a
  // different flow and would silently drop the move. The flush variant saves
  // synchronously while the store still holds this flow.
  flushPersist: () => void = persist,
): (changes: NodeChange<AllNodeType>[]) => void {
  const burstActive = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // Keep the latest callbacks without re-creating the handler.
  const takeSnapshotRef = useRef(takeSnapshot);
  takeSnapshotRef.current = takeSnapshot;
  const persistRef = useRef(persist);
  persistRef.current = persist;
  const flushPersistRef = useRef(flushPersist);
  flushPersistRef.current = flushPersist;

  const endBurst = useCallback((mode: "debounced" | "flush" = "debounced") => {
    if (!burstActive.current) return;
    burstActive.current = false;
    (mode === "flush" ? flushPersistRef : persistRef).current();
  }, []);

  // A move a user just made must not be lost because they navigated away
  // before the debounce fired.
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      endBurst("flush");
    },
    [endBurst],
  );

  return useCallback(
    (changes: NodeChange<AllNodeType>[]) => {
      const isKeyboardMove =
        !isDraggingRef.current &&
        changes.some(
          (change) =>
            change.type === "position" && change.position && !change.dragging,
        );
      if (isKeyboardMove) {
        if (!burstActive.current) {
          takeSnapshotRef.current();
          burstActive.current = true;
        }
        clearTimeout(timer.current);
        timer.current = setTimeout(() => endBurst(), debounceMs);
      }
      onNodesChange(changes);
    },
    [onNodesChange, isDraggingRef, endBurst, debounceMs],
  );
}
