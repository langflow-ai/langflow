export type UtilityStoreType = {
  selectedItems: any[];
  setSelectedItems: (itemId: any) => void;
  healthCheckTimeout: string | null;
  setHealthCheckTimeout: (timeout: string | null) => void;
  playgroundScrollBehaves: ScrollBehavior;
  setPlaygroundScrollBehaves: (behaves: ScrollBehavior) => void;
};
