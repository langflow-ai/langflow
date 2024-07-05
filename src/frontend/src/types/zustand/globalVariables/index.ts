export type GlobalVariablesStore = {
  globalVariablesEntries: Array<string> | undefined;
  globalVariables: {
    [name: string]: {
      id: string;
      type?: string;
      default_fields?: string[];
      value?: string;
    };
  };
  setGlobalVariables: (variables: {
    [name: string]: {
      id: string;
      type?: string;
      default_fields?: string[];
      value?: string;
    };
  }) => void;
  addGlobalVariable: (
    name: string,
    id: string,
    type?: string,
    default_fields?: string[],
    value?: string,
  ) => void;
  removeGlobalVariable: (name: string) => Promise<void>;
  getVariableId: (name: string) => string | undefined;
  unavaliableFields: { [name: string]: string } | undefined;
  setUnavaliableFields: (fields: { [name: string]: string }) => void;
  removeUnavaliableField: (field: string) => void;
};
