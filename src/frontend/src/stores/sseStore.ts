import { create } from "zustand";
import { SSEStoreType } from "../types/zustand/sse";

export const useSSEStore = create<SSEStoreType>((set) => ({
    updateSSEData: (sseData) => {
        set({ sseData });
    },
    sseData: {},
    isBuilding: false,
    setIsBuilding: (isBuilding) => {
        set({ isBuilding });
    },
}));
