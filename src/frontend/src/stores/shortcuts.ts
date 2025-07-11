import { toCamelCase } from "@/utils/utils";
import { create } from "zustand";
import { defaultShortcuts } from "../constants/constants";
import type { shortcutsStoreType } from "../types/store";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  shortcuts: defaultShortcuts,
  setShortcuts: (newShortcuts) => {
    set({ shortcuts: newShortcuts });
  },
  outputInspection: "o",
  play: "p",
  flow: "mod+shift+b",
  undo: "mod+z",
  redo: "mod+y",
  redoAlt: "mod+shift+z",
  openPlayground: "mod+k",
  advancedSettings: "mod+shift+a",
  minimize: "mod+.",
  code: "space",
  copy: "mod+c",
  duplicate: "mod+d",
  componentShare: "mod+shift+s",
  docs: "mod+shift+d",
  changesSave: "mod+s",
  saveComponent: "mod+alt+s",
  delete: "backspace",
  group: "mod+g",
  cut: "mod+x",
  paste: "mod+v",
  api: "r",
  update: "mod+u",
  download: "mod+j",
  freezePath: "mod+shift+f",
  toolMode: "mod+shift+m",
  toggleSidebar: "mod+b",
  searchComponentsSidebar: "/",
  updateUniqueShortcut: (name, combination) => {
    set({
      [name]: combination,
    });
  },
  getShortcutsFromStorage: () => {
    if (localStorage.getItem("langflow-shortcuts")) {
      const savedShortcuts = localStorage.getItem("langflow-shortcuts");
      const savedArr = JSON.parse(savedShortcuts!);
      savedArr.forEach(({ name, shortcut }) => {
        const shortcutName = toCamelCase(name);
        set({
          [shortcutName]: shortcut,
        });
      });
      get().setShortcuts(JSON.parse(savedShortcuts!));
    }
  },
}));

useShortcutsStore.getState().getShortcutsFromStorage();
