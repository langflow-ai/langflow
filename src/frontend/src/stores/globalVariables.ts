import { create } from "zustand";
import { GlobalVariablesStore } from "../types/zustand/globalVariables";

export const useGlobalVariablesStore = create<GlobalVariablesStore>(
  (set, get) => ({
    avaliableFields: [],
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
    setAvaliableFields: (fields) => {
      set({ avaliableFields: fields });
    },
    addAvaliableField: (field) => {
      set({ avaliableFields: [...get().avaliableFields, field] });
    },
    globalVariablesEntries: [],
    globalVariables: {},
    setGlobalVariables: (variables) => {
      set({
        globalVariables: variables,
        globalVariablesEntries: Object.keys(variables),
      });
    },
    addGlobalVariable: (name, id, type) => {
      const data = { id, type };
      const newVariables = { ...get().globalVariables, [name]: data };
      set({
        globalVariables: newVariables,
        globalVariablesEntries: Object.keys(newVariables),
      });
    },
    removeGlobalVariable: (name) => {
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
