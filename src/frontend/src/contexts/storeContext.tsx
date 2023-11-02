import { createContext, useState } from "react";
import { checkHasStore } from "../controllers/API";
import { storeContextType } from "../types/contexts/store";

//store context to share user components and update them
const initialValue = {
  savedFlows: new Set<string>(),
  setSavedFlows: () => {},
  hasStore: true,
  setHasStore: () => {},
  hasApiKey: true,
  setHasApiKey: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<Set<string>>(new Set());

  const [hasStore, setHasStore] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(true);

  checkHasStore().then((res) => {
    setHasStore(res["enabled"]);
    setHasApiKey(res["has_api_key"]);
  });

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
