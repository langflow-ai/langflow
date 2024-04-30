export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string>;
  globalVariables: { [name: string]: { id: string; type?: string, default_fields?: string[] } };
  setGlobalVariables: (variables: {
    [name: string]: { id: string; type?: string, default_fields?: string[]};
  }) => void;
  addGlobalVariable: (name: string, id: string, type?: string, default_fields?: string[]) => void;
  removeGlobalVariable: (name: string) => Promise<void>;
  getVariableId: (name: string) => string | undefined;
  unavaliableFields: Set<string>;
  setUnavaliableFields: (fields: Set<string>) => void;
  addUnavaliableField: (field: string) => void;
  removeUnavaliableField: (field: string) => void;
};
