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
 * presses ends. ReactFlow calls onNodeDragStop only after the final settle
 * change of a pointer drag, so `isDraggingRef` is still true for that change
 * and drag settles are never double-counted here.
 */
export function useKeyboardMovePersistence(
  onNodesChange: (changes: NodeChange<AllNodeType>[]) => void,
  isDraggingRef: React.RefObject<boolean>,
  takeSnapshot: () => void,
  persist: () => void,
  debounceMs = 600,
): (changes: NodeChange<AllNodeType>[]) => void {
  const burstActive = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // Keep the latest callbacks without re-creating the handler.
  const takeSnapshotRef = useRef(takeSnapshot);
  takeSnapshotRef.current = takeSnapshot;
  const persistRef = useRef(persist);
  persistRef.current = persist;

  const endBurst = useCallback(() => {
    if (!burstActive.current) return;
    burstActive.current = false;
    persistRef.current();
  }, []);

  // A move a user just made must not be lost because they navigated away
  // before the debounce fired.
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      endBurst();
    },
    [endBurst],
  );

  return useCallback(
    (changes: NodeChange<AllNodeType>[]) => {
      const isKeyboardMove =
        !isDraggingRef.current &&
        changes.some((change) => change.type === "position" && change.position);
      if (isKeyboardMove) {
        if (!burstActive.current) {
          takeSnapshotRef.current();
          burstActive.current = true;
        }
        clearTimeout(timer.current);
        timer.current = setTimeout(endBurst, debounceMs);
      }
      onNodesChange(changes);
    },
    [onNodesChange, isDraggingRef, endBurst, debounceMs],
  );
}
