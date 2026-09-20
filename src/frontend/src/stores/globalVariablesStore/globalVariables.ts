import { create } from "zustand";
import type { GlobalVariablesStore } from "../../types/zustand/globalVariables";
import getUnavailableFields from "./utils/get-unavailable-fields";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    setGlobalVariables: (entities) => {
      set({
        globalVariablesEntries: entities.map((entry) => entry.name),
        unavailableFields: getUnavailableFields(entities),
        globalVariablesEntities: entities,
      });
    },
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
  }),
);
