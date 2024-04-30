import { create } from "zustand";
import { GlobalVariablesStore } from "../types/zustand/globalVariables";
import { deleteGlobalVariable } from "../controllers/API";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    unavaliableFields: new Set(),
    setUnavaliableFields: (fields) => {
      set({ unavaliableFields: fields });
    },
    addUnavaliableField: (field) => {
      set({ unavaliableFields: get().unavaliableFields.add(field) });
    },
    removeUnavaliableField: (field) => {
      get().unavaliableFields.delete(field);
    },
    globalVariablesEntries: [],
    globalVariables: {},
    setGlobalVariables: (variables) => {
      set({
        globalVariables: variables,
        globalVariablesEntries: Object.keys(variables),
      });
    },
    addGlobalVariable: (name, id, type, default_fields) => {
      const data = { id, type, default_fields };
      const newVariables = { ...get().globalVariables, [name]: data };
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables),
      });
    },
    removeGlobalVariable:async (name) => {
      const id = get().globalVariables[name]?.id;
      if (id === undefined) return;
      await deleteGlobalVariable(id)
      const newVariables = { ...get().globalVariables };
      delete newVariables[name];
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables),
      });
    },
    getVariableId: (name) => {
      return get().globalVariables[name]?.id;
    },
  })
);
