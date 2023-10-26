import { createContext, useState } from "react";
import { checkHasStore } from "../controllers/API";
import { storeContextType } from "../types/contexts/store";

//store context to share user components and update them
const initialValue = {
  savedFlows: new Set<string>(),
  setSavedFlows: () => {},
  hasStore: false,
  setHasStore: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<Set<string>>(new Set());

  const [hasStore, setHasStore] = useState(false);

  checkHasStore().then((res) => {
    setHasStore(res["enabled"]);
  });

  return (
    <StoreContext.Provider
      value={{ savedFlows, setSavedFlows, hasStore, setHasStore }}
    >
      {children}
    </StoreContext.Provider>
  );
}
