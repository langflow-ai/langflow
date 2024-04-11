export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [name: string]: { id: string; category?: string, value?: string } };
  setGlobalVariables: (variables: {
    [name: string]: { id: string; category?: string; value?: string};
  }) => void;
  addGlobalVariable: (name: string, id: string, category?: string, value?: string) => void;
  removeGlobalVariable: (name: string) => void;
  getVariableId: (name: string) => string | undefined;
};
