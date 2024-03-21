export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [name: string]: { id: string; provider?: string } };
  setGlobalVariables: (variables: {
    [name: string]: { id: string; provider?: string };
  }) => void;
  addGlobalVariable: (name: string, id: string, provider?: string) => void;
  removeGlobalVariable: (name: string) => void;
  getVariableId: (name: string) => string | undefined;
};
