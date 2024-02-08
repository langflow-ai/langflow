export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [key: string]: { id: string; provider: string } };
  setGlobalVariables: (variables: {
    [key: string]: { id: string; provider: string };
  }) => void;
  addGlobalVariable: (key: string, value: string, provider?: string) => void;
  removeGlobalVariable: (key: string) => void;
};
