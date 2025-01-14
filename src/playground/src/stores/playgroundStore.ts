import { create } from "zustand";

interface PlaygroundStore {
  lockChat: boolean;
  setLockChat: (lock: boolean) => void;
  onLockChange?: (lock: boolean) => void;
  chatValueStore: string;
  setChatValueStore: (value: string) => void;
}

export const usePlaygroundStore = create<PlaygroundStore>((set) => ({
  lockChat: false,
  onLockChange: undefined,
  chatValueStore: "",
  setLockChat: (lock) => {
    set((state) => {
      if (state.onLockChange && state.lockChat !== lock) {
        state.onLockChange(lock);
      }
      return { lockChat: lock };
    });
  },
  setChatValueStore: (value: string) => set({ chatValueStore: value }),
}));
