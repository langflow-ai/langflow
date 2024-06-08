import { create } from "zustand";
import {
  defaultShortcuts,
  unavailableShortcutss,
} from "../constants/constants";
import { shortcutsStoreType } from "../types/store";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  unavailableShortcuts: unavailableShortcutss,
  shortcuts: defaultShortcuts,
  setShortcuts: (newShortcuts, unavailable) => {
    set({ shortcuts: newShortcuts, unavailableShortcuts: unavailable });
  },
  undo: "mod+z",
  redo: "mod+y",
  open: "mod+k",
  advanced: "mod+shift+a",
  minimize: "mod+shift+q",
  code: "space",
  copy: "mod+c",
  duplicate: "mod+d",
  share: "mod+shift+s",
  docs: "mod+shift+d",
  save: "mod+s",
  delete: "backspace",
  group: "mod+g",
  cut: "mod+x",
  paste: "mod+v",
  api: "mod+r",
  update: "mod+u",
  download: "mod+j",
  freeze: "mod+f",
  updateUniqueShortcut: (name, combination) => {
    set({
      [name]: combination,
    });
  },
  getShortcutsFromStorage: () => {
    if (localStorage.getItem("langflow-shortcuts")) {
      const savedShortcuts = localStorage.getItem("langflow-shortcuts");
      const savedUShortcuts = localStorage.getItem("langflow-UShortcuts");
      get().setShortcuts(
        JSON.parse(savedShortcuts!),
        JSON.parse(savedUShortcuts!),
      );
    }
  },
}));

useShortcutsStore.getState().getShortcutsFromStorage();
