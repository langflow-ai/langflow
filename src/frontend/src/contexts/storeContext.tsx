import { createContext, useState } from "react";
import { storeContextType } from "../types/contexts/store";
import { FlowType } from "../types/flow";

//store context to share user components and update them
const initialValue = {
  savedFlows: {},
  setSavedFlows: () => {},
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<{ [key: string]: FlowType }>({});

  return (
    <StoreContext.Provider value={{ savedFlows, setSavedFlows }}>
      {children}
    </StoreContext.Provider>
  );
}
