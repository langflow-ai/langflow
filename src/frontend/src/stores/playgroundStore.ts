import { PlaygroundStoreType } from "@/types/zustand/playground";
import { create } from "zustand";
import useFlowStore from "./flowStore";

export const usePlaygroundStore = create<PlaygroundStoreType>((set) => ({
  selectedSession: useFlowStore.getState().currentFlow?.id,
  setSelectedSession: (selectedSession: string | undefined) =>
    set({ selectedSession }),
  isPlayground: false,
  setIsPlayground: (isPlayground: boolean) => set({ isPlayground }),
}));
