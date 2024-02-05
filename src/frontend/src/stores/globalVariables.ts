import { create } from "zustand";
import { GlobalVariablesStore } from "../types/zustand/globalVariables";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    globalVariablesEntries: [],
    globalVariables: {},
    setGlobalVariables: (variables) => {
      set({
        globalVariables: variables,
        globalVariablesEntries: Object.keys(variables),
      });
    },
    addGlobalVariable: (key, value) => {
      const newVariables = { ...get().globalVariables, [key]: value };
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables),
      });
    },
    removeGlobalVariable: (key) => {
      const newVariables = { ...get().globalVariables };
      delete newVariables[key];
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables),
      });
    },
  })
);
