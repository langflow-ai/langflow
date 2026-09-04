import { useCallback } from "react";

interface UseSpanNodeActionsParams {
  hasChildren: boolean;
  onSelect: () => void;
  onToggle: () => void;
}

export function useSpanNodeActions({
  hasChildren,
  onSelect,
  onToggle,
}: UseSpanNodeActionsParams) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onSelect();
      }
    },
    [onSelect],
  );

  const handleExpandClick = useCallback(
    (e: React.MouseEvent) => {
      if (!hasChildren) return;
      e.stopPropagation();
      onToggle();
    },
    [hasChildren, onToggle],
  );

  return { handleKeyDown, handleExpandClick };
}
