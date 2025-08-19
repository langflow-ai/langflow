import { create } from "zustand";
import type { PlaygroundStoreType } from "@/types/zustand/playground";

export const usePlaygroundStore = create<PlaygroundStoreType>((set) => ({
  selectedSession: undefined,
  setSelectedSession: (selectedSession: string | undefined) =>
    set({ selectedSession }),
  isPlayground: false,
  setIsPlayground: (isPlayground: boolean) => set({ isPlayground }),
  isFullscreen: false,
  setIsFullscreen: (isFullscreen: boolean) => set({ isFullscreen }),
}));
