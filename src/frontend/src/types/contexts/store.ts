export type storeContextType = {
  savedFlows: Set<string>;
  setSavedFlows: (newState: Set<string>) => void;
  setHasStore: (store: boolean) => void;
  hasStore: boolean;
  setHasApiKey: (key: boolean) => void;
  hasApiKey: boolean;
  getSavedComponents: () => void;
  errorApiKey: boolean;
  loadingSaved: boolean;
};
