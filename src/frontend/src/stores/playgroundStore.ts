import { create } from "zustand";
import type { PlaygroundStoreType } from "@/types/zustand/playground";

export const usePlaygroundStore = create<PlaygroundStoreType>((set) => ({
  selectedSession: undefined,
  setSelectedSession: (selectedSession: string | undefined) =>
    set({ selectedSession }),
  isPlayground: false,
  setIsPlayground: (isPlayground: boolean) => set({ isPlayground }),
  isFullscreen: false,
  toggleFullscreen: () =>
    set((state) => ({ isFullscreen: !state.isFullscreen })),
  setIsFullscreen: (isFullscreen: boolean) => set({ isFullscreen }),
  isOpen: false,
  setIsOpen: (isOpen: boolean) => set({ isOpen }),
  reset: (flowId: string) =>
    set({
      selectedSession: flowId,
      isFullscreen: false,
      isOpen: false,
    }),
}));
