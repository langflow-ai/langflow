import { create } from "zustand";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

function isSameSelection(
  left: CollaborationSelectionTarget | null,
  right: CollaborationSelectionTarget | null,
): boolean {
  if (left === right) {
    return true;
  }
  if (!left || !right) {
    return false;
  }
  return left.kind === right.kind && left.id === right.id;
}

type CollaborationLocalSelectionState = {
  localSelection: CollaborationSelectionTarget | null;
  setLocalSelection: (selected: CollaborationSelectionTarget | null) => void;
};

export const useCollaborationLocalSelectionStore =
  create<CollaborationLocalSelectionState>((set) => ({
    localSelection: null,
    setLocalSelection: (localSelection) =>
      set((state) =>
        isSameSelection(state.localSelection, localSelection)
          ? state
          : { localSelection },
      ),
  }));

export function setCollaborationLocalSelection(
  selected: CollaborationSelectionTarget | null,
): void {
  useCollaborationLocalSelectionStore.getState().setLocalSelection(selected);
}
