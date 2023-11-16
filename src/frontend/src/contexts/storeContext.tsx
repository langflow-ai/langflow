import { createContext, useEffect, useState } from "react";
import {
  checkHasApiKey,
  checkHasStore,
  getStoreComponents,
} from "../controllers/API";
import { storeContextType } from "../types/contexts/store";

//store context to share user components and update them
const initialValue = {
  savedFlows: new Set<string>(),
  setSavedFlows: () => {},
  hasStore: true,
  setHasStore: () => {},
  hasApiKey: false,
  setHasApiKey: () => {},
  getSavedComponents: () => {},
  errorApiKey: false,
  loadingSaved: false,
};

export const StoreContext = createContext<storeContextType>(initialValue);

export function StoreProvider({ children }) {
  const [savedFlows, setSavedFlows] = useState<Set<string>>(new Set());

  const [hasStore, setHasStore] = useState(true);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [storeChecked, setStoreChecked] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [errorApiKey, setErrorApiKey] = useState(false);

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
    getSavedComponents();
  }, []);

  function getSavedComponents() {
    setLoadingSaved(true);
    getStoreComponents({
      sort: "-count(liked_by)",
      liked: true,
    })
      .then((data) => {
        if (data?.authorized === false) {
          setErrorApiKey(true);
          setSavedFlows(new Set<string>());
        } else {
          let savedIds = new Set<string>();
          let results = data?.results ?? [];
          results.forEach((flow) => {
            savedIds.add(flow.id);
          });
          setSavedFlows(savedIds);
          setErrorApiKey(false);
          setLoadingSaved(false);
        }
      })
      .catch((err) => {
        setSavedFlows(new Set<string>());
        setErrorApiKey(true);
      });
  }

  useEffect(() => {
    const fetchStoreData = async () => {
      try {
        if (storeChecked) return;
        const res = await checkHasApiKey();
        console.log(res);
        setHasApiKey(res?.has_api_key ?? false);
      } catch (e) {
        console.log(e);
      }
    };

    fetchStoreData();
  }, [storeChecked]);

  return (
    <StoreContext.Provider
      value={{
        savedFlows,
        setSavedFlows,
        hasStore,
        setHasStore,
        hasApiKey,
        setHasApiKey,
        getSavedComponents,
        errorApiKey,
        loadingSaved,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}
