import { create } from "zustand";
import type { APIDataType, ComponentDisplayNamesType } from "../types/api";
import type { TypesStoreType } from "../types/zustand/types";
import {
  extractSecretFieldsFromComponents,
  templatesGenerator,
  typesGenerator,
} from "../utils/reactflowUtils";

export const useTypesStore = create<TypesStoreType>((set, get) => ({
  activeScopeKey: null,
  activateScope: (scopeKey) => {
    if (get().activeScopeKey === scopeKey) return;
    set({
      activeScopeKey: scopeKey,
      types: {},
      templates: {},
      data: {},
      ComponentFields: new Set(),
      componentDisplayNames: {} as ComponentDisplayNamesType,
    });
  },
  setScopedTypes: (scopeKey, data, componentDisplayNames) => {
    if (get().activeScopeKey !== scopeKey) return false;
    set({
      types: typesGenerator(data),
      data,
      ComponentFields: extractSecretFieldsFromComponents(data),
      templates: templatesGenerator(data),
      componentDisplayNames,
    });
    return true;
  },
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
    set({
      types: typesGenerator(data),
      data,
      ComponentFields: extractSecretFieldsFromComponents(data),
      templates: templatesGenerator(data),
    });
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
  componentDisplayNames: {} as ComponentDisplayNamesType,
  setComponentDisplayNames: (data: ComponentDisplayNamesType) => {
    set({ componentDisplayNames: data });
  },
}));
