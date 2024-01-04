import { create } from "zustand";
import { checkHasApiKey, checkHasStore } from "../controllers/API";

type State = {
  hasStore: boolean;
  validApiKey: boolean;
  hasApiKey: boolean;
  loadingApiKey: boolean;
};

type Action = {
  updateHasStore: (hasStore: State["hasStore"]) => void;
  updateValidApiKey: (validApiKey: State["validApiKey"]) => void;
  updateHasApiKey: (hasApiKey: State["hasApiKey"]) => void;
  updateLoadingApiKey: (loadingApiKey: State["loadingApiKey"]) => void;
};

export const useStoreStore = create<State & Action>((set) => ({
  hasStore: true,
  validApiKey: false,
  hasApiKey: false,
  loadingApiKey: true,
  updateHasStore: (hasStore) => set(() => ({ hasStore: hasStore })),
  updateValidApiKey: (validApiKey) => set(() => ({ validApiKey: validApiKey })),
  updateLoadingApiKey: (hasApiKey) => set(() => ({ hasApiKey: hasApiKey })),
  updateHasApiKey: (loadingApiKey) =>
    set(() => ({ loadingApiKey: loadingApiKey })),
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
