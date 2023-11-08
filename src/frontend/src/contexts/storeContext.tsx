import { createContext, useEffect, useState } from "react";
import { checkHasStore } from "../controllers/API";
import { storeContextType } from "../types/contexts/store";

//store context to share user components and update them
const initialValue = {
  savedFlows: new Set<string>(),
  setSavedFlows: () => {},
  hasStore: true,
  setHasStore: () => {},
  hasApiKey: false,
  setHasApiKey: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<Set<string>>(new Set());

  const [hasStore, setHasStore] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [storeChecked, setStoreChecked] = useState(false);

  useEffect(() => {
    const fetchStoreData = async () => {
      try {
        if (storeChecked) return;
        const res = await checkHasStore();
        setHasStore(res?.enabled ?? false);
        setHasApiKey(res?.has_api_key ?? false);
        setStoreChecked(true);
      } catch (e) {
        console.log(e);
      }
    };

    fetchStoreData();
  }, []);

  return (
    <StoreContext.Provider
      value={{
        savedFlows,
        setSavedFlows,
        hasStore,
        setHasStore,
        hasApiKey,
        setHasApiKey,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}
