import { createContext } from "react";

export type ActionPickerAddingContextValue = {
  isAdding: boolean;
  startAdding: () => void;
  stopAdding: () => void;
};

// Bridges the header "+" and the badge row, which render in separate DOM subtrees.
export const ActionPickerAddingContext =
  createContext<ActionPickerAddingContextValue>({
    isAdding: false,
    startAdding: () => {},
    stopAdding: () => {},
  });
