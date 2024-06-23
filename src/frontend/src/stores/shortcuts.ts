import { create } from "zustand";
import { defaultShortcuts } from "../constants/constants";
import { shortcutsStoreType } from "../types/store";

export const useShortcutsStore = create<shortcutsStoreType>((set, get) => ({
  shortcuts: defaultShortcuts,
  setShortcuts: (newShortcuts) => {
    set({ shortcuts: newShortcuts });
  },
  output: "o",
  play: "p",
  flow: "mod+b",
  undo: "mod+z",
  redo: "mod+y",
  open: "mod+k",
  advanced: "mod+shift+a",
  minimize: "mod+shift+q",
  code: "space",
  copy: "mod+c",
  duplicate: "mod+d",
  component: "mod+shift+s",
  docs: "mod+shift+d",
  save: "mod+s",
  delete: "backspace",
  group: "mod+g",
  cut: "mod+x",
  paste: "mod+v",
  api: "r",
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
      const savedArr = JSON.parse(savedShortcuts!);
      savedArr.forEach(({ name, shortcut }) => {
        let shortcutName = name.split(" ")[0].toLowerCase();
        set({
          [shortcutName]: shortcut,
        });
      });
      get().setShortcuts(JSON.parse(savedShortcuts!));
    }
  },
}));

useShortcutsStore.getState().getShortcutsFromStorage();
