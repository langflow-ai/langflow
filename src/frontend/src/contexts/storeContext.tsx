import { createContext, useState } from "react";
import { checkHasStore } from "../controllers/API";
import { storeContextType } from "../types/contexts/store";
import { FlowType } from "../types/flow";

//store context to share user components and update them
const initialValue = {
  savedFlows: {},
  setSavedFlows: () => {},
  hasStore: false,
  setHasStore: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<{ [key: string]: FlowType }>({});
  const [hasStore, setHasStore] = useState(false);

  checkHasStore().then((res) => {
    setHasStore(res[0].has_store);
  });

  return (
    <StoreContext.Provider
      value={{ savedFlows, setSavedFlows, hasStore, setHasStore }}
    >
      {children}
    </StoreContext.Provider>
  );
}
