import { create } from "zustand";
import { shortcutsStoreType } from "../types/store";
import { defaultShortcuts, unavailableShortcutss } from "../constants/constants";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  unavailableShortcuts: unavailableShortcutss,
  shortcuts: defaultShortcuts,
  setShortcuts: (newShortcuts, unavailable) => {
    set({shortcuts: newShortcuts, unavailableShortcuts: unavailable} );
  },
}));
