export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [name: string]: { id: string; type?: string } };
  setGlobalVariables: (variables: {
    [name: string]: { id: string; type?: string };
  }) => void;
  addGlobalVariable: (name: string, id: string, type?: string) => void;
  removeGlobalVariable: (name: string) => void;
  getVariableId: (name: string) => string | undefined;
  avaliableFields: Array<string>;
  setAvaliableFields: (fields: Array<string>) => void;
  addAvaliableField: (field: string) => void;
};
