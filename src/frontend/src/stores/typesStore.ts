import { create } from "zustand";
import type { APIDataType } from "../types/api";
import type { TypesStoreType } from "../types/zustand/types";
import {
  extractSecretFieldsFromComponents,
  templatesGenerator,
  typesGenerator,
} from "../utils/reactflowUtils";

export const useTypesStore = create<TypesStoreType>((set, get) => ({
  ComponentFields: new Set(),
  setComponentFields: (fields) => {
    set({ ComponentFields: fields });
  },
  addComponentField: (field) => {
    set({ ComponentFields: get().ComponentFields.add(field) });
  },
  types: {},
  templates: {},
  data: {},
  setTypes: (data: APIDataType) => {
    set((old) => ({
      types: typesGenerator(data),
      data: { ...old.data, ...data },
      ComponentFields: extractSecretFieldsFromComponents({
        ...old.data,
        ...data,
      }),
      templates: templatesGenerator(data),
    }));
  },
  setTemplates: (newState: {}) => {
    set({ templates: newState });
  },
  setData: (change: APIDataType | ((old: APIDataType) => APIDataType)) => {
    const newChange =
      typeof change === "function" ? change(get().data) : change;
    set({ data: newChange });
    get().setComponentFields(extractSecretFieldsFromComponents(newChange));
  },
}));
