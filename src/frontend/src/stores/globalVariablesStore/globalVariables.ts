import { create } from "zustand";
import { GlobalVariablesStore } from "../../types/zustand/globalVariables";
import getUnavailableFields from "./utils/get-unavailable-fields";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    unavaliableFields: undefined,
    setUnavaliableFields: (fields) => {
      set({ unavaliableFields: fields });
    },
    removeUnavaliableField: (field) => {
      const newFields = get().unavaliableFields || {};
      delete newFields[field];
      set({ unavaliableFields: newFields });
    },
    globalVariablesEntries: undefined,
    globalVariables: {},
    setGlobalVariables: (variables) => {
      set({
        globalVariables: variables,
        globalVariablesEntries: Object.keys(variables) || [],
        unavaliableFields: getUnavailableFields(variables),
      });
    },
    addGlobalVariable: (name, id, type, default_fields) => {
      const data = { id, type, default_fields };
      const newVariables = { ...get().globalVariables, [name]: data };
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables) || [],
        unavaliableFields: getUnavailableFields(newVariables),
      });
    },
    removeGlobalVariable: async (name) => {
      const id = get().globalVariables[name]?.id;
      if (id === undefined) return;
      const newVariables = { ...get().globalVariables };
      delete newVariables[name];
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables) || [],
        unavaliableFields: getUnavailableFields(newVariables),
      });
    },
    getVariableId: (name) => {
      return get().globalVariables[name]?.id;
    },
  }),
);
