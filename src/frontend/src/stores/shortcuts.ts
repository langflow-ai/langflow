import { create } from "zustand";
import { shortcutsStoreType } from "../types/store";
import { defaultShortcuts, unavailableShortcutss } from "../constants/constants";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  unavailableShortcuts: unavailableShortcutss,
  shortcuts: defaultShortcuts,
  setShortcuts: (newShortcuts, unavailable) => {
    set({shortcuts: newShortcuts, unavailableShortcuts: unavailable} );
  },
  undo: "mod+z",
  redo: "mod+y",
  open: "mod+k",
  advanced: "mod+shift+a",
  minimize: "mod+shift+q",
  code: "mod+shift+u",
  copy: "mod+c",
  duplicate: "mod+d",
  share: "mod+shift+s",
  docs: "mod+shift+d",
  save: "mod+s",
  delete: "backspace",
  updateUniqueShortcut: (name, combination) => {
    set({
      [name]: combination
    })
  }
}));
