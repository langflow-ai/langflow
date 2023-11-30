import { createContext, useContext, useEffect, useState } from "react";
import { checkHasApiKey, checkHasStore } from "../controllers/API";
import { storeContextType } from "../types/contexts/store";
import { AuthContext } from "./authContext";

//store context to share user components and update them
const initialValue = {
  hasStore: true,
  setHasStore: () => {},
  validApiKey: false,
  setValidApiKey: () => {},
  hasApiKey: false,
  setHasApiKey: () => {},
  loadingApiKey: true,
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [hasStore, setHasStore] = useState(false);
  const [loadingApiKey, setLoadingApiKey] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(true);
  const [validApiKey, setValidApiKey] = useState(false);
  const [storeChecked, setStoreChecked] = useState(false);
  const { apiKey } = useContext(AuthContext);

  useEffect(() => {
    const fetchStoreData = async () => {
      try {
        if (storeChecked) return;
        const res = await checkHasStore();
        setHasStore(res?.enabled ?? false);
        setStoreChecked(true);
      } catch (e) {
        console.log(e);
      }
    };

    fetchStoreData();
  }, []);

  const fetchApiData = async () => {
    setLoadingApiKey(true);
    try {
      const res = await checkHasApiKey();
      setHasApiKey(res?.has_api_key ?? false);
      setValidApiKey(res?.is_valid ?? false);
      setLoadingApiKey(false);
    } catch (e) {
      setLoadingApiKey(false);
      console.log(e);
    }
  };

  useEffect(() => {
    fetchApiData();
  }, [storeChecked, apiKey]);

  return (
    <StoreContext.Provider
      value={{
        hasStore,
        setHasStore,
        hasApiKey,
        setHasApiKey,
        validApiKey,
        setValidApiKey,
        loadingApiKey,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}
