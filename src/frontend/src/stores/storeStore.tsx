import { create } from "zustand";
import { checkHasApiKey, checkHasStore } from "../controllers/API";
import { StoreStoreType } from "../types/zustand/store";

export const useStoreStore = create<StoreStoreType>((set) => ({
  hasStore: true,
  validApiKey: false,
  hasApiKey: false,
  loadingApiKey: true,
  updateHasStore: (hasStore) => set(() => ({ hasStore: hasStore })),
  updateValidApiKey: (validApiKey) => set(() => ({ validApiKey: validApiKey })),
  updateLoadingApiKey: (loadingApiKey) =>
    set(() => ({ loadingApiKey: loadingApiKey })),
  updateHasApiKey: (hasApiKey) => set(() => ({ hasApiKey: hasApiKey })),
}));

checkHasStore().then((res) => {
  useStoreStore.setState({ hasStore: res?.enabled ?? false });
});

const fetchApiData = async () => {
  useStoreStore.setState({ loadingApiKey: true });
  try {
    const res = await checkHasApiKey();

    useStoreStore.setState({
      loadingApiKey: false,
      validApiKey: res?.is_valid ?? false,
      hasApiKey: res?.has_api_key ?? false,
    });
  } catch (e) {
    useStoreStore.setState({ loadingApiKey: false });
    console.log(e);
  }
};

fetchApiData();
