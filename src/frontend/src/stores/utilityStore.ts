import { UtilityStoreType } from "@/types/zustand/utility";
import { create } from "zustand";

export const useUtilityStore = create<UtilityStoreType>((set, get) => ({
  selectedItems: [],
  setSelectedItems: (itemId) => {
    if (get().selectedItems.includes(itemId)) {
      set({
        selectedItems: get().selectedItems.filter((item) => item !== itemId),
      });
    } else {
      set({ selectedItems: get().selectedItems.concat(itemId) });
    }
  },
  healthCheckTimeout: null,
  setHealthCheckTimeout: (timeout: string | null) =>
    set({ healthCheckTimeout: timeout }),
  playgroundScrollBehaves: "instant",
  setPlaygroundScrollBehaves: (behaves: ScrollBehavior) =>
    set({ playgroundScrollBehaves: behaves }),
  maxFileSizeUpload: 100 * 1024 * 1024, // 100MB in bytes
  setMaxFileSizeUpload: (maxFileSizeUpload: number) =>
    set({ maxFileSizeUpload: maxFileSizeUpload * 1024 * 1024 }),
}));
