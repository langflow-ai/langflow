import { create } from "zustand";
import { ENABLE_LANGFLOW_STORE } from "@/customization/feature-flags";
import { checkHasApiKey, checkHasStore } from "../controllers/API";
import type { StoreStoreType } from "../types/zustand/store";

export const useStoreStore = create<StoreStoreType>((set) => ({
  hasStore: ENABLE_LANGFLOW_STORE,
  validApiKey: false,
  hasApiKey: false,
  loadingApiKey: true,
  checkHasStore: () => {
    checkHasStore().then((res) => {
      set({
        hasStore: ENABLE_LANGFLOW_STORE && (res?.enabled ?? false),
      });
    });
  },
  updateValidApiKey: (validApiKey) => set(() => ({ validApiKey: validApiKey })),
  updateLoadingApiKey: (loadingApiKey) =>
    set(() => ({ loadingApiKey: loadingApiKey })),
  updateHasApiKey: (hasApiKey) => set(() => ({ hasApiKey: hasApiKey })),
  fetchApiData: async () => {
    set({ loadingApiKey: true });
    try {
      const res = await checkHasApiKey();
      set({
        validApiKey: res?.is_valid ?? false,
        hasApiKey: res?.has_api_key ?? false,
        loadingApiKey: false,
      });
    } catch (e) {
      set({ loadingApiKey: false });
      console.error(e);
    }
  },
}));
