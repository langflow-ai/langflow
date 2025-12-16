import { create } from "zustand";

type PlaygroundState = {
  isPlayground: boolean;
  selectedSession?: string;
  setSelectedSession: (id?: string) => void;
};

const usePlaygroundStore = create<PlaygroundState>((set) => ({
  isPlayground: true,
  selectedSession: undefined,
  setSelectedSession: (id) => set({ selectedSession: id }),
}));

export { usePlaygroundStore };
