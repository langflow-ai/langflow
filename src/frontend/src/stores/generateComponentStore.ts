import { create } from "zustand";

const DEFAULT_MAX_RETRIES = 3;
const STORAGE_KEY = "generate-component-max-retries";

const getStoredMaxRetries = (): number => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) {
      const value = parseInt(stored, 10);
      if (!isNaN(value) && value >= 0 && value <= 5) {
        return value;
      }
    }
  } catch {
    // localStorage not available
  }
  return DEFAULT_MAX_RETRIES;
};

type GenerateComponentStoreType = {
  isTerminalOpen: boolean;
  maxRetries: number;
  setTerminalOpen: (open: boolean) => void;
  toggleTerminal: () => void;
  setMaxRetries: (value: number) => void;
};

export const useGenerateComponentStore = create<GenerateComponentStoreType>((set) => ({
  isTerminalOpen: false,
  maxRetries: getStoredMaxRetries(),
  setTerminalOpen: (open) => set({ isTerminalOpen: open }),
  toggleTerminal: () => set((state) => ({ isTerminalOpen: !state.isTerminalOpen })),
  setMaxRetries: (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, value.toString());
    } catch {
      // localStorage not available
    }
    set({ maxRetries: value });
  },
}));
