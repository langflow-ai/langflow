import { create } from "zustand";
import { getAll } from "../controllers/API";
import { APIDataType } from "../types/api";
import { TypesStoreType } from "../types/zustand/types";
import { templatesGenerator, typesGenerator } from "../utils/reactflowUtils";
import useAlertStore from "./alertStore";

export const useTypesStore = create<TypesStoreType>((set, get) => ({
  types: {},
  templates: {},
  data: {},
  getTypes: () => {
    return new Promise<void>(async (resolve, reject) => {
      getAll()
        .then((response) => {
          const data = response.data;
          useAlertStore.setState({ loading: false });
          set((old) => ({
            types: typesGenerator(data),
            data: { ...old.data, ...data },
            templates: templatesGenerator(data),
          }));
          resolve();
        })
        .catch((error) => {
          useAlertStore.getState().setErrorData({
            title: "An error has occurred while fetching types.",
            list: ["Please refresh the page."],
          });
          console.error("An error has occurred while fetching types.");
          console.log(error);
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
  },
}));
