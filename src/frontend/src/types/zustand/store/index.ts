type fetchApiDataParam = {
  has_api_key: boolean;
  is_valid: boolean;
};

export type StoreStoreType = {
  hasStore: boolean;
  validApiKey: boolean;
  hasApiKey: boolean;
  loadingApiKey: boolean;
  checkHasStore: () => void;
  updateValidApiKey: (validApiKey: boolean) => void;
  updateHasApiKey: (hasApiKey: boolean) => void;
  updateLoadingApiKey: (loadingApiKey: boolean) => void;
  fetchApiData: (data: fetchApiDataParam) => void;
};
