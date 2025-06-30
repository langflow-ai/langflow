import { create } from "zustand";
import { GlobalVariablesStore } from "../../types/zustand/globalVariables";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    unavailableFields: {},
    setUnavailableFields: (fields) => {
      set({ unavailableFields: fields });
    },
    globalVariablesEntries: undefined,
    setGlobalVariablesEntries: (entries) => {
      set({ globalVariablesEntries: entries });
    },
    setGlobalVariablesEntities: (entities) => {
      set({ globalVariablesEntities: entities });
    },
    globalVariablesEntities: undefined,
    setUsageData: (usageData) => {
      set({ usageData });
    },
    usageData: undefined,
  }),
);
