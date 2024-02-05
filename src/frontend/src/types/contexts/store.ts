export type storeContextType = {
  setHasStore: (store: boolean) => void;
  hasStore: boolean;
  setHasApiKey: (key: boolean) => void;
  hasApiKey: boolean;
  setValidApiKey: (key: boolean) => void;
  validApiKey: boolean;
  loadingApiKey: boolean;
};
