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
    addGlobalVariable: (key, id, provider) => {
      const data = { id, provider };
      const newVariables = { ...get().globalVariables, [key]: data };
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
    getVariableId: (key) => {
      return get().globalVariables[key]?.id;
    }
  })
);
