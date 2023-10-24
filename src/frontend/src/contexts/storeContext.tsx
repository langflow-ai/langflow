import { createContext, useState } from "react";
import { storeContextType } from "../types/contexts/store";

//store context to share user components and update them
const initialValue = {
  savedFlows: new Set<string>(),
  setSavedFlows: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<Set<string>>(new Set());

  return (
    <StoreContext.Provider value={{ savedFlows, setSavedFlows }}>
      {children}
    </StoreContext.Provider>
  );
}
