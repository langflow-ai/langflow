import { PlaygroundStoreType } from "@/types/zustand/playground";
import { create } from "zustand";

export const usePlaygroundStore = create<PlaygroundStoreType>((set) => ({
  selectedViewField: undefined,
  setSelectedViewField: (selectedViewField: string) =>
    set({ selectedViewField }),
}));
