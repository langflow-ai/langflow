import { create } from "zustand";
import { shortcutsStoreType } from "../types/store";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  openCodeModalWShortcut: false,
  handleModalWShortcut: (modal) => {
    switch (modal) {
      case "code":
        set({
          openCodeModalWShortcut: !get().openCodeModalWShortcut,
        });
        break;
    }
  },
}));
