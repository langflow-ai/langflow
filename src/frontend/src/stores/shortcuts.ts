import { create } from "zustand";
import { toCamelCase } from "@/utils/utils";
import { defaultShortcuts } from "../constants/constants";
import type { shortcutsStoreType } from "../types/store";
import useFlowStore from "./flowStore";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  shortcuts: useFlowStore.getState().inspectionPanelVisible
    ? defaultShortcuts.filter(
        (shortcut) => shortcut.name !== "Advanced Settings",
      )
    : defaultShortcuts,
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
      const savedArrFiltered = useFlowStore.getState().inspectionPanelVisible
        ? savedArr.filter((shortcut) => shortcut.name !== "Advanced Settings")
        : savedArr;
      savedArrFiltered.forEach(({ name, shortcut }) => {
        const shortcutName = toCamelCase(name);
        set({
          [shortcutName]: shortcut,
        });
      });
      get().setShortcuts(savedArrFiltered);
    }
  },
}));

useShortcutsStore.getState().getShortcutsFromStorage();
