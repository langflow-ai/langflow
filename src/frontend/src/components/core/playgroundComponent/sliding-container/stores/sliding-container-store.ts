import { create } from "zustand";

const MIN_WIDTH = 300;
const MAX_WIDTH_RATIO = 0.5;
const DEFAULT_WIDTH = 400;

export interface SlidingContainerStoreType {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  toggle: () => void;
  width: number;
  setWidth: (width: number) => void;
  isFullscreen: boolean;
  setIsFullscreen: (isFullscreen: boolean) => void;
  toggleFullscreen: () => void;
}

export const useSlidingContainerStore = create<SlidingContainerStoreType>(
  (set) => ({
    isOpen: false,
    setIsOpen: (isOpen: boolean) => set({ isOpen }),
    toggle: () => set((state) => ({ isOpen: !state.isOpen })),
    width: DEFAULT_WIDTH,
    setWidth: (width: number) => {
      const maxWidth = window.innerWidth * MAX_WIDTH_RATIO;
      set({ width: Math.max(MIN_WIDTH, Math.min(maxWidth, width)) });
    },
    isFullscreen: false,
    setIsFullscreen: (isFullscreen: boolean) => set({ isFullscreen }),
    toggleFullscreen: () =>
      set((state) => ({ isFullscreen: !state.isFullscreen })),
  }),
);
