import { useCallback, useRef } from "react";

import { pushHistory, readHistory } from "./input-history-storage";

type Direction = "up" | "down";

interface UseInputHistoryReturn {
  /**
   * Move through the persisted command history. ``draft`` is the text the
   * user had in the input *before* navigating — it gets returned when Down
   * walks past the newest entry so the draft is never lost.
   *
   * Returns the recalled string, or ``null`` when there's nothing to
   * recall in that direction (empty history on Up, already at present on
   * Down).
   */
  recall: (direction: Direction, draft: string) => string | null;
  /**
   * Append a new entry. Resets the pointer and the saved draft so the
   * next Up starts from the newest entry again.
   */
  push: (value: string) => void;
  /** Drop the in-flight navigation state — e.g. on manual typing. */
  reset: () => void;
}

/**
 * Hook that wraps the persistent command-history primitives with the
 * cursor and draft state needed for shell-style Up/Down navigation.
 *
 * Pointer model:
 *   - ``null`` → at the present (textarea reflects the user's live draft).
 *   - ``0`` → showing the newest history entry.
 *   - ``n`` → showing the n-th-from-newest entry (capped at history.length - 1).
 */
export function useInputHistory(): UseInputHistoryReturn {
  const pointerRef = useRef<number | null>(null);
  const draftRef = useRef<string>("");

  const recall = useCallback(
    (direction: Direction, draft: string): string | null => {
      const history = readHistory();
      if (history.length === 0) return null;

      if (direction === "up") {
        if (pointerRef.current === null) {
          // First step into history — stash the draft so Down can restore
          // it later.
          draftRef.current = draft;
          pointerRef.current = 0;
          return history[0];
        }
        // Walk to older. Clamp at the oldest entry (bash-style).
        const next = Math.min(pointerRef.current + 1, history.length - 1);
        pointerRef.current = next;
        return history[next];
      }

      // direction === "down"
      if (pointerRef.current === null) {
        // Already at present and not in history → nothing to recall.
        return null;
      }
      if (pointerRef.current === 0) {
        // One step past newest returns the original draft.
        pointerRef.current = null;
        return draftRef.current;
      }
      const next = pointerRef.current - 1;
      pointerRef.current = next;
      return history[next];
    },
    [],
  );

  const push = useCallback((value: string) => {
    pushHistory(value);
    pointerRef.current = null;
    draftRef.current = "";
  }, []);

  const reset = useCallback(() => {
    pointerRef.current = null;
    draftRef.current = "";
  }, []);

  return { recall, push, reset };
}
