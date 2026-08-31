import { create } from "zustand";
import { isModifierOnlyCombination } from "@/utils/shortcuts";
import { toCamelCase } from "@/utils/utils";
import { defaultShortcuts } from "../constants/constants";
import type { shortcutsStoreType } from "../types/store";

type SavedShortcut = {
  name: string;
  display_name: string;
  shortcut: string;
};

/**
 * Older builds allowed recording modifier-only combinations (e.g. just "mod"),
 * which can never fire. Restore the default combination for those entries and
 * drop the ones that no longer map to a known action.
 */
function sanitizeSavedShortcuts(saved: SavedShortcut[]): {
  sanitized: SavedShortcut[];
  changed: boolean;
} {
  let changed = false;
  const sanitized: SavedShortcut[] = [];
  saved.forEach((item) => {
    if (!isModifierOnlyCombination(item.shortcut)) {
      sanitized.push(item);
      return;
    }
    changed = true;
    const fallback = defaultShortcuts.find(
      (defaultItem) => toCamelCase(defaultItem.name) === toCamelCase(item.name),
    );
    if (fallback) {
      sanitized.push({ ...item, shortcut: fallback.shortcut });
    }
  });
  return { sanitized, changed };
}

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
  aiAssistant: "a",
  searchComponentsSidebar: "/",
  updateUniqueShortcut: (name, combination) => {
    set({
      [name]: combination,
    });
  },
  getShortcutsFromStorage: () => {
    const savedShortcuts = localStorage.getItem("langflow-shortcuts");
    if (!savedShortcuts) {
      return;
    }
    const savedArr: SavedShortcut[] = JSON.parse(savedShortcuts);
    const { sanitized, changed } = sanitizeSavedShortcuts(savedArr);
    if (changed) {
      localStorage.setItem("langflow-shortcuts", JSON.stringify(sanitized));
    }
    sanitized.forEach(({ name, shortcut }) => {
      const shortcutName = toCamelCase(name);
      set({
        [shortcutName]: shortcut,
      });
    });
    get().setShortcuts(sanitized);
  },
}));

useShortcutsStore.getState().getShortcutsFromStorage();
