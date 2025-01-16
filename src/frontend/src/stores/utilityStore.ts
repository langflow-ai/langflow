import { Pagination, Tag } from "@/types/utils/types";
import { UtilityStoreType } from "@/types/zustand/utility";
import { create } from "zustand";

export const useUtilityStore = create<UtilityStoreType>((set, get) => ({
  chatValueStore: "",
  setChatValueStore: (value: string) => set({ chatValueStore: value }),
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
  flowsPagination: {
    page: 1,
    size: 10,
  },
  setFlowsPagination: (flowsPagination: Pagination) => set({ flowsPagination }),
  tags: [],
  setTags: (tags: Tag[]) => set({ tags }),
  featureFlags: {},
  setFeatureFlags: (featureFlags: Record<string, any>) => set({ featureFlags }),
}));
