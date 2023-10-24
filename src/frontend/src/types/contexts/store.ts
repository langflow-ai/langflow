export type storeContextType = {
  savedFlows: Set<string>;
  setSavedFlows: (newState: Set<string>) => void;
};
