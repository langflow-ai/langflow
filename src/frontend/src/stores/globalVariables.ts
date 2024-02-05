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
  })
);
