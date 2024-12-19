import { create } from "zustand";

interface DurationState {
  durations: Record<string, number>;
  intervals: Record<string, NodeJS.Timeout>;
  setDuration: (chatId: string, duration: number) => void;
  incrementDuration: (chatId: string) => void;
  clearInterval: (chatId: string) => void;
  setInterval: (chatId: string, intervalId: NodeJS.Timeout) => void;
}

export const useDurationStore = create<DurationState>((set) => ({
  durations: {},
  intervals: {},
  setDuration: (chatId, duration) =>
    set((state) => ({
      durations: { ...state.durations, [chatId]: duration },
    })),
  incrementDuration: (chatId) =>
    set((state) => ({
      durations: {
        ...state.durations,
        [chatId]: (state.durations[chatId] || 0) + 10,
      },
    })),
  clearInterval: (chatId) =>
    set((state) => {
      if (state.intervals[chatId]) {
        clearInterval(state.intervals[chatId]);
      }
      const { [chatId]: _, ...rest } = state.intervals;
      return { intervals: rest };
    }),
  setInterval: (chatId, intervalId) =>
    set((state) => ({
      intervals: { ...state.intervals, [chatId]: intervalId },
    })),
}));
