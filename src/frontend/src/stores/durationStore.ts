import { create } from "zustand";

interface DurationState {
  durations: Record<string, number>;
  intervals: Record<string, NodeJS.Timeout>;
  startTimes: Record<string, number>;
  setDuration: (chatId: string, duration: number) => void;
  startTimer: (chatId: string) => void;
  clearInterval: (chatId: string) => void;
  clearStartTime: (chatId: string) => void;
  setInterval: (chatId: string, intervalId: NodeJS.Timeout) => void;
}

export const useDurationStore = create<DurationState>((set) => ({
  durations: {},
  intervals: {},
  startTimes: {},
  setDuration: (chatId, duration) =>
    set((state) => ({
      durations: { ...state.durations, [chatId]: duration },
    })),
  startTimer: (chatId) =>
    set((state) => ({
      startTimes: { ...state.startTimes, [chatId]: Date.now() },
      durations: { ...state.durations, [chatId]: 0 },
    })),
  clearInterval: (chatId) =>
    set((state) => {
      if (state.intervals[chatId]) {
        clearInterval(state.intervals[chatId]);
      }
      const { [chatId]: _interval, ...restIntervals } = state.intervals;
      // Don't remove startTime - preserve it so timer can resume when component remounts
      return {
        intervals: restIntervals,
      };
    }),
  clearStartTime: (chatId) =>
    set((state) => {
      const { [chatId]: _startTime, ...restStartTimes } = state.startTimes;
      return {
        startTimes: restStartTimes,
      };
    }),
  setInterval: (chatId, intervalId) =>
    set((state) => ({
      intervals: { ...state.intervals, [chatId]: intervalId },
    })),
}));
