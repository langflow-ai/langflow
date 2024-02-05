import { create } from "zustand";
import { GlobalVariablesStore } from "../types/zustand/globalVariables";

const useGlobalVariablesStore = create<GlobalVariablesStore>((set, get) => ({
  globalVariables: [],
  setGlobalVariables: (variables) => {
    set({ globalVariables: variables });
  },
}));
