import { create } from "zustand";
import { useSlidingContainerStore } from "@/components/core/playgroundComponent/sliding-container/stores";
import type { PlaygroundStoreType } from "@/types/zustand/playground";

export const usePlaygroundStore = create<PlaygroundStoreType>((set, get) => ({
  selectedSession: undefined,
  setSelectedSession: (selectedSession: string | undefined) =>
    set({ selectedSession }),
  isPlayground: false,
  setIsPlayground: (isPlayground: boolean) => set({ isPlayground }),
  isFullscreen: false,
  toggleFullscreen: () => {
    set((state) => {
      const next = !state.isFullscreen;
      useSlidingContainerStore.getState().setIsFullscreen(next);
      return { isFullscreen: next };
    });
  },
  setIsFullscreen: (isFullscreen: boolean) => {
    useSlidingContainerStore.getState().setIsFullscreen(isFullscreen);
    set({ isFullscreen });
  },
  isOpen: false,
  setIsOpen: (isOpen: boolean) => {
    useSlidingContainerStore.getState().setIsOpen(isOpen);
    set({ isOpen });
  },
  reset: (flowId: string) =>
    set(() => {
      useSlidingContainerStore.getState().setIsFullscreen(false);
      useSlidingContainerStore.getState().setIsOpen(false);
      return {
        selectedSession: flowId,
        isFullscreen: false,
        isOpen: false,
      };
    }),
}));
