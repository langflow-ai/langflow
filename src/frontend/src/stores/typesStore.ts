import { create } from "zustand";
import { getAll } from "../controllers/API";
import { APIDataType } from "../types/api";
import { TypesStoreType } from "../types/zustand/types";
import {
  extractFieldsFromComponenents,
  templatesGenerator,
  typesGenerator,
} from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";
import useFlowsManagerStore from "./flowsManagerStore";

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
  getTypes: () => {
    return new Promise<void>(async (resolve, reject) => {
      const setLoading = useFlowsManagerStore.getState().setIsLoading;
      setLoading(true);
      getAll()
        .then((response) => {
          const data = response?.data;
          useAlertStore.setState({ loading: false });
          set((old) => ({
            types: typesGenerator(data),
            data: { ...old.data, ...data },
            ComponentFields: extractFieldsFromComponenents({
              ...old.data,
              ...data,
            }),
            templates: templatesGenerator(data),
          }));
          setLoading(false);
          resolve();
        })
        .catch((error) => {
          console.error("An error has occurred while fetching types.");
          console.log(error);
          setLoading(false);
          reject();
        });
    });
  },
  setTypes: (newState: {}) => {
    set({ types: newState });
  },
  setTemplates: (newState: {}) => {
    set({ templates: newState });
  },
  setData: (change: APIDataType | ((old: APIDataType) => APIDataType)) => {
    let newChange = typeof change === "function" ? change(get().data) : change;
    set({ data: newChange });
    get().setComponentFields(extractFieldsFromComponenents(newChange));
  },
}));
