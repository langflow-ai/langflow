import { useEffect, useRef } from "react";
import { create } from "zustand";

interface ThinkingDurationState {
  startTime: number | null;
  duration: number | null;
  setStartTime: (time: number) => void;
  setDuration: (duration: number) => void;
  reset: () => void;
}

export const useThinkingDurationStore = create<ThinkingDurationState>(
  (set) => ({
    startTime: null,
    duration: null,
    setStartTime: (time) => set({ startTime: time, duration: null }),
    setDuration: (duration) => set({ duration, startTime: null }),
    reset: () => set({ startTime: null, duration: null }),
  }),
);

// Hook to track thinking duration based on isBuilding state
export function useTrackThinkingDuration(isBuilding: boolean) {
  const { setStartTime, setDuration } = useThinkingDurationStore();
  const wasBuilding = useRef(false);

  useEffect(() => {
    if (isBuilding && !wasBuilding.current) {
      // Building just started
      setStartTime(Date.now());
    } else if (!isBuilding && wasBuilding.current) {
      // Building just finished - read startTime directly from store to avoid stale closure
      const currentStartTime = useThinkingDurationStore.getState().startTime;
      if (currentStartTime) {
        const elapsed = Date.now() - currentStartTime;
        setDuration(elapsed);
      }
    }
    wasBuilding.current = isBuilding;
  }, [isBuilding, setStartTime, setDuration]);
}

// Hook to get the last thinking duration
export function useThinkingDuration() {
  return useThinkingDurationStore((state) => state.duration);
}
