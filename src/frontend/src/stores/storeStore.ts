import FeatureFlags from "@/../feature-config.json";
import { create } from "zustand";
import { checkHasApiKey, checkHasStore } from "../controllers/API";
import { StoreStoreType } from "../types/zustand/store";

export const useStoreStore = create<StoreStoreType>((set) => ({
  hasStore: true,
  validApiKey: false,
  hasApiKey: false,
  loadingApiKey: true,
  checkHasStore: () => {
    checkHasStore().then((res) => {
      set({
        hasStore: FeatureFlags.ENABLE_LANGFLOW_STORE && (res?.enabled ?? false),
      });
    });
  },
  updateValidApiKey: (validApiKey) => set(() => ({ validApiKey: validApiKey })),
  updateLoadingApiKey: (loadingApiKey) =>
    set(() => ({ loadingApiKey: loadingApiKey })),
  updateHasApiKey: (hasApiKey) => set(() => ({ hasApiKey: hasApiKey })),
  fetchApiData: (data) => {
    set({
      validApiKey: data?.is_valid ?? false,
      hasApiKey: data?.has_api_key ?? false,
    });
  },
}));
